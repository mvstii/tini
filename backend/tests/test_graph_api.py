from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_db
from app.graph.service import clear_cache
from app.main import app
from app.models import (
    Artist,
    ArtistEdge,
    GraphSnapshot,
    Track,
    User,
    UserTrackArtist,
    UserTrackLink,
    UserTrackMeta,
)

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


@pytest.fixture
def client(db, monkeypatch):
    cfg = Settings(_env_file=None, credential_key=Fernet.generate_key().decode())
    monkeypatch.setattr("app.auth.get_settings", lambda: cfg)
    app.dependency_overrides[get_db] = lambda: db
    clear_cache()
    yield TestClient(app)
    app.dependency_overrides.clear()
    clear_cache()


def login(c, email="g@example.com"):
    r = c.post("/auth/register", json={"email": email, "password": "uzun-parola-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def artist(db, name):
    a = Artist(name=name, name_norm=name.lower())
    db.add(a)
    db.flush()
    return a


def edge(db, s, d, w):
    db.add(
        ArtistEdge(
            src=s.id, dst=d.id, source="lastfm", weight=w, fetched_at=NOW,
            expires_at=NOW + timedelta(days=1),
        )
    )


def world(db, c, email="g@example.com"):
    """Kullanıcı + A→B→C zinciri; parça A'ya bağlı, snapshot yazılı."""
    h = login(c, email)
    u = db.scalar(select(User).where(User.email == email))
    a, b, cc = artist(db, "Aaa"), artist(db, "Bbb"), artist(db, "Ccc")
    edge(db, a, b, 0.9)
    edge(db, b, cc, 0.6)
    t = Track(isrc=f"US{abs(hash(email)) % 10**10:010d}"[:12], artist_id=a.id)
    db.add(t)
    db.flush()
    db.add(UserTrackLink(user_id=u.id, service="spotify", external_id="x1", track_id=t.id))
    db.add(
        UserTrackMeta(
            user_id=u.id, track_id=t.id, title="SPOTIFY-BASLIK", artist_names=["SPOTIFY-SANATCI"],
            duration_ms=1, expires_at=NOW + timedelta(hours=1),
        )
    )
    db.add(GraphSnapshot(edge_count=2, params={}))
    db.flush()
    return h, u, t, (a, b, cc)


def test_requires_auth(client):
    assert client.get("/graph/neighborhood?track=1").status_code == 401


def test_neighborhood_response_shape_and_no_spotify_strings(client, db):
    h, _, t, (a, b, cc) = world(db, client)
    r = client.get(f"/graph/neighborhood?track={t.id}&depth=2", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["algo_version"] == "graph-1" and body["snapshot"] >= 1
    assert body["anchor"] == {"artist_id": a.id, "name": "Aaa"}
    assert [n["name"] for n in body["depth1"]] == ["Bbb"]
    assert [n["name"] for n in body["depth2"]] == ["Ccc"]
    assert body["depth2"][0]["via"]["name"] == "Bbb"
    assert "SPOTIFY" not in r.text


def test_depth1_only(client, db):
    h, _, t, _ = world(db, client)
    body = client.get(f"/graph/neighborhood?track={t.id}&depth=1", headers=h).json()
    assert body["depth2"] == []


def test_other_users_track_is_404(client, db):
    _, _, t, _ = world(db, client)
    h2 = login(client, "other@example.com")
    assert client.get(f"/graph/neighborhood?track={t.id}", headers=h2).status_code == 404


def test_unresolved_track_is_404_and_tier_b_anchor_works(client, db):
    h, u, t, (a, b, cc) = world(db, client)
    t2 = Track(isrc="USZZZ0000001")
    db.add(t2)
    db.flush()
    db.add(UserTrackLink(user_id=u.id, service="spotify", external_id="x2", track_id=t2.id))
    db.flush()
    assert client.get(f"/graph/neighborhood?track={t2.id}", headers=h).status_code == 404
    db.add(UserTrackArtist(user_id=u.id, track_id=t2.id, artist_id=b.id, confidence=0.9,
                           method="name_lastfm"))
    db.flush()
    r = client.get(f"/graph/neighborhood?track={t2.id}&depth=1", headers=h)
    assert r.status_code == 200 and r.json()["anchor"]["name"] == "Bbb"


def test_no_snapshot_is_503(client, db):
    h, _, t, _ = world(db, client)
    db.execute(delete(GraphSnapshot))
    assert client.get(f"/graph/neighborhood?track={t.id}", headers=h).status_code == 503


def test_matrix_is_cached_per_snapshot_version(client, db, monkeypatch):
    h, _, t, _ = world(db, client)
    import app.graph.service as svc

    calls = []
    real = svc.build_matrix
    monkeypatch.setattr(svc, "build_matrix", lambda *a: calls.append(1) or real(*a))
    for _ in range(3):
        assert client.get(f"/graph/neighborhood?track={t.id}", headers=h).status_code == 200
    assert len(calls) == 1
    db.add(GraphSnapshot(edge_count=2, params={}))
    db.flush()
    client.get(f"/graph/neighborhood?track={t.id}", headers=h)
    assert len(calls) == 2
