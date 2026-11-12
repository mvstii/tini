import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import GraphSettings
from app.graph.expand import expand, load_anchors
from app.graph.expansion import plan_expansion
from app.graph.store import enforce_size_cap, store_edges
from app.models import (
    Artist,
    ArtistEdge,
    FetchLog,
    GraphSnapshot,
    Track,
    User,
    UserTrackMeta,
)
from app.sources.http import SourceError
from app.sources.lastfm import LfmSimilar

CFG = GraphSettings()
NOW = datetime(2026, 10, 30, tzinfo=UTC)


@pytest.fixture
def db(test_engine):
    engine = test_engine
    try:
        conn = engine.connect()
    except Exception:
        pytest.skip("PostgreSQL erişilemiyor")
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    trans.rollback()
    conn.close()


# --- plan_expansion (saf) ---


def test_plan_fetches_unknown_anchors_only_at_level_zero():
    plan = plan_expansion([3, 1, 1], 2, fresh=set(), edges={})
    assert plan.to_fetch == [1, 3] and plan.cached == 0


def test_plan_walks_cached_edges_to_next_level():
    plan = plan_expansion([1], 2, fresh={1}, edges={1: [5, 4]})
    assert plan.to_fetch == [4, 5] and plan.cached == 1


def test_plan_depth_one_does_not_expand_neighbors():
    plan = plan_expansion([1], 1, fresh={1}, edges={1: [4]})
    assert plan.to_fetch == [] and plan.cached == 1


def test_plan_all_fresh_is_empty_and_negative_cache_stops_branch():
    plan = plan_expansion([1], 3, fresh={1, 2}, edges={1: [2]})  # 2 boş sonuç, kenarı yok
    assert plan.to_fetch == [] and plan.cached == 2


def test_plan_handles_cycles_and_is_deterministic():
    edges = {1: [2], 2: [1]}
    a = plan_expansion([1], 3, {1, 2}, edges)
    assert a == plan_expansion([1], 3, {1, 2}, edges)
    assert a.visited == 2


# --- store / expand ---


class FakeLfm:
    def __init__(self, table):
        self.table = table
        self.calls = []

    def get_similar(self, name=None, mbid=None, limit=20):
        self.calls.append((name, mbid))
        v = self.table.get(mbid or name, [])
        if isinstance(v, Exception):
            raise v
        return v


def mk_artist(db, name, mbid=None):
    a = Artist(name=name, name_norm=name.lower(), mbid=mbid)
    db.add(a)
    db.flush()
    return a


def test_store_caps_neighbors_dedupes_and_skips_self(db):
    cfg = GraphSettings(edge_max_neighbors=2)
    a = mk_artist(db, "Aaa")
    sims = [
        LfmSimilar("Bbb", None, 0.5), LfmSimilar("Ccc", None, 0.9),
        LfmSimilar("Ddd", None, 0.1), LfmSimilar("Aaa", None, 1.0),
    ]
    # Aaa'nın kendisi Last.fm adıyla gelirse ayrı satır açılır; kapasite en yüksek 2 ile sınırlı.
    n = store_edges(db, a.id, sims, cfg, NOW, 100)
    assert n == 2
    rows = db.execute(select(ArtistEdge.weight).where(ArtistEdge.src == a.id)).scalars().all()
    assert sorted(rows) == [0.9, 1.0]


def test_store_replaces_old_edges_and_clamps_weight(db):
    a = mk_artist(db, "Aaa")
    store_edges(db, a.id, [LfmSimilar("Bbb", None, 0.4)], CFG, NOW, 100)
    store_edges(db, a.id, [LfmSimilar("Ccc", None, 7.0)], CFG, NOW, 100)
    rows = db.execute(select(ArtistEdge.weight).where(ArtistEdge.src == a.id)).scalars().all()
    assert rows == [1.0]


def test_store_neighbor_with_mbid_reuses_existing_artist(db):
    m = uuid.uuid4()
    b = mk_artist(db, "Bbb", mbid=m)
    a = mk_artist(db, "Aaa")
    store_edges(db, a.id, [LfmSimilar("Bbb", m, 0.5)], CFG, NOW, 100)
    assert db.scalar(select(ArtistEdge.dst).where(ArtistEdge.src == a.id)) == b.id


