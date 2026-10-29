from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import connections
from app import library as lib_mod
from app.adapters.base import Library, LibraryTrack
from app.config import Settings
from app.connect import get_http
from app.db import make_engine
from app.deps import get_db
from app.library import store_library
from app.main import app
from app.models import ServiceConnection, Track, UserTrackLink, UserTrackMeta
from app.security import encrypt_value

KEY = Fernet.generate_key().decode()
TTL = timedelta(hours=24)


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


def _user(db):
    from app.models import User

    u = User(email="lib@example.com", password_hash="x")
    db.add(u)
    db.flush()
    return u


def _lib():
    return Library(
        tracks=[
            LibraryTrack("a1", "ZZTEST000001", "Bir", ("X",), 1000),
            LibraryTrack("a2", "ZZTEST000002", "Iki", ("Y", "Z"), None),
            LibraryTrack("a3", "ZZTEST000001", "Bir (yeniden)", ("X",), 1000),  # aynı ISRC
        ],
        skipped=2,
    )


def test_store_library_writes_catalog_links_and_meta(db):
    u = _user(db)
    n = store_library(db, u.id, "spotify", _lib(), TTL)
    assert n == 2
    isrcs = db.scalars(select(Track.isrc).where(Track.isrc.like("ZZTEST%"))).all()
    assert sorted(isrcs) == ["ZZTEST000001", "ZZTEST000002"]
    assert db.scalar(select(func.count()).select_from(UserTrackLink)) >= 3
    meta = db.scalars(select(UserTrackMeta).where(UserTrackMeta.user_id == u.id)).all()
    assert len(meta) == 2
    assert all(m.expires_at - m.fetched_at == TTL for m in meta)
    # Paylaşılan katalogda başlık/sanatçı alanı yok
    assert not hasattr(Track, "title") and not hasattr(Track, "artist_names")


def test_store_library_is_idempotent_and_refreshes_meta(db):
    u = _user(db)
    store_library(db, u.id, "spotify", _lib(), TTL)
    changed = Library(tracks=[LibraryTrack("a1", "ZZTEST000001", "Yeni ad", ("X",), 5)])
    store_library(db, u.id, "spotify", changed, TTL)
    assert db.scalar(
        select(func.count()).select_from(Track).where(Track.isrc == "ZZTEST000001")
    ) == 1
    titles = db.scalars(
        select(UserTrackMeta.title).where(UserTrackMeta.user_id == u.id)
    ).all()
    assert "Yeni ad" in titles
    links = db.scalars(select(UserTrackLink).where(UserTrackLink.user_id == u.id)).all()
    assert len(links) == 3


def test_store_empty_library_noop(db):
    u = _user(db)
    assert store_library(db, u.id, "spotify", Library(), TTL) == 0


def _spotify(request: httpx.Request) -> httpx.Response:
    track = {
        "id": "sp1", "name": "Sarki", "duration_ms": 1,
        "external_ids": {"isrc": "ZZTEST000009"}, "artists": [{"name": "S"}],
    }
    if request.url.path == "/v1/me/tracks":
        return httpx.Response(200, json={"items": [{"track": track}], "next": None})
    return httpx.Response(200, json={"items": []})


@pytest.fixture
def client(db, monkeypatch):
    cfg = Settings(_env_file=None, credential_key=KEY)
    monkeypatch.setattr(connections, "get_settings", lambda: cfg)
    monkeypatch.setattr(lib_mod, "get_settings", lambda: cfg)
    monkeypatch.setattr("app.auth.get_settings", lambda: cfg)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_http] = lambda: httpx.Client(
        transport=httpx.MockTransport(_spotify)
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login(c):
    r = c.post("/auth/register", json={"email": "ep@example.com", "password": "uzun-parola-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}, r


def test_import_requires_connection_then_imports(client, db):
    h, _ = _login(client)
    assert client.post("/library/import").status_code == 401
    assert client.post("/library/import", headers=h).status_code == 409
    assert client.post("/library/import?service=yok", headers=h).status_code == 400

    from app.models import User

    uid = db.scalars(select(User.id).where(User.email == "ep@example.com")).one()
    db.add(
        ServiceConnection(
            user_id=uid, service="spotify", external_user_id="u",
            access_token_enc=encrypt_value(KEY, "AT"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.flush()
    r = client.post("/library/import", headers=h)
    assert r.status_code == 200 and r.json() == {"imported": 1, "skipped": 0}
    assert db.scalar(select(func.count()).select_from(UserTrackMeta)
                     .where(UserTrackMeta.user_id == uid)) == 1
