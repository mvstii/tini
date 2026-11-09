import httpx

from app.sources.http import SourceClient
from app.sources.listenbrainz import (
    ListenBrainzClient,
    parse_metadata,
    parse_radio,
    parse_top_recordings,
)
from app.sources.musicbrainz import MusicBrainzClient

R1, R2, R3 = "r1", "r2", "r3"


def test_parse_radio_accepts_list_and_payload_and_dedups():
    rows = [{"recording_mbid": R1}, {"recording_mbid": R1}, {"recording_mbid": R2}, {"x": 1}]
    assert parse_radio(rows) == [R1, R2]
    assert parse_radio({"payload": rows}) == [R1, R2]
    assert parse_radio({"payload": {"recordings": rows}}) == [R1, R2]
    assert parse_radio("nope") == []
    assert parse_radio(None) == []


def test_parse_top_recordings_sorted_by_listens_and_capped():
    body = [
        {"recording_mbid": R1, "total_listen_count": 5},
        {"recording_mbid": R2, "total_listen_count": 50},
        {"recording_mbid": R3, "total_listen_count": None},
    ]
    assert parse_top_recordings(body, 2) == [(R2, 50), (R1, 5)]


def test_parse_metadata_extracts_isrc_and_primary_artist():
    body = {
        R1: {
            "recording": {"name": "Song", "isrcs": ["TRABC2100001", "bad"]},
            "artist": {"name": "A & B", "artists": [{"artist_mbid": "a1", "name": "A"}]},
        },
        R2: {"recording": {"name": "NoIsrc"}, "artist": {}},
        R3: "garbage",
    }
    out = parse_metadata(body)
    assert out[R1].isrcs == ("TRABC2100001",)
    assert out[R1].artist_mbid == "a1" and out[R1].artist_name == "A & B"
    assert out[R2].isrcs == () and out[R2].artist_mbid is None
    assert R3 not in out


def _lb(handler):
    http = SourceClient(
        httpx.Client(transport=httpx.MockTransport(handler)), user_agent="t",
        min_interval=0.0, max_retries=1, backoff_base=0.0, backoff_max=0.0,
        sleep=lambda s: None,
    )
    return http


def test_client_sends_token_only_where_needed():
    seen = []

    def handler(req):
        seen.append(req)
        if "lb-radio" in req.url.path:
            return httpx.Response(200, json=[{"recording_mbid": R1}])
        if "top-recordings" in req.url.path:
            return httpx.Response(200, json=[{"recording_mbid": R2, "total_listen_count": 3}])
        meta = {R1: {"recording": {"name": "S", "isrcs": ["TRABC2100001"]}}}
        return httpx.Response(200, json=meta)

    lb = ListenBrainzClient(_lb(handler), "https://lb.test/1/", "tok")
    assert lb.radio_tags("rock", 10) == [R1]
    assert lb.top_recordings("a1", 5) == [(R2, 3)]
    assert lb.recordings([R1])[R1].isrcs == ("TRABC2100001",)
    assert lb.recordings([]) == {}
    assert "authorization" not in seen[0].headers
    assert seen[1].headers["authorization"] == "Token tok"
    assert seen[2].method == "POST" and seen[2].headers["authorization"] == "Token tok"


def test_musicbrainz_recording_isrcs_filters_invalid():
    def handler(req):
        return httpx.Response(200, json={"isrcs": ["TRABC2100001", "short"]})

    mb = MusicBrainzClient(_lb(handler), "https://mb.test/ws/2")
    assert mb.recording_isrcs("r1") == ["TRABC2100001"]
