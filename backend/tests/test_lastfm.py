import uuid

import httpx
import pytest

from app.catalog.confidence import name_match_confidence
from app.config import GraphSettings
from app.sources.http import SourceClient, SourceError
from app.sources.lastfm import LastfmClient

CFG = GraphSettings()
M = "44444444-4444-4444-4444-444444444444"


def client(handler, key="K"):
    http = SourceClient(
        httpx.Client(transport=httpx.MockTransport(handler)),
        user_agent="Tini/test ( t )", min_interval=0, max_retries=1,
        backoff_base=0, backoff_max=0, sleep=lambda s: None,
    )
    return LastfmClient(http, "https://lfm/2.0/", key)


def test_api_key_required():
    with pytest.raises(ValueError):
        client(lambda r: httpx.Response(200, json={}), key="")


def test_get_info_by_name_and_params():
    seen = {}

    def handler(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json={"artist": {"name": "Sezen Aksu", "mbid": M}})

    a = client(handler).get_info(name="sezen aksu")
    assert (a.name, str(a.mbid)) == ("Sezen Aksu", M)
    assert seen["method"] == "artist.getInfo" and seen["artist"] == "sezen aksu"
    assert seen["autocorrect"] == "1" and "mbid" not in seen


def test_get_info_by_mbid_prefers_mbid():
    seen = {}

    def handler(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json={"artist": {"name": "X", "mbid": ""}})

    a = client(handler).get_info(name="x", mbid=uuid.UUID(M))
    assert a.mbid is None  # boş mbid → None
    assert seen["mbid"] == M and "artist" not in seen


def test_not_found_error_6_is_none_other_errors_raise():
    c = client(lambda r: httpx.Response(200, json={"error": 6, "message": "nf"}))
    assert c.get_info(name="yok") is None
    c = client(lambda r: httpx.Response(200, json={"error": 29, "message": "rate"}))
    with pytest.raises(SourceError):
        c.get_info(name="x")


def test_get_similar_parses_and_skips_malformed():
    body = {
        "similarartists": {
            "artist": [
                {"name": "A", "mbid": M, "match": "0.9"},
                {"name": "B", "mbid": "", "match": "0.5"},
                {"name": "C"},  # match yok → atlanır
            ]
        }
    }
    out = client(lambda r: httpx.Response(200, json=body)).get_similar(name="x", limit=5)
    assert [(s.name, s.match) for s in out] == [("A", 0.9), ("B", 0.5)]
    assert out[1].mbid is None


def test_name_match_confidence():
    exact = name_match_confidence("ezhel", "ezhel", False, CFG)
    assert exact == CFG.tier_b_exact_confidence
    assert name_match_confidence("ezhel", "ezhel", True, CFG) == min(
        1.0, exact + CFG.tier_b_mbid_bonus
    )
    close = name_match_confidence("sezen aksu", "sezen aksu band", False, CFG)
    far = name_match_confidence("ezhel", "metallica", False, CFG)
    assert far < close < exact
    assert far < CFG.tier_b_min_confidence
    assert name_match_confidence("", "x", True, CFG) == 0.0
