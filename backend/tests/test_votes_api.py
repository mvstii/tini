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
    assert body["algo_version"] == "profile-4"
    assert [(v["track"], v["vote"], v["score"]) for v in body["votes"]] == [(t.id, 2, -0.6)]


def test_current_is_per_user(client, db):
    h1, _, t = setup_user(db, client)
    client.post("/votes", json={"track": t.id, "vote": 5}, headers=h1)
    r = client.post("/auth/register", json={"email": "o@example.com", "password": "uzun-parola-1"})
    h2 = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/votes/current", headers=h2).json()["votes"] == []


def test_unheard_requires_owned_track_and_auth(client, db):
    h, _, t = setup_user(db, client)
    assert client.post("/votes/unheard", json={"track": t.id}).status_code == 401
    assert client.post("/votes/unheard", json={"track": t.id + 999}, headers=h).status_code == 404


def test_unheard_appends_events_and_expires_after_n(client, db):
    from app.models import UnheardEvent

    h, u, t = setup_user(db, client)
    got = [client.post("/votes/unheard", json={"track": t.id}, headers=h).json() for _ in range(3)]
    assert [(g["state"], g["presentations"]) for g in got] == [
        ("pooled", 1), ("presented", 2), ("expired", 3)
    ]
    assert len(db.scalars(select(UnheardEvent).where(UnheardEvent.user_id == u.id)).all()) == 3


def test_unheard_event_update_is_blocked(client, db):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    h, _, t = setup_user(db, client)
    client.post("/votes/unheard", json={"track": t.id}, headers=h)
    with pytest.raises(DBAPIError):
        with db.begin_nested():
            db.execute(text("UPDATE unheard_event SET state='expired'"))


def test_expired_unheard_enters_profile_as_weak_negative(client, db):
    h, _, t = setup_user(db, client)
    for _ in range(3):
        client.post("/votes/unheard", json={"track": t.id}, headers=h)
    # artist çözülmemiş parça profile girmez ama oy sayısına yansır
    body = client.post("/profile/rebuild", headers=h).json()
    assert body["algo_version"] == "profile-4" and body["vote_count"] == 1


def test_vote_after_unheard_removes_track_from_pool(client, db):
    h, _, t = setup_user(db, client)
    for _ in range(3):
        client.post("/votes/unheard", json={"track": t.id}, headers=h)
    client.post("/votes", json={"track": t.id, "vote": 5}, headers=h)
    body = client.post("/profile/rebuild", headers=h).json()
    assert body["vote_count"] == 1  # yalnız gerçek oy; örtük negatif eklenmedi


def test_like_enters_profile_as_weak_positive_but_vote_wins(client, db):
    h, _, t = setup_user(db, client)
    assert client.post("/likes", json={"track": t.id}, headers=h).status_code == 201
    body = client.post("/profile/rebuild", headers=h).json()
    assert body["vote_count"] == 1  # beğeni örtük pozitif olarak sayıldı
    client.post("/votes", json={"track": t.id, "vote": 5}, headers=h)
    body = client.post("/profile/rebuild", headers=h).json()
    assert body["vote_count"] == 1  # açık oy varken beğeni ikinci kez sayılmaz
