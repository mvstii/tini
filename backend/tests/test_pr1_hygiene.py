import json
import threading
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import db as db_mod
from app.config import GraphSettings
from app.graph.expand import expand
from app.models import Artist, FetchLog
from app.sources.http import SourceClient, SourceError, get_limiter
from app.sources.lastfm import LastfmClient
from app.timing import Stages
from app.upstream import parse_retry_after, upstream_unavailable


# ---- Ortak hız sınırlayıcı ---------------------------------------------------------------------
def _client(clock, sleeps, lock, source="musicbrainz"):
    def sleep(s):
        with lock:
            sleeps.append(s)
            clock["t"] += s

    return SourceClient(
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))),
        user_agent="Tini/test ( t@example.com )", min_interval=1.0, max_retries=0,
        backoff_base=1.0, backoff_max=1.0, sleep=sleep, clock=lambda: clock["t"], source=source,
    )


def test_limiter_is_shared_across_clients_by_source_name():
    clock, sleeps, lock = {"t": 0.0}, [], threading.Lock()
    a, b = _client(clock, sleeps, lock), _client(clock, sleeps, lock)
    a.get_json("https://x/1")
    b.get_json("https://x/2")  # farklı istemci, aynı kaynak: 1 sn beklemeli
    assert sleeps == [1.0]
    assert get_limiter("musicbrainz") is get_limiter("musicbrainz")
    assert get_limiter("musicbrainz") is not get_limiter("lastfm")


def test_limiter_two_threads_share_interval_and_sleep_outside_lock():
    limiter = get_limiter("musicbrainz")
    clock = {"t": 100.0}
    slept: list[float] = []
    inside_lock_sleep: list[bool] = []
    barrier = threading.Barrier(2)

    def sleep(s):
        inside_lock_sleep.append(limiter._lock.locked())
        slept.append(s)

    def worker():
        barrier.wait()
        limiter.acquire(1.0, lambda: clock["t"], sleep)

    ts = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    # Saat sabit: biri hemen geçer, diğeri tam 1 sn bekler; üçüncü slot 2 sn olurdu.
    assert slept == [1.0]
    assert inside_lock_sleep == [False]
    limiter.acquire(1.0, lambda: clock["t"], sleep)
    assert slept == [1.0, 2.0]


def test_unnamed_clients_keep_private_limiters():
    clock, sleeps, lock = {"t": 0.0}, [], threading.Lock()
    a, b = _client(clock, sleeps, lock, None), _client(clock, sleeps, lock, None)
    a.get_json("https://x/1")
    b.get_json("https://x/2")
    assert sleeps == []


# ---- get_json sağlamlığı -----------------------------------------------------------------------
@pytest.mark.parametrize("body", [b"", b"<html>Bad gateway</html>"])
def test_get_json_non_json_body_is_source_error(body):
    c = SourceClient(
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))),
        user_agent="t", min_interval=0, max_retries=0, backoff_base=1, backoff_max=1,
        sleep=lambda s: None, clock=lambda: 0.0,
    )
    with pytest.raises(SourceError):
        c.get_json("https://x/a")


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


def test_lastfm_html_response_for_one_artist_does_not_abort_round(db):
    def handler(req):
        if req.url.params.get("artist") == "Bozuk":
            return httpx.Response(200, content=b"<html>Bad gateway</html>")
        return httpx.Response(200, json={"similarartists": {"artist": [
            {"name": "Komsu", "match": "0.9"}]}})

    src = SourceClient(
        httpx.Client(transport=httpx.MockTransport(handler)),
        user_agent="t", min_interval=0, max_retries=0, backoff_base=1, backoff_max=1,
        sleep=lambda s: None, clock=lambda: 0.0,
    )
    lfm = LastfmClient(src, "https://ws.audioscrobbler.com/2.0/", "k")
    bad = Artist(name="Bozuk", name_norm="bozuk")
    good = Artist(name="Saglam", name_norm="saglam")
    db.add_all([bad, good])
    db.flush()
    r = expand(db, lfm, GraphSettings(), limit=5, depth=1, anchors=[bad.id, good.id],
               now=datetime(2026, 11, 8, tzinfo=UTC))
    assert r["error"] == 1 and r["ok"] == 1
    assert db.get(FetchLog, ("lastfm_similar", f"artist:{bad.id}")).status == "error"


