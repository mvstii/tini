import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.resolve import resolve_pending
from app.catalog.resolve_b import resolve_pending_b, resolve_track_b
from app.config import GraphSettings
from app.db import make_engine
from app.models import (
    Artist,
    ArtistRef,
    FetchLog,
    Track,
    User,
    UserTrackArtist,
    UserTrackMeta,
)
from app.sources.http import SourceError
from app.sources.lastfm import LfmArtist

CFG = GraphSettings()
NOW = datetime(2026, 10, 30, tzinfo=UTC)


@pytest.fixture
def db():
    engine = make_engine()
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


class FakeLfm:
    def __init__(self, table):
        self.table = table
        self.calls = []

    def get_info(self, name=None, mbid=None):
        self.calls.append(name)
        v = self.table.get(name)
        if isinstance(v, Exception):
            raise v
        return v


class NoMB:
    def lookup_isrc(self, isrc):
        return None


def setup(db, isrc, names, email="b@example.com"):
    u = User(email=email, password_hash="x")
    t = Track(isrc=isrc)
    db.add_all([u, t])
    db.flush()
    db.add(
        UserTrackMeta(
            user_id=u.id, track_id=t.id, title="SPOTIFY-BASLIK", artist_names=names,
            duration_ms=1, expires_at=NOW + timedelta(hours=1),
        )
    )
    db.flush()
    return u, t


def mb_empty(db):
    """Kademe A'yı çalıştırıp yalnızca bu testteki ISRC'leri boş bırak."""
    resolve_pending(db, NoMB(), CFG, limit=100000, now=NOW)


def test_tier_b_links_user_only_not_shared_track(db):
    u, t = setup(db, "ZZB000000001", ["ezhel"])
    lfm = FakeLfm({"ezhel": LfmArtist("Ezhel", None)})
    assert resolve_track_b(db, u.id, t.id, "ezhel", lfm, CFG, NOW) == "linked"
    link = db.get(UserTrackArtist, (u.id, t.id))
    a = db.get(Artist, link.artist_id)
    assert (a.name, a.name_norm, a.mbid) == ("Ezhel", "ezhel", None)
    assert link.method == "name_lastfm" and link.confidence >= CFG.tier_b_min_confidence
    db.refresh(t)
    assert t.artist_id is None  # paylaşılan parça bağı kurulmaz
    ref = db.scalars(select(ArtistRef).where(ArtistRef.artist_id == a.id)).one()
    assert (ref.provider, ref.provider_id) == ("lastfm", "name:ezhel")


def test_tier_b_reuses_existing_mbid_artist(db):
    m = uuid.uuid4()
    existing = Artist(mbid=m, name="Ezhel", name_norm="ezhel")
    db.add(existing)
    u, t = setup(db, "ZZB000000002", ["Ezhel"], "b2@example.com")
    lfm = FakeLfm({"Ezhel": LfmArtist("Ezhel", m)})
    resolve_track_b(db, u.id, t.id, "Ezhel", lfm, CFG, NOW)
    assert db.get(UserTrackArtist, (u.id, t.id)).artist_id == existing.id


def test_low_confidence_is_tier_c(db):
    u, t = setup(db, "ZZB000000003", ["ezhel"], "b3@example.com")
    other = "Zzz Unrelated Act"  # geliştirme verisinde bulunmayan ad
    lfm = FakeLfm({"ezhel": LfmArtist(other, None)})
    assert resolve_track_b(db, u.id, t.id, "ezhel", lfm, CFG, NOW) == "empty"
    assert db.get(UserTrackArtist, (u.id, t.id)) is None
    assert db.get(FetchLog, ("lastfm", f"track:{t.id}")).status == "empty"
    assert not db.scalar(select(func.count()).select_from(Artist).where(Artist.name == other))


