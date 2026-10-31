from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine
from app.deps import get_db
from app.graph.service import clear_cache
from app.main import app
from app.models import Artist, ArtistEdge, GraphSnapshot, TasteProfile, Track, User, UserTrackLink

NOW = datetime(2026, 10, 31, tzinfo=UTC)


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


@pytest.fixture
def client(db, monkeypatch):
    cfg = Settings(_env_file=None, credential_key=Fernet.generate_key().decode())
    monkeypatch.setattr("app.auth.get_settings", lambda: cfg)
    app.dependency_overrides[get_db] = lambda: db
    clear_cache()
    yield TestClient(app)
    app.dependency_overrides.clear()
    clear_cache()


def register(c, email):
    r = c.post("/auth/register", json={"email": email, "password": "uzun-parola-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def library_track(db, email, isrc, artist):
    u = db.scalar(select(User).where(User.email == email))
    t = Track(isrc=isrc, artist_id=artist.id)
    db.add(t)
    db.flush()
    db.add(UserTrackLink(user_id=u.id, service="spotify", external_id=isrc, track_id=t.id))
    db.flush()
    return t


def mk_artist(db, name):
    a = Artist(name=name, name_norm=name.lower())
    db.add(a)
    db.flush()
    return a


def test_profile_404_before_rebuild(client, db):
    h = register(client, "p0@example.com")
    assert client.get("/profile", headers=h).status_code == 404


def test_rebuild_versions_and_latest(client, db):
    h = register(client, "p1@example.com")
    a, b = mk_artist(db, "Aaa"), mk_artist(db, "Bbb")
    t1 = library_track(db, "p1@example.com", "ZZP000000001", a)
    t2 = library_track(db, "p1@example.com", "ZZP000000002", b)
    client.post("/votes", json={"track": t1.id, "vote": 6}, headers=h)
    client.post("/votes", json={"track": t2.id, "vote": 1}, headers=h)

    r1 = client.post("/profile/rebuild", headers=h)
    assert r1.status_code == 201 and r1.json()["version"] == 1
    r2 = client.post("/profile/rebuild", headers=h)
    assert r2.json()["version"] == 2
    got = client.get("/profile", headers=h).json()
    assert got["version"] == 2 and got["algo_version"] == "profile-2"
    assert got["graph_version"] == db.scalar(select(func.max(GraphSnapshot.version)))
    assert got["anchors"] == [{"artist_id": a.id, "weight": 1.0}]
    assert got["avoid"] == [{"artist_id": b.id, "strength": 1.0, "hard": True}]
    assert [u["artist_id"] for u in got["unclustered"]] == [a.id]
    assert len(db.scalars(select(TasteProfile).where(TasteProfile.version >= 1)).all()) >= 2


def test_rebuild_records_graph_version(client, db):
    h = register(client, "p2@example.com")
    a, b = mk_artist(db, "Ccc"), mk_artist(db, "Ddd")
    db.add(
        ArtistEdge(src=a.id, dst=b.id, source="lastfm", weight=0.9, fetched_at=NOW,
                   expires_at=NOW + timedelta(days=1))
    )
    snap = GraphSnapshot(edge_count=1, params={})
    db.add(snap)
    db.flush()
    t = library_track(db, "p2@example.com", "ZZP000000003", a)
    client.post("/votes", json={"track": t.id, "vote": 5}, headers=h)
    body = client.post("/profile/rebuild", headers=h).json()
    assert body["graph_version"] == snap.version


def test_profile_is_per_user(client, db):
    h1 = register(client, "p3@example.com")
    h2 = register(client, "p4@example.com")
    client.post("/profile/rebuild", headers=h1)
    assert client.get("/profile", headers=h2).status_code == 404
