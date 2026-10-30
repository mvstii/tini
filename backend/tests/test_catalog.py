import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.names import normalize_name
from app.catalog.resolve import resolve_pending, resolve_track, upsert_artist
from app.config import GraphSettings
from app.db import make_engine
from app.models import Artist, ArtistRef, FetchLog, Track, User, UserTrackMeta
from app.sources.http import SourceError
from app.sources.musicbrainz import MbArtist, MbRecording

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


class FakeMB:
    def __init__(self, table):
        self.table = table
        self.calls = []

    def lookup_isrc(self, isrc):
        self.calls.append(isrc)
        v = self.table.get(isrc)
        if isinstance(v, Exception):
            raise v
        return v


def rec(*artists):
    return MbRecording(uuid.uuid4(), tuple(MbArtist(m, n) for m, n in artists))


def track(db, isrc):
    t = Track(isrc=isrc)
    db.add(t)
    db.flush()
    return t


def test_normalize_name():
    assert normalize_name("  Sezen  Aksu ") == "sezen aksu"
    assert normalize_name("Beyoncé") == "beyonce"
    assert normalize_name("AC/DC") == "ac dc"
    assert normalize_name("Sagopa Kajmer") == normalize_name("sagopa-kajmer")
    assert normalize_name("Işık") == "isık"  # ı korunur, ş→s


def test_tier_a_resolves_and_links_shared_artist(db):
    m = uuid.uuid4()
    t = track(db, "ZZCAT0000001")
    mb = FakeMB({t.isrc: rec((m, "Ezhel"))})
    assert resolve_track(db, t, mb, CFG, NOW) == "ok"
    a = db.get(Artist, t.artist_id)
    assert (a.mbid, a.name, a.name_norm) == (m, "Ezhel", "ezhel")
    ref = db.scalars(select(ArtistRef).where(ArtistRef.artist_id == a.id)).one()
    assert (ref.provider, ref.provider_id, ref.match_method) == ("musicbrainz", str(m), "isrc_mb")
    assert ref.confidence == CFG.tier_a_confidence
    assert t.mbid is not None


def test_same_artist_two_tracks_one_row(db):
    m = uuid.uuid4()
    t1, t2 = track(db, "ZZCAT0000002"), track(db, "ZZCAT0000003")
    mb = FakeMB({t1.isrc: rec((m, "Ezhel")), t2.isrc: rec((m, "Ezhel"))})
    resolve_track(db, t1, mb, CFG, NOW)
    resolve_track(db, t2, mb, CFG, NOW)
    assert t1.artist_id == t2.artist_id


def test_conflicting_mbid_same_name_does_not_merge(db):
    m1, m2 = uuid.uuid4(), uuid.uuid4()
    a1 = upsert_artist(db, m1, "UZI")
    a2 = upsert_artist(db, m2, "Uzi")
    assert a1 != a2
    rows = db.scalars(select(Artist).where(Artist.mbid.in_([m1, m2]))).all()
    assert {r.name_norm for r in rows} == {"uzi"}
    assert upsert_artist(db, m1, "UZI") == a1  # aynı MBID tekrar → aynı satır


def test_empty_and_error_are_negatively_cached(db):
    t1, t2 = track(db, "ZZCAT0000004"), track(db, "ZZCAT0000005")
    mb = FakeMB({t2.isrc: SourceError("429")})
    assert resolve_track(db, t1, mb, CFG, NOW) == "empty"
    assert resolve_track(db, t2, mb, CFG, NOW) == "error"
    assert t1.artist_id is None and t2.artist_id is None
    assert resolve_track(db, t1, mb, CFG, NOW + timedelta(hours=1)) == "cached"
    assert mb.calls.count(t1.isrc) == 1
    # hata TTL'i kısa: bir saat sonra yeniden denenir; boş sonuç hâlâ önbellekte
    retry = NOW + timedelta(seconds=CFG.fetch_error_ttl_seconds + 1)
    assert resolve_track(db, t2, mb, CFG, retry) == "error"
    assert mb.calls.count(t2.isrc) == 2
    later = NOW + timedelta(seconds=CFG.fetch_empty_ttl_seconds + 1)
    assert resolve_track(db, t1, mb, CFG, later) == "empty"


def test_resolve_pending_skips_resolved_and_cached(db):
    m = uuid.uuid4()
    done = track(db, "ZZCAT0000006")
    done.artist_id = upsert_artist(db, m, "Eski")
    todo, miss = track(db, "ZZCAT0000007"), track(db, "ZZCAT0000008")
    mb = FakeMB({todo.isrc: rec((uuid.uuid4(), "Yeni"))})
    c1 = resolve_pending(db, mb, CFG, limit=1000, now=NOW)
    assert done.isrc not in mb.calls
    assert {todo.isrc, miss.isrc} <= set(mb.calls)
    assert c1["ok"] >= 1 and c1["empty"] >= 1
    mb.calls.clear()
    resolve_pending(db, mb, CFG, limit=1000, now=NOW)
    assert todo.isrc not in mb.calls and miss.isrc not in mb.calls  # negatif önbellek


def test_shared_tables_never_contain_spotify_strings(db):
    u = User(email="cat@example.com", password_hash="x")
    db.add(u)
    db.flush()
    t = track(db, "ZZCAT0000009")
    db.add(
        UserTrackMeta(
            user_id=u.id, track_id=t.id, title="SPOTIFY-BASLIK",
            artist_names=["SPOTIFY-SANATCI"], duration_ms=1,
            expires_at=NOW + timedelta(hours=1),
        )
    )
    db.flush()
    mb = FakeMB({t.isrc: rec((uuid.uuid4(), "Kanonik Ad"))})
    resolve_track(db, t, mb, CFG, NOW)
    db.flush()
    bad = ("SPOTIFY-BASLIK", "SPOTIFY-SANATCI")
    assert not db.scalar(
        select(func.count())
        .select_from(Artist)
        .where(Artist.name.in_(bad) | Artist.name_norm.in_(bad))
    )
    assert not db.scalar(
        select(func.count()).select_from(ArtistRef).where(ArtistRef.provider_id.in_(bad))
    )
    assert not db.scalar(select(func.count()).select_from(FetchLog).where(FetchLog.key.in_(bad)))
    assert mb.calls == [t.isrc]  # MB'ye yalnızca ISRC gitti