def test_not_found_and_error(db):
    u, t = setup(db, "ZZB000000004", ["yok"], "b4@example.com")
    assert resolve_track_b(db, u.id, t.id, "yok", FakeLfm({}), CFG, NOW) == "empty"
    lfm = FakeLfm({"yok": SourceError("429")})
    assert resolve_track_b(db, u.id, t.id, "yok", lfm, CFG, NOW) == "error"
    assert db.get(FetchLog, ("lastfm", f"track:{t.id}")).status == "error"


def test_pending_only_after_tier_a_empty_and_respects_cache(db):
    u, t = setup(db, "ZZB000000005", ["ezhel"], "b5@example.com")
    lfm = FakeLfm({"ezhel": LfmArtist("Ezhel", None)})
    # Kademe A çalışmadan B aday görmez
    resolve_pending_b(db, lfm, CFG, limit=100000, now=NOW)
    assert "ezhel" not in lfm.calls
    mb_empty(db)
    c = resolve_pending_b(db, lfm, CFG, limit=100000, now=NOW)
    assert c["linked"] >= 1 and "ezhel" in lfm.calls
    lfm.calls.clear()
    resolve_pending_b(db, lfm, CFG, limit=100000, now=NOW)
    assert "ezhel" not in lfm.calls  # zaten bağlı


def test_pending_skips_expired_meta_and_negative_cache(db):
    u, t = setup(db, "ZZB000000006", ["yok"], "b6@example.com")
    mb_empty(db)
    lfm = FakeLfm({})
    resolve_pending_b(db, lfm, CFG, limit=100000, now=NOW)
    assert lfm.calls.count("yok") == 1
    resolve_pending_b(db, lfm, CFG, limit=100000, now=NOW + timedelta(minutes=1))
    assert lfm.calls.count("yok") == 1  # negatif önbellek
    # süresi dolmuş kullanıcı önbelleği kullanılmaz
    later = NOW + timedelta(seconds=CFG.fetch_empty_ttl_seconds + 7200)
    resolve_pending_b(db, lfm, CFG, limit=100000, now=later)
    assert lfm.calls.count("yok") == 1


def test_spotify_strings_never_reach_shared_tables(db):
    u, t = setup(db, "ZZB000000007", ["SPOTIFY-SANATCI"], "b7@example.com")
    lfm = FakeLfm({"SPOTIFY-SANATCI": LfmArtist("Kanonik Ad", None)})
    resolve_track_b(db, u.id, t.id, "SPOTIFY-SANATCI", lfm, CFG, NOW)
    db.flush()
    bad = ("SPOTIFY-SANATCI", "SPOTIFY-BASLIK", "spotify sanatci")
    assert not db.scalar(
        select(func.count()).select_from(Artist)
        .where(Artist.name.in_(bad) | Artist.name_norm.in_(bad))
    )
    assert not db.scalar(
        select(func.count()).select_from(ArtistRef).where(ArtistRef.provider_id.in_(bad))
    )
    assert not db.scalar(select(func.count()).select_from(FetchLog).where(FetchLog.key.in_(bad)))
    # Negatif yol da Spotify dizesi yazmaz
    u2, t2 = setup(db, "ZZB000000008", ["SPOTIFY-SANATCI"], "b8@example.com")
    resolve_track_b(db, u2.id, t2.id, "SPOTIFY-SANATCI", FakeLfm({}), CFG, NOW)
    keys = db.scalars(select(FetchLog.key).where(FetchLog.source == "lastfm")).all()
    assert all(k.startswith("track:") for k in keys)


def test_user_delete_cascades_tier_b_link(db):
    u, t = setup(db, "ZZB000000009", ["ezhel"], "b9@example.com")
    resolve_track_b(db, u.id, t.id, "ezhel", FakeLfm({"ezhel": LfmArtist("Ezhel", None)}), CFG, NOW)
    db.flush()
    db.delete(u)
    db.flush()
    assert db.get(UserTrackArtist, (u.id, t.id)) is None
