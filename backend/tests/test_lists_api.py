from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine
from app.deps import get_db
from app.graph.service import clear_cache
from app.main import app
from app.models import Artist, ArtistEdge, GraphSnapshot, Track, User, UserTrackLink

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


def mk_artist(db, name):
    a = Artist(name=name, name_norm=name.lower())
    db.add(a)
    db.flush()
    return a


def library_track(db, email, isrc, artist):
    u = db.scalar(select(User).where(User.email == email))
    t = Track(isrc=isrc, artist_id=artist.id)
    db.add(t)
    db.flush()
    db.add(UserTrackLink(user_id=u.id, service="spotify", external_id=isrc, track_id=t.id))
    db.flush()
    return t


def edge(a, b, w=0.9):
    return ArtistEdge(src=a.id, dst=b.id, source="lastfm", weight=w, fetched_at=NOW,
                      expires_at=NOW + timedelta(days=1))


def setup_user(client, db, email, tag):
    h = register(client, email)
    seed, c1, c2 = (mk_artist(db, f"{tag}{n}") for n in ("Seed", "A", "B"))
    db.add_all([edge(seed, c1), edge(seed, c2)])
    db.add(GraphSnapshot(edge_count=2, params={}))
    db.flush()
    t = library_track(db, email, f"ZZ{tag}00000001", seed)
    client.post("/votes", json={"track": t.id, "vote": 6}, headers=h)
    client.post("/profile/rebuild", headers=h)
    return h, seed, c1, c2


def test_generate_requires_profile(client, db):
    h = register(client, "l0@example.com")
    assert client.post("/lists/generate", headers=h).status_code == 404


def test_generate_persists_list_with_reasons_and_track(client, db):
    h, seed, c1, c2 = setup_user(client, db, "l1@example.com", "LA")
    shared = Track(isrc="ZZLA00000099", artist_id=c1.id)
    db.add(shared)
    db.flush()

    r = client.post("/lists/generate", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["algo_version"] == "list-1" and body["profile_version"] == 1
    items = {i["artist_id"]: i for i in body["items"]}
    assert set(items) == {c1.id, c2.id}
    assert [i["position"] for i in body["items"]] == [1, 2]
    assert items[c1.id]["track_id"] == shared.id and items[c2.id]["track_id"] is None
    assert items[c1.id]["reasons"][0]["seed_name"] == "LASeed"
    assert items[c1.id]["reasons"][0]["is_anchor"]

    again = client.get(f"/lists/{body['id']}", headers=h).json()
    assert again == body


def test_list_is_private_to_owner(client, db):
    h1, *_ = setup_user(client, db, "l2@example.com", "LB")
    lid = client.post("/lists/generate", headers=h1).json()["id"]
    h2 = register(client, "l3@example.com")
    assert client.get(f"/lists/{lid}", headers=h2).status_code == 404


def test_item_feedback_is_recorded_as_event(client, db):
    from app.models import ListFeedback

    h, seed, c1, c2 = setup_user(client, db, "l4@example.com", "LC")
    lst = client.post("/lists/generate", headers=h).json()
    url = f"/lists/{lst['id']}/items/1/feedback"

    r = client.post(url, json={"seed_id": seed.id}, headers=h)
    assert r.status_code == 201 and r.json()["kind"] == "wrong_reason"
    assert client.post(url, json={}, headers=h).status_code == 201  # tüm gerekçe, ikinci olay
    rows = db.scalars(select(ListFeedback).where(ListFeedback.list_id == lst["id"])).all()
    assert [(f.position, f.seed_id) for f in rows] == [(1, seed.id), (1, None)]


def test_item_feedback_validation_and_privacy(client, db):
    h1, seed, c1, c2 = setup_user(client, db, "l5@example.com", "LD")
    lid = client.post("/lists/generate", headers=h1).json()["id"]
    assert client.post(f"/lists/{lid}/items/99/feedback", json={}, headers=h1).status_code == 404
    bad = client.post(f"/lists/{lid}/items/1/feedback", json={"seed_id": c2.id}, headers=h1)
    assert bad.status_code == 422
    assert client.post(
        f"/lists/{lid}/items/1/feedback", json={"kind": "x"}, headers=h1
    ).status_code == 422

    h2 = register(client, "l6@example.com")
    assert client.post(f"/lists/{lid}/items/1/feedback", json={}, headers=h2).status_code == 404
