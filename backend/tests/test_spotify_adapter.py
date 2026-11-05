from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet

from app import connections
from app.adapters.spotify.client import SpotifyAdapter
from app.config import Settings
from app.models import ServiceConnection
from app.security import decrypt_value, encrypt_value


def _track(i, isrc="USAAA0000001", name="Sarki", artists=("Sanatci",)):
    return {
        "id": f"id{i}",
        "name": name,
        "duration_ms": 1000,
        "external_ids": {"isrc": isrc} if isrc else {},
        "artists": [{"name": a} for a in artists],
    }


def _adapter(handler, sleeps=None):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    sleep = sleeps.append if sleeps is not None else (lambda s: None)
    return SpotifyAdapter(http, "AT", sleep=sleep)


def test_read_library_dedups_and_flags_bad_records():
    def handler(req):
        if req.url.path == "/v1/me/tracks":
            items = [
                {"track": _track(1)},
                {"track": _track(2, isrc=None)},  # ISRC yok -> atlanır
                {"track": _track(3, name="")},  # boş metadata -> atlanır
                {"track": _track(4, artists=())},  # sanatçı yok -> atlanır
            ]
            return httpx.Response(200, json={"items": items, "next": None})
        return httpx.Response(200, json={"items": [_track(1), _track(5, isrc="usbbb0000002")]})

    lib = _adapter(handler).read_library()
    assert [t.external_id for t in lib.tracks] == ["id1", "id5"]
    assert lib.tracks[1].isrc == "USBBB0000002"
    assert lib.skipped == 3


def test_pagination_follows_next_until_limit():
    calls = []

    def handler(req):
        if req.url.path == "/v1/me/tracks":
            off = int(req.url.params["offset"])
            calls.append(off)
            return httpx.Response(
                200, json={"items": [{"track": _track(off + 1)}], "next": "x"}
            )
        return httpx.Response(200, json={"items": []})

    _adapter(handler).read_library(max_tracks=150)
    assert calls == [0, 50, 100]


def test_retries_on_429_with_retry_after():
    state = {"n": 0}
    sleeps = []

    def handler(req):
        state["n"] += 1
        if state["n"] <= 2:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, json={"items": []})

    _adapter(handler, sleeps).read_library()
    assert sleeps[:2] == [3, 3]


def test_gives_up_after_max_retries():
    def handler(req):
        return httpx.Response(429, headers={"Retry-After": "1"})

    with pytest.raises(httpx.HTTPStatusError):
        _adapter(handler).read_library()


def test_create_playlist_uses_items_endpoint_in_chunks():
    posted = []

    def handler(req):
        if req.url.path == "/v1/me/playlists":
            return httpx.Response(201, json={"id": "pl1"})
        posted.append((req.url.path, len(req.read().decode().split("spotify:track:")) - 1))
        return httpx.Response(201, json={})

    pid = _adapter(handler).create_playlist("Tini", [f"t{i}" for i in range(150)])
    assert pid == "pl1"
    assert posted == [("/v1/playlists/pl1/items", 100), ("/v1/playlists/pl1/items", 50)]


KEY = Fernet.generate_key().decode()


def _conn(expires_in):
    return ServiceConnection(
        service="spotify",
        access_token_enc=encrypt_value(KEY, "OLD"),
        refresh_token_enc=encrypt_value(KEY, "RT"),
        expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
    )


class _Db:
    commits = 0

    def commit(self):
        self.commits += 1


def test_valid_token_not_refreshed(monkeypatch):
    cfg = Settings(_env_file=None, credential_key=KEY)
    monkeypatch.setattr(connections, "get_settings", lambda: cfg)
    http = httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail("çağrılmamalı")))
    assert connections.valid_access_value(_Db(), _conn(3600), http) == "OLD"