# ---- Tek engine --------------------------------------------------------------------------------
def test_engine_is_singleton_and_reset_creates_new_one():
    db_mod.reset_engine()
    e1 = db_mod.get_engine()
    assert db_mod.get_engine() is e1
    f1 = db_mod.get_session_factory()
    assert db_mod.get_session_factory() is f1
    db_mod.reset_engine()
    e2 = db_mod.get_engine()
    assert e2 is not e1
    assert db_mod.get_session_factory() is not f1
    db_mod.reset_engine()


# ---- Stages / upstream -------------------------------------------------------------------------
def test_stages_lap_and_header():
    t = {"v": 0.0}
    st = Stages(clock=lambda: t["v"])
    t["v"] = 0.0125
    st.lap("candidates")
    with st.stage("rank"):
        t["v"] = 0.0225
    assert st.as_dict() == {"candidates": 12.5, "rank": 10.0}
    assert st.header() == "candidates;dur=12.5, rank;dur=10.0"


def test_parse_retry_after_handles_seconds_date_and_garbage():
    now = datetime(2026, 11, 8, 12, 0, 0, tzinfo=UTC)
    assert parse_retry_after("7", 30) == 7
    assert parse_retry_after(None, 30) == 30
    assert parse_retry_after("saçma", 30) == 30
    date = (now + timedelta(seconds=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert parse_retry_after(date, 30, now) == 90


def _status_error(code, headers=None):
    req = httpx.Request("GET", "https://api.spotify.com/v1/me")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, headers=headers))


def test_upstream_unavailable_maps_statuses():
    e = upstream_unavailable(_status_error(503, {"Retry-After": "12"}), "İçe aktarma")
    assert isinstance(e, HTTPException) and e.status_code == 503
    assert e.headers["Retry-After"] == "12"
    assert upstream_unavailable(_status_error(429), "x").headers["Retry-After"] == "30"
    assert upstream_unavailable(_status_error(401), "x").status_code == 409
    assert upstream_unavailable(httpx.ConnectError("x"), "x").status_code == 503
    assert upstream_unavailable(_status_error(400), "x").status_code == 502


def test_spotify_http_date_retry_after_does_not_crash():
    from app.adapters.spotify.client import SpotifyAdapter

    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
        return httpx.Response(200, json={"items": []})

    sleeps = []
    a = SpotifyAdapter(httpx.Client(transport=httpx.MockTransport(handler)), "t", sleeps.append)
    assert a._request("GET", "/me") == {"items": []}
    assert sleeps == [0.0]


def test_request_log_server_timing_flag_off_hides_stages(monkeypatch):
    from app import requestlog
    from app.config import Settings

    class S:
        stages = Stages(clock=lambda: 0.0)

    s = S()
    s.stages.add("rank", 1.0)

    class Req:
        state = s

    assert requestlog._stages(Req()) is s.stages
    monkeypatch.setattr(requestlog, "get_settings",
                        lambda: Settings(_env_file=None, server_timing_enabled=False))
    assert requestlog._stages(Req()) is None


def test_rapid_vote_bench_summary_and_percentiles():
    from app.jobs.rapid_vote_bench import percentile, summarize

    vals = [float(i) for i in range(1, 101)]
    assert percentile(vals, 50) == 50.0 and percentile(vals, 95) == 95.0
    assert percentile([], 95) == 0.0
    s = summarize(vals, empty=2, server_errors=1, rss_mb={"peak": 100.0})
    assert s["p95_ms"] == 95 and s["max_ms"] == 100 and s["empty_responses"] == 2
    assert "token" not in json.dumps(s).lower()
