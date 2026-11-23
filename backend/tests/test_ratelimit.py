import itertools
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app, docs_urls
from app.ratelimit import (
    SWEEP_EVERY,
    SlidingWindowLimiter,
    check_media_limit,
    get_auth_limits,
    login_key,
)

PW = "uzun-bir-parola-1"
_emails = itertools.count()


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_blocks_at_limit_and_recovers_after_window():
    clock = FakeClock()
    lim = SlidingWindowLimiter(2, 60, clock)
    assert lim.retry_after("k") is None
    lim.hit("k")
    lim.hit("k")
    assert lim.retry_after("k") == 60
    clock.now += 40
    assert lim.retry_after("k") == 20
    clock.now += 21
    assert lim.retry_after("k") is None


def test_limiter_keys_are_independent_and_reset_works():
    lim = SlidingWindowLimiter(1, 60, FakeClock())
    lim.hit("a")
    assert lim.retry_after("a") is not None
    assert lim.retry_after("b") is None
    lim.reset("a")
    assert lim.retry_after("a") is None


def test_docs_closed_only_in_prod():
    assert docs_urls("prod") == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert docs_urls("dev")["openapi_url"] == "/openapi.json"


@pytest.fixture
def client():
    get_auth_limits().clear()
    yield TestClient(app)
    get_auth_limits().clear()


def _email() -> str:
    return f"rl{next(_emails)}-{uuid.uuid4().hex[:8]}@example.com"


def test_login_locks_after_failures_then_sets_retry_after(client):
    email = _email()
    assert client.post("/auth/register", json={"email": email, "password": PW}).status_code == 201
    limit = get_auth_limits().login_email.limit
    for _ in range(limit):
        r = client.post("/auth/login", json={"email": email, "password": "yanlis-parola-9"})
        assert r.status_code == 401
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_successful_login_resets_email_counter(client):
    email = _email()
    client.post("/auth/register", json={"email": email, "password": PW})
    limit = get_auth_limits().login_email.limit
    for _ in range(limit - 1):
        client.post("/auth/login", json={"email": email, "password": "yanlis-parola-9"})
    assert client.post("/auth/login", json={"email": email, "password": PW}).status_code == 200
    for _ in range(limit - 1):
        r = client.post("/auth/login", json={"email": email, "password": "yanlis-parola-9"})
        assert r.status_code == 401


def test_unknown_email_also_counts(client):
    email = _email()
    limit = get_auth_limits().login_email.limit
    for _ in range(limit):
        assert client.post(
            "/auth/login", json={"email": email, "password": PW}
        ).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": PW}).status_code == 429


def test_register_limited_per_ip(client):
    limit = get_auth_limits().register_ip.limit
    for _ in range(limit):
        r = client.post("/auth/register", json={"email": _email(), "password": PW})
        assert r.status_code == 201
    r = client.post("/auth/register", json={"email": _email(), "password": PW})
    assert r.status_code == 429


def test_sweep_drops_stale_keys():
    clock = FakeClock()
    lim = SlidingWindowLimiter(5, 60, clock)
    for i in range(10):
        lim.hit(f"k{i}")
    clock.now += 61
    lim.sweep()
    assert lim._hits == {}


def test_hit_sweeps_automatically():
    clock = FakeClock()
    lim = SlidingWindowLimiter(10**6, 60, clock)
    for i in range(50):
        lim.hit(f"old{i}")
    clock.now += 61
    for _ in range(SWEEP_EVERY):
        lim.hit("live")
    assert set(lim._hits) == {"live"}


def test_media_limit_per_user_then_429():
    lim = SlidingWindowLimiter(2, 60, FakeClock())
    check_media_limit("u1", lim)
    check_media_limit("u1", lim)
    with pytest.raises(HTTPException) as e:
        check_media_limit("u1", lim)
    assert e.value.status_code == 429
    assert int(e.value.headers["Retry-After"]) > 0
    check_media_limit("u2", lim)  # başka kullanıcı etkilenmez


def test_login_key_pairs_email_and_ip():
    assert login_key("a@x.com", "1.1.1.1") != login_key("a@x.com", "2.2.2.2")


def test_other_ip_cannot_lock_victim_email(client):
    email = _email()
    assert client.post("/auth/register", json={"email": email, "password": PW}).status_code == 201
    limits = get_auth_limits()
    for _ in range(limits.login_email.limit):  # saldırganın IP'si kilitlenir
        limits.login_email.hit(login_key(email, "9.9.9.9"))
    assert client.post("/auth/login", json={"email": email, "password": PW}).status_code == 200