def test_expired_token_refreshed_and_stored_encrypted(monkeypatch):
    cfg = Settings(_env_file=None, credential_key=KEY, spotify_client_id="cid")
    monkeypatch.setattr(connections, "get_settings", lambda: cfg)
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"access_token": "NEW", "expires_in": 3600})
        )
    )
    conn, db = _conn(-10), _Db()
    assert connections.valid_access_value(db, conn, http) == "NEW"
    assert decrypt_value(KEY, conn.access_token_enc) == "NEW"
    assert decrypt_value(KEY, conn.refresh_token_enc) == "RT"  # yanıtta yoksa eskisi kalır
    assert db.commits == 1


def test_open_url_resolves_isrc_to_track_uri():
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json={"tracks": {"items": [{"id": "abc123"}]}})

    assert _adapter(handler).open_url("USAAA0000001", "X") == ("track", "spotify:track:abc123")
    assert seen == [{"q": "isrc:USAAA0000001", "type": "track", "limit": "1"}]


def test_open_url_falls_back_to_artist_search():
    empty = _adapter(lambda r: httpx.Response(200, json={"tracks": {"items": []}}))
    assert empty.open_url("USAAA0000001", "Tyler, The Creator") == (
        "search", "spotify:search:Tyler%2C%20The%20Creator")
    assert empty.open_url(None, "Drake") == ("search", "spotify:search:Drake")


def test_open_url_with_hint_searches_artist_and_title_instead_of_random_track():
    def handler(req):
        raise AssertionError("ISRC yok ve ipucu var: sanatçı parçası aranmamalı")

    a = _adapter(handler)
    assert a.open_url(None, "Drake", "Views") == ("search", "spotify:search:Drake%20Views")


def test_find_artist_track_requires_matching_artist_name():
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        items = [
            {"id": "X1", "artists": [{"name": "Baska"}]},
            {"id": "X2", "artists": [{"name": "Feat"}, {"name": "DRAKE"}]},
        ]
        return httpx.Response(200, json={"tracks": {"items": items}})

    a = _adapter(handler)
    assert a.find_artist_track("Drake") == "X2"
    assert seen[0]["q"] == 'artist:"Drake"' and seen[0]["type"] == "track"
    assert a.find_artist_track("Kimse") is None
    assert a.find_artist_track("") is None
    assert a.open_url(None, "Drake") == ("track", "spotify:track:X2")


def test_find_artist_track_folds_dollar_and_punctuation():
    def handler(req):
        items = [{"id": "T1", "artists": [{"name": "Travis Scott"}]}]
        return httpx.Response(200, json={"tracks": {"items": items}})

    a = _adapter(handler)
    assert a.find_artist_track("Travi$ Scott") == "T1"
    assert a.find_artist_track("TRAVIS  SCOTT.") == "T1"


def test_find_artist_track_scans_later_pages_for_short_names():
    offsets = []

    def handler(req):
        off = int(req.url.params["offset"])
        offsets.append(off)
        if off == 10:
            items = [{"id": "N1", "artists": [{"name": "NAV"}]}]
        else:
            items = [{"id": f"x{off}{i}", "artists": [{"name": "NAVAI"}]} for i in range(10)]
        return httpx.Response(200, json={"tracks": {"items": items}})

    a = _adapter(handler)
    assert a.find_artist_track("NAV") == "N1"
    assert offsets == [0, 10]


def test_find_artist_track_gives_up_after_page_limit_or_empty_page():
    offsets = []
    empty = False

    def handler(req):
        offsets.append(int(req.url.params["offset"]))
        n = 0 if empty else 5  # canlıda sayfa limitten kısa döner
        items = [{"id": f"x{i}", "artists": [{"name": "Baska"}]} for i in range(n)]
        return httpx.Response(200, json={"tracks": {"items": items}})

    a = _adapter(handler)
    assert a.find_artist_track("Kimse") is None
    assert offsets == [0, 10, 20]
    offsets.clear()
    empty = True
    assert a.find_artist_track("Kimse") is None
    assert offsets == [0]
