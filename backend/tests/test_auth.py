from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import make_engine
from app.deps import get_db
from app.main import app
from app.models import UserSession
from app.security import (
    decrypt_value,
    encrypt_value,
    hash_password,
    new_session_token,
    verify_password,
)

PW = "uzun-bir-parola-1"


@pytest.fixture
def client():
    engine = make_engine()
    try:
        conn = engine.connect()
    except Exception:
        pytest.skip("PostgreSQL erişilemiyor")
    trans = conn.begin()
    db = Session(bind=conn, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
    db.close()
    trans.rollback()
    conn.close()


def _register(c, email="a@example.com"):
    r = c.post("/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_register_login_me(client):
    h = _register(client)
    assert client.get("/me", headers=h).json()["email"] == "a@example.com"
    r = client.post("/auth/login", json={"email": "A@Example.com", "password": PW})
    assert r.status_code == 200


def test_duplicate_email_rejected(client):
    _register(client)
    r = client.post("/auth/register", json={"email": "a@example.com", "password": PW})
    assert r.status_code == 409


def test_wrong_password_and_short_password(client):
    _register(client)
    bad = {"email": "a@example.com", "password": "yanlis-parola"}
    assert client.post("/auth/login", json=bad).status_code == 401
    short = {"email": "b@example.com", "password": "kisa"}
    assert client.post("/auth/register", json=short).status_code == 422


def test_me_requires_valid_session(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer yok"}).status_code == 401


def test_logout_invalidates_session(client):
    h = _register(client)
    assert client.post("/auth/logout", headers=h).status_code == 204
    assert client.get("/me", headers=h).status_code == 401


def test_expired_session_rejected(client):
    h = _register(client)
    db = app.dependency_overrides[get_db]()
    db.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert client.get("/me", headers=h).status_code == 401


def test_password_hash_and_session_digest():
    hashed = hash_password(PW)
    assert hashed != PW and verify_password(hashed, PW) and not verify_password(hashed, "x")
    value, digest = new_session_token()
    assert value != digest and len(digest) == 64


def test_value_encryption_roundtrip():
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    blob = encrypt_value(key, "gizli-deger")
    assert blob != b"gizli-deger" and decrypt_value(key, blob) == "gizli-deger"
