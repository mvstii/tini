# ruff: noqa: F811
from datetime import date

import httpx
from test_lists_api import (  # noqa: F401
    _connect_spotify,
    client,
    db,
    library_track,
    register,
    setup_user,
)

from app.recommend.daily import pick_daily

DAY = date(2026, 11, 2)


def test_pick_is_deterministic_and_skips_voted():
    cands = [(1, 10), (2, 20), (3, None)]
    a = pick_daily(cands, DAY, "u1", set(), "daily-1")
    assert a == pick_daily(cands, DAY, "u1", set(), "daily-1")
    assert a in {1, 2, 3}
    rest = pick_daily(cands, DAY, "u1", {10, 20}, "daily-1")
    assert rest == 3  # yalnız parçası olmayan öğe kaldı
    assert pick_daily([(1, 10)], DAY, "u1", {10}, "daily-1") is None


def test_pick_varies_with_day_and_user():
    cands = [(p, None) for p in range(1, 40)]
    days = {pick_daily(cands, date(2026, 11, d), "u1", set(), "s") for d in range(1, 29)}
    users = {pick_daily(cands, DAY, f"u{n}", set(), "s") for n in range(30)}
    assert len(days) > 5 and len(users) > 5


def test_daily_requires_profile(client, db):
    h = register(client, "d0@example.com")
    assert client.get("/recommend/daily", headers=h).status_code == 404


def test_daily_without_service_returns_artist_and_reason(client, db):
    h, seed, c1, c2 = setup_user(client, db, "d1@example.com", "DA")
    r = client.get("/recommend/daily", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["algo_version"] == "daily-1"
    assert body["name"] in {"DAA", "DAB"}
    assert body["title"] is None and body["image"] is None
    assert body["reasons"][0]["seed_name"] == "DASeed"
    assert client.get("/recommend/daily", headers=h).json() == body  # aynı gün, aynı seçim
    url = f"/lists/{body['list_id']}/items/{body['position']}/open"
    assert url.endswith("/open")


def test_daily_card_comes_from_service_and_survives_errors(client, db, monkeypatch):
    h, seed, c1, c2 = setup_user(client, db, "d2@example.com", "DB")
    item = {
        "id": "T1", "name": "Şarkı", "artists": [{"name": "DBA"}, {"name": "DBB"}],
        "album": {"images": [{"url": "http://img/300", "width": 300}]},
    }
    _connect_spotify(
        db, "d2@example.com", monkeypatch,
        lambda req: httpx.Response(200, json={"tracks": {"items": [item]}}),
    )
    body = client.get("/recommend/daily", headers=h).json()
    assert body["title"] == "Şarkı" and body["image"] == "http://img/300"
    assert body["artists"] == ["DBA", "DBB"]

    from app.connect import get_http
    from app.main import app

    app.dependency_overrides[get_http] = lambda: httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(500))
    )
    body = client.get("/recommend/daily", headers=h).json()
    assert body["title"] is None and body["name"] in {"DBA", "DBB"}


def test_daily_returns_track_and_it_can_be_voted_outside_library(client, db):
    from sqlalchemy import select

    from app.models import ListItem, Track

    h, seed, c1, c2 = setup_user(client, db, "d4@example.com", "DD")
    lst = client.post("/lists/generate", headers=h).json()
    t = Track(isrc="ZZDD00000077", artist_id=c1.id)  # kütüphanede değil
    db.add(t)
    db.flush()
    for it in db.scalars(select(ListItem).where(ListItem.list_id == lst["id"])):
        it.track_id = t.id
    db.flush()
    body = client.get("/recommend/daily", headers=h).json()
    assert body["track"] == t.id
    r = client.post("/votes", json={"track": body["track"], "vote": 5}, headers=h)
    assert r.status_code == 201


def test_vote_on_other_users_list_track_is_rejected(client, db):
    from sqlalchemy import select

    from app.models import ListItem, Track

    h1, seed, c1, c2 = setup_user(client, db, "d5@example.com", "DE")
    lst = client.post("/lists/generate", headers=h1).json()
    t = Track(isrc="ZZDE00000077", artist_id=c1.id)
    db.add(t)
    db.flush()
    for it in db.scalars(select(ListItem).where(ListItem.list_id == lst["id"])):
        it.track_id = t.id
    db.flush()
    h2 = register(client, "d6@example.com")
    assert client.post("/votes", json={"track": t.id, "vote": 5}, headers=h2).status_code == 404


def test_daily_skips_voted_tracks(client, db):
    h, seed, c1, c2 = setup_user(client, db, "d3@example.com", "DC")
    t1 = library_track(db, "d3@example.com", "ZZDC00000099", c1)
    client.post("/lists/generate", headers=h)
    client.post("/votes", json={"track": t1.id, "vote": 4}, headers=h)
    for n in range(5):  # her gün oylanmamış olan (DCB) çıkmalı
        body = client.get("/recommend/daily", headers=h).json()
        assert body["name"] == "DCB", n