def test_expand_walks_two_levels_caches_and_snapshots(db):
    a = mk_artist(db, "Aaa")
    db.add(Track(isrc="USAAA0000001", artist_id=a.id))
    db.flush()
    lfm = FakeLfm({"Aaa": [LfmSimilar("Bbb", None, 0.8)], "Bbb": [LfmSimilar("Ccc", None, 0.5)]})
    r = expand(db, lfm, CFG, limit=10, depth=2, anchors=[a.id], now=NOW)
    assert r["ok"] == 2 and r["fetched"] == 2 and r["snapshot"] is not None
    assert r["cache_hit_ratio"] == 0.0
    assert [c[0] for c in lfm.calls] == ["Aaa", "Bbb"]
    snap = db.get(GraphSnapshot, r["snapshot"])
    assert snap.edge_count >= 2 and snap.params["depth"] == 2

    lfm2 = FakeLfm({})
    r2 = expand(db, lfm2, CFG, limit=10, depth=2, anchors=[a.id], now=NOW + timedelta(hours=1))
    assert lfm2.calls == [] and r2["fetched"] == 0 and r2["cache_hit_ratio"] == 1.0
    assert r2["snapshot"] is None


def test_expand_refetches_after_ttl_and_respects_limit(db):
    a = mk_artist(db, "Aaa")
    lfm = FakeLfm({"Aaa": [LfmSimilar("Bbb", None, 0.8)]})
    r = expand(db, lfm, CFG, limit=1, depth=2, anchors=[a.id], now=NOW)
    assert r["fetched"] == 1
    later = NOW + timedelta(seconds=CFG.fetch_ok_ttl_seconds + 1)
    lfm2 = FakeLfm({"Aaa": [LfmSimilar("Bbb", None, 0.8)]})
    expand(db, lfm2, CFG, limit=1, depth=1, anchors=[a.id], now=later)
    assert [c[0] for c in lfm2.calls] == ["Aaa"]


def test_expand_error_and_empty_are_negative_cached(db):
    a = mk_artist(db, "Aaa")
    lfm = FakeLfm({"Aaa": SourceError("boom")})
    r = expand(db, lfm, CFG, limit=5, depth=2, anchors=[a.id], now=NOW)
    assert r["error"] == 1 and r["snapshot"] is None
    r = expand(db, lfm, CFG, limit=5, depth=2, anchors=[a.id], now=NOW + timedelta(seconds=10))
    assert len(lfm.calls) == 1  # hata TTL'si içinde yeniden denenmez
    log = db.get(FetchLog, ("lastfm_similar", f"artist:{a.id}"))
    assert log.status == "error"


def test_shared_tables_carry_no_spotify_strings(db):
    u = User(email="g@example.com", password_hash="x")
    t = Track(isrc="USAAA0000002")
    a = mk_artist(db, "Aaa")
    db.add_all([u, t])
    db.flush()
    t.artist_id = a.id
    db.add(
        UserTrackMeta(
            user_id=u.id, track_id=t.id, title="SPOTIFY-BASLIK", artist_names=["SPOTIFY-SANATCI"],
            duration_ms=1, expires_at=NOW + timedelta(hours=1),
        )
    )
    db.flush()
    lfm = FakeLfm({"Aaa": [LfmSimilar("Bbb", None, 0.8)]})
    assert a.id in load_anchors(db)  # kademe A çapası
    expand(db, lfm, CFG, limit=5, depth=2, anchors=[a.id], now=NOW)
    names = db.scalars(select(Artist.name)).all()
    assert not any("SPOTIFY" in (n or "") for n in names)
    assert db.scalar(select(func.count()).select_from(ArtistEdge)) >= 1


def test_enforce_size_cap_drops_oldest_when_over_max(db):
    a = mk_artist(db, "Aaa")
    old = NOW - timedelta(days=5)
    store_edges(db, a.id, [LfmSimilar("Old", None, 0.5)], CFG, old, 100)
    b = mk_artist(db, "Bbb")
    store_edges(db, b.id, [LfmSimilar("New", None, 0.5)], CFG, NOW, 100)
    # Gerçek tablo küçük; eşikleri bayt cinsinden aşağı çekerek aşımı simüle et.
    cfg = GraphSettings(edge_warn_bytes=1, edge_max_bytes=2)
    res = enforce_size_cap(db, cfg)
    assert res["dropped"] >= 1
    left = db.scalar(select(func.count()).select_from(ArtistEdge))
    assert left < 2


def test_enforce_size_cap_noop_under_limit(db):
    assert enforce_size_cap(db, CFG)["dropped"] == 0
