from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_db
from app.graph.service import clear_cache
from app.main import app
from app.models import Artist, ArtistEdge, GraphSnapshot, Track, User, UserTrackLink

NOW = datetime(2026, 10, 31, tzinfo=UTC)


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


def edge(a, b, w=0.9):
    return ArtistEdge(src=a.id, dst=b.id, source="lastfm", weight=w, fetched_at=NOW,
                      expires_at=NOW + timedelta(days=1))


def test_candidates_404_without_profile(client, db):
    h = register(client, "r0@example.com")
    assert client.get("/recommend/candidates", headers=h).status_code == 404


def test_candidates_with_reasons_and_known_excluded(client, db):
    h = register(client, "r1@example.com")
    seed, cand, voted = (mk_artist(db, n) for n in ("RSeed", "RCand", "RVoted"))
    db.add_all([edge(seed, cand), edge(seed, voted)])
    db.add(GraphSnapshot(edge_count=2, params={}))
    db.flush()
    t1 = library_track(db, "r1@example.com", "ZZR000000001", seed)
    t2 = library_track(db, "r1@example.com", "ZZR000000002", voted)
    client.post("/votes", json={"track": t1.id, "vote": 6}, headers=h)
    client.post("/votes", json={"track": t2.id, "vote": 4}, headers=h)
    client.post("/profile/rebuild", headers=h)

    body = client.get("/recommend/candidates", headers=h).json()
    got = {c["artist_id"]: c for c in body["candidates"]}
    assert cand.id in got and voted.id not in got and seed.id not in got
    reasons = got[cand.id]["reasons"]  # Good oylu RVoted da tohum; çapa boost'u ilk sırada
    assert reasons[0]["seed_id"] == seed.id and reasons[0]["seed_name"] == "RSeed"
    assert reasons[0]["is_anchor"] and not reasons[1]["is_anchor"]
    assert sum(r["share"] for r in reasons) == pytest.approx(1.0, abs=1e-3)
    assert got[cand.id]["name"] == "RCand"
    assert body["algo_version"] == "recommend-1" and body["profile_version"] == 1
    assert body["graph_version"] == db.scalar(select(GraphSnapshot.version).order_by(
        GraphSnapshot.version.desc()).limit(1))
