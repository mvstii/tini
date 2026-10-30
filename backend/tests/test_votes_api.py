import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine
from app.deps import get_db
from app.main import app
from app.models import Track, User, UserTrackLink, VoteEvent


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
    yield TestClient(app)
    app.dependency_overrides.clear()


def setup_user(db, c, email="v@example.com"):
    r = c.post("/auth/register", json={"email": email, "password": "uzun-parola-1"})
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    u = db.scalar(select(User).where(User.email == email))
    t = Track(isrc="TRTEST000001")
    db.add(t)
    db.flush()
    db.add(UserTrackLink(user_id=u.id, service="spotify", external_id="x1", track_id=t.id))
    db.flush()
    return h, u, t


def test_vote_requires_auth(client):
    assert client.post("/votes", json={"track": 1, "vote": 4}).status_code in (401, 403)


def test_vote_unknown_track_404(client, db):
    h, _, _ = setup_user(db, client)
    assert client.post("/votes", json={"track": 999999999, "vote": 4}, headers=h).status_code == 404


@pytest.mark.parametrize("vote", [0, 7])
def test_vote_out_of_range_422(client, db, vote):
    h, _, t = setup_user(db, client)
    assert client.post("/votes", json={"track": t.id, "vote": vote}, headers=h).status_code == 422


def test_revote_appends_event_and_current_is_last(client, db):
    h, u, t = setup_user(db, client)
    assert client.post("/votes", json={"track": t.id, "vote": 6}, headers=h).status_code == 201
    assert client.post("/votes", json={"track": t.id, "vote": 2}, headers=h).status_code == 201
    events = db.scalars(select(VoteEvent).where(VoteEvent.user_id == u.id)).all()
    assert len(events) == 2  # silinmez, yeni olay eklenir
    body = client.get("/votes/current", headers=h).json()
    assert body["algo_version"] == "profile-1"
    assert [(v["track"], v["vote"], v["score"]) for v in body["votes"]] == [(t.id, 2, -0.6)]


def test_current_is_per_user(client, db):
    h1, _, t = setup_user(db, client)
    client.post("/votes", json={"track": t.id, "vote": 5}, headers=h1)
    r = client.post("/auth/register", json={"email": "o@example.com", "password": "uzun-parola-1"})
    h2 = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/votes/current", headers=h2).json()["votes"] == []
