import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.spotify import oauth
from app.config import Settings, get_settings
from app.connect import get_http
from app.deps import get_db
from app.main import app
from app.models import ServiceConnection
from app.security import decrypt_value

KEY = Fernet.generate_key().decode()


def test_pkce_challenge_matches_verifier():
    verifier, challenge = oauth.make_pkce()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert challenge == expected.rstrip(b"=").decode()
    assert oauth.make_pkce()[0] != verifier


def test_authorize_url_has_pkce_params():
    url = oauth.build_authorize_url("cid", "http://x/cb", "a b", "st", "ch")
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] == ["ch"]
    assert q["state"] == ["st"] and q["scope"] == ["a b"] and "client_secret" not in q


def _spotify_mock(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/token":
        form = parse_qs(request.content.decode())
        assert form["code_verifier"] and form["client_id"] == ["cid"]
        return httpx.Response(
            200,
            json={"access_token": "AT", "refresh_token": "RT", "expires_in": 3600, "scope": "s"},
        )
    if request.url.path == "/v1/me":
        return httpx.Response(200, json={"id": "spotify-user-1"})
    return httpx.Response(404)


@pytest.fixture
def client(test_engine):
    engine = test_engine
    try:
        conn = engine.connect()
    except Exception:
        pytest.skip("PostgreSQL erişilemiyor")
    trans = conn.begin()
    db = Session(bind=conn, join_transaction_mode="create_savepoint")
    mock = httpx.Client(transport=httpx.MockTransport(_spotify_mock))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_http] = lambda: mock
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, spotify_client_id="cid", credential_key=KEY
    )
    yield TestClient(app), db
    app.dependency_overrides.clear()
    db.close()
    trans.rollback()
    conn.close()


def _login(c):
    r = c.post("/auth/register", json={"email": "s@example.com", "password": "uzun-parola-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_full_connect_flow_stores_encrypted_tokens(client, monkeypatch):
    c, db = client
    monkeypatch.setattr("app.connect.get_settings", app.dependency_overrides[get_settings])
    monkeypatch.setattr("app.auth.get_settings", app.dependency_overrides[get_settings])
    h = _login(c)
    url = c.post("/connect/spotify/start", headers=h).json()["authorize_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    r = c.get("/connect/spotify/callback", params={"code": "abc", "state": state})
    assert r.status_code == 200

    conn = db.scalars(
        select(ServiceConnection).where(ServiceConnection.external_user_id == "spotify-user-1")
    ).one()
    assert conn.external_user_id == "spotify-user-1"
    assert conn.access_token_enc != b"AT" and decrypt_value(KEY, conn.access_token_enc) == "AT"
    assert decrypt_value(KEY, conn.refresh_token_enc) == "RT"
    assert c.get("/connections", headers=h).json() == [
        {"service": "spotify", "external_user_id": "spotify-user-1"}
    ]
    # state tek kullanımlık
    again = c.get("/connect/spotify/callback", params={"code": "abc", "state": state})
    assert again.status_code == 400


def test_callback_unregistered_user_gets_clear_403_and_logged_reason(client, monkeypatch, caplog):
    c, _ = client
    monkeypatch.setattr("app.connect.get_settings", app.dependency_overrides[get_settings])
    monkeypatch.setattr("app.auth.get_settings", app.dependency_overrides[get_settings])

    def forbidden_me(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/me":
            return httpx.Response(403, text="User not registered in the Developer Dashboard")
        return _spotify_mock(request)

    app.dependency_overrides[get_http] = lambda: httpx.Client(
        transport=httpx.MockTransport(forbidden_me)
    )
    h = _login(c)
    url = c.post("/connect/spotify/start", headers=h).json()["authorize_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    with caplog.at_level("WARNING", logger="tini.connect"):
        r = c.get("/connect/spotify/callback", params={"code": "abc", "state": state})
    assert r.status_code == 403 and "test listesinde değil" in r.json()["detail"]
    assert "403" in caplog.text and "not registered" in caplog.text
    assert "AT" not in caplog.text.replace("WARNING", "")  # token günlüğe sızmaz


def test_callback_rejects_unknown_state(client):
    c, _ = client
    r = c.get("/connect/spotify/callback", params={"code": "x", "state": "yok"})
    assert r.status_code == 400


def test_start_requires_login_and_config(client, monkeypatch):
    c, _ = client
    assert c.post("/connect/spotify/start").status_code == 401
