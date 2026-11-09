import httpx
import pytest

from app.config import GraphSettings
from app.sources.http import SourceClient, SourceError
from app.sources.musicbrainz import MusicBrainzClient

A1 = "11111111-1111-1111-1111-111111111111"
R1 = "22222222-2222-2222-2222-222222222222"


def make(handler, *, retries=3, interval=1.0):
    sleeps: list[float] = []
    clock = {"t": 0.0}

    def sleep(s):
        sleeps.append(s)
        clock["t"] += s

    http = SourceClient(
        httpx.Client(transport=httpx.MockTransport(handler)),
        user_agent="Tini/test ( t@example.com )", min_interval=interval,
        max_retries=retries, backoff_base=2.0, backoff_max=60.0,
        sleep=sleep, clock=lambda: clock["t"],
    )
    return http, sleeps


def test_user_agent_required():
    with pytest.raises(ValueError):
        SourceClient(
            httpx.Client(), user_agent="", min_interval=1, max_retries=1,
            backoff_base=1, backoff_max=1,
        )


def test_sends_user_agent_and_rate_limits():
    seen = []

    def handler(req):
        seen.append(req.headers["user-agent"])
        return httpx.Response(200, json={})

    http, sleeps = make(handler)
    http.get_json("https://x/a")
    http.get_json("https://x/b")
    assert seen == ["Tini/test ( t@example.com )"] * 2
    assert sleeps == [1.0]  # ikinci istek ≥1 sn sonra


def test_429_honors_retry_after_then_succeeds():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"ok": True})

    http, sleeps = make(handler)
    assert http.get_json("https://x") == {"ok": True}
    assert 7.0 in sleeps


def test_5xx_exponential_backoff_and_limit():
    def handler(req):
        return httpx.Response(503)

    http, sleeps = make(handler, retries=2, interval=0)
    with pytest.raises(SourceError):
        http.get_json("https://x")
    assert [s for s in sleeps if s] == [2.0, 4.0]


def test_404_returns_none_and_4xx_raises():
    http, _ = make(lambda r: httpx.Response(404))
    assert http.get_json("https://x") is None
    http, _ = make(lambda r: httpx.Response(400))
    with pytest.raises(SourceError):
        http.get_json("https://x")


def test_transport_error_retried():
    n = []

    def handler(req):
        n.append(1)
        if len(n) < 3:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"a": 1})

    http, _ = make(handler, interval=0)
    assert http.get_json("https://x") == {"a": 1}


def test_musicbrainz_lookup_isrc_parses_first_credit():
    body = {
        "recordings": [
            {
                "id": R1,
                "artist-credit": [
                    {"artist": {"id": A1, "name": "Ezhel"}},
                    {"artist": {"id": "33333333-3333-3333-3333-333333333333", "name": "Ceg"}},
                ],
            }
        ]
    }
    paths = []

    def handler(req):
        paths.append((req.url.path, dict(req.url.params)))
        return httpx.Response(200, json=body)

    http, _ = make(handler)
    mb = MusicBrainzClient(http, GraphSettings().musicbrainz_base_url)
    rec = mb.lookup_isrc("TRABC2000001")
    assert str(rec.mbid) == R1
    assert [a.name for a in rec.artists] == ["Ezhel", "Ceg"]
    assert paths[0][0].endswith("/isrc/TRABC2000001")
    assert paths[0][1]["inc"] == "artist-credits"


def test_musicbrainz_unknown_isrc_is_none():
    http, _ = make(lambda r: httpx.Response(404))
    assert MusicBrainzClient(http, "https://mb/ws/2").lookup_isrc("X") is None
    http, _ = make(lambda r: httpx.Response(200, json={"recordings": []}))
    assert MusicBrainzClient(http, "https://mb/ws/2").lookup_isrc("X") is None


def test_post_json_sends_body_and_auth_and_backs_off_on_429():
    seen = []

    def handler(req):
        seen.append(req)
        if len(seen) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, json={"ok": True})

    http, sleeps = make(handler, interval=0.0)
    out = http.post_json(
        "https://x.test/p", {"a": [1]}, headers={"Authorization": "Token t"}
    )
    assert out == {"ok": True}
    assert len(seen) == 2
    assert seen[1].method == "POST"
    assert seen[1].headers["Authorization"] == "Token t"
    assert seen[1].headers["User-Agent"].startswith("Tini/test")
    assert 3.0 in sleeps


def test_post_json_404_returns_none():
    http, _ = make(lambda req: httpx.Response(404), interval=0.0)
    assert http.post_json("https://x.test/p", {}) is None
