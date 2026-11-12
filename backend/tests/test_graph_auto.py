import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GraphSettings
from app.graph import scheduler
from app.graph.auto import TRACKS_SOURCE, artists_needing_tracks, fill_tracks
from app.graph.expand import load_anchors
from app.jobs.worker import Worker
from app.models import (
    Artist,
    ArtistEdge,
    FetchLog,
    GeneratedList,
    ListItem,
    Track,
    User,
)
from app.sources.http import SourceError
from app.sources.musicbrainz import parse_artist_isrcs

CFG = GraphSettings()
NOW = datetime(2026, 11, 4, tzinfo=UTC)


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


class FakeMb:
    def __init__(self, by_mbid: dict, fail: bool = False) -> None:
        self.by_mbid, self.fail, self.calls = by_mbid, fail, 0

    def artist_isrcs(self, mbid, limit):
        self.calls += 1
        if self.fail:
            raise SourceError("boom")
        return self.by_mbid.get(mbid, [])


def _artist(db, name="x", mbid=True):
    a = Artist(name=name, name_norm=name, mbid=uuid.uuid4() if mbid else None)
    db.add(a)
    db.flush()
    return a


def test_parse_artist_isrcs_skips_invalid_and_duplicates():
    rid = str(uuid.uuid4())
    data = {"recordings": [
        {"id": rid, "isrcs": ["ZZA000000001", "ZZA000000002"]},
        {"id": str(uuid.uuid4()), "isrcs": ["ZZA000000001"]},
        {"id": str(uuid.uuid4()), "isrcs": []},
        {"id": str(uuid.uuid4()), "isrcs": ["SHORT"]},
    ]}
    out = parse_artist_isrcs(data)
    assert out == [("ZZA000000001", uuid.UUID(rid))]
    assert parse_artist_isrcs(None) == []


def test_fill_tracks_adds_capped_isrc_tracks_and_logs(db):
    a = _artist(db)
    pairs = [(f"ZZF{k:09d}", uuid.uuid4()) for k in range(8)]
    mb = FakeMb({a.mbid: pairs})
    res = fill_tracks(db, mb, [a.id], CFG, NOW)
    got = db.scalars(select(Track.isrc).where(Track.artist_id == a.id)).all()
    assert len(got) == CFG.tracks_per_artist == res["tracks"]
    log = db.get(FetchLog, (TRACKS_SOURCE, f"artist:{a.id}"))
    assert log.status == "ok"
    fill_tracks(db, mb, [a.id], CFG, NOW)
    assert mb.calls == 1  # parçası var: tekrar sorulmaz


def test_fill_tracks_negative_cache_and_error(db):
    a, b, c = _artist(db), _artist(db), _artist(db, mbid=False)
    mb = FakeMb({})
    fill_tracks(db, mb, [a.id, c.id], CFG, NOW)
    fill_tracks(db, mb, [a.id], CFG, NOW)
    assert mb.calls == 1  # boş sonuç önbelleklendi, MBID'siz atlandı
    assert db.get(FetchLog, (TRACKS_SOURCE, f"artist:{a.id}")).status == "empty"
    res = fill_tracks(db, FakeMb({}, fail=True), [b.id], CFG, NOW)
    assert res["error"] == 1
    assert db.scalars(select(Track).where(Track.artist_id == b.id)).first() is None


def test_fill_tracks_existing_isrc_not_duplicated(db):
    a, other = _artist(db), _artist(db)
    db.add(Track(isrc="ZZG000000001", artist_id=other.id))
    db.flush()
    fill_tracks(db, FakeMb({a.mbid: [("ZZG000000001", uuid.uuid4())]}), [a.id], CFG, NOW)
    assert db.scalar(select(Track.artist_id).where(Track.isrc == "ZZG000000001")) == other.id


def test_artists_needing_tracks_lists_then_neighbors(db):
    # Teste özel kenar kaynağı: paylaşılan veritabanındaki gerçek grafı taramaz (yavaşlık).
    cfg = CFG.model_copy(update={"edge_source": "test_auto"})
    src, listed, nb, has = _artist(db), _artist(db), _artist(db), _artist(db)
    db.add(Track(isrc="ZZH000000001", artist_id=has.id))
    for dst, w in ((nb, 0.9), (has, 0.8)):
        db.add(ArtistEdge(
            src=src.id, dst=dst.id, source=cfg.edge_source, weight=w,
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        ))
    user = User(email=f"{uuid.uuid4()}@t.io", password_hash="x")
    db.add(user)
    db.flush()
    lst = GeneratedList(
        user_id=user.id, kind="main", profile_version=1, algo_version="t",
        candidate_algo_version="t", graph_version=1, params={},
    )
    db.add(lst)
    db.flush()
    db.add(ListItem(
        list_id=lst.id, position=0, artist_id=listed.id, track_id=None, score=1, reasons=[]
    ))
    db.flush()
    out = artists_needing_tracks(db, cfg, NOW, 100000)
    assert out.index(listed.id) < out.index(nb.id)
    assert has.id not in out and src.id not in out
    assert listed.id in load_anchors(db)  # öneri listesindeki sanatçı çapa olur


def test_scheduler_disabled(monkeypatch):
    class Cfg:
        auto_expand = False

    monkeypatch.setattr(scheduler, "get_graph_settings", lambda: Cfg())
    started = []
    monkeypatch.setattr(scheduler, "run_round", lambda: started.append(1))

    async def go():
        async with scheduler.lifespan(None):
            await asyncio.sleep(0.05)

    asyncio.run(go())
    assert started == []


def test_loop_survives_errors(monkeypatch):
    calls = []

    def fake():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(scheduler, "run_round", fake)
    monkeypatch.setattr(scheduler, "idle_seconds", lambda: 1e9)  # boşta: beklemeden çalış
    w = Worker(5)
    monkeypatch.setattr(scheduler, "get_worker", lambda: w)

    async def go():
        task = asyncio.create_task(scheduler._loop(0, 0.01))
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(go())
    assert len(calls) >= 2
