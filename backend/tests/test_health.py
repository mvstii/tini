from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.spotify_cache_ttl_seconds == 86400
