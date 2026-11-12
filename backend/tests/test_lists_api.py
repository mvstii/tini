from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import RecommendSettings, Settings, get_recommend_settings
from app.db import make_engine
from app.deps import get_db
from app.graph.service import clear_cache
from app.main import app
from app.models import (
    Artist,
    ArtistEdge,
    ArtistTag,
    GraphSnapshot,
    Track,
    User,
    UserTrackLink,
)

NOW = datetime(2026, 10, 31, tzinfo=UTC)


@pytest.fixture
def db():
    engine = make_engine()
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


@pytest.fixture
def client(db, monkeypatch):
    cfg = Settings(_env_file=None, credential_key=Fernet.generate_key().decode())
    monkeypatch.setattr("app.auth.get_settings", lambda: cfg)
    app.dependency_overrides[get_db] = lambda: db
    clear_cache()
    yield TestClient(app)
    app.dependency_overrides.clear()
    clear_cache()


def register(c, email):
    r = c.post("/auth/register", json={"email": email, "password": "uzun-parola-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def mk_artist(db, name):
    a = Artist(name=name, name_norm=name.lower())
    db.add(a)
    db.flush()
    return a


def library_track(db, email, isrc, artist):
    u = db.scalar(select(User).where(User.email == email))
    t = Track(isrc=isrc, artist_id=artist.id)
    db.add(t)
    db.flush()
    db.add(UserTrackLink(user_id=u.id, service="spotify", external_id=isrc, track_id=t.id))
    db.flush()
    return t


def edge(a, b, w=0.9):
    return ArtistEdge(src=a.id, dst=b.id, source="lastfm", weight=w, fetched_at=NOW,
                      expires_at=NOW + timedelta(days=1))


def setup_user(client, db, email, tag):
    h = register(client, email)
    seed, c1, c2 = (mk_artist(db, f"{tag}{n}") for n in ("Seed", "A", "B"))
    db.add_all([edge(seed, c1), edge(seed, c2)])
    db.add(GraphSnapshot(edge_count=2, params={}))
    db.flush()
    t = library_track(db, email, f"ZZ{tag}00000001", seed)
    client.post("/votes", json={"track": t.id, "vote": 6}, headers=h)
    client.post("/profile/rebuild", headers=h)
    return h, seed, c1, c2


def test_generate_requires_profile(client, db):
    h = register(client, "l0@example.com")
    assert client.post("/lists/generate", headers=h).status_code == 404


def test_generate_persists_list_with_reasons_and_track(client, db):
    h, seed, c1, c2 = setup_user(client, db, "l1@example.com", "LA")
    shared = Track(isrc="ZZLA00000099", artist_id=c1.id)
    db.add(shared)
    db.flush()

    r = client.post("/lists/generate", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["algo_version"] == "list-5" and body["profile_version"] == 1
    items = {i["artist_id"]: i for i in body["items"]}
    assert set(items) == {c1.id, c2.id}
    assert [i["position"] for i in body["items"]] == [1, 2]
    assert items[c1.id]["track_id"] == shared.id and items[c2.id]["track_id"] is None
    assert items[c1.id]["reasons"][0]["seed_name"] == "LASeed"
    assert items[c1.id]["reasons"][0]["is_anchor"]

    again = client.get(f"/lists/{body['id']}", headers=h).json()
    assert again == body


def test_list_is_private_to_owner(client, db):
    h1, *_ = setup_user(client, db, "l2@example.com", "LB")
    lid = client.post("/lists/generate", headers=h1).json()["id"]
    h2 = register(client, "l3@example.com")
    assert client.get(f"/lists/{lid}", headers=h2).status_code == 404


def test_item_feedback_is_recorded_as_event(client, db):
    from app.models import ListFeedback

    h, seed, c1, c2 = setup_user(client, db, "l4@example.com", "LC")
    lst = client.post("/lists/generate", headers=h).json()
    url = f"/lists/{lst['id']}/items/1/feedback"

    r = client.post(url, json={"seed_id": seed.id}, headers=h)
    assert r.status_code == 201 and r.json()["kind"] == "wrong_reason"
    assert client.post(url, json={}, headers=h).status_code == 201  # tüm gerekçe, ikinci olay
    rows = db.scalars(select(ListFeedback).where(ListFeedback.list_id == lst["id"])).all()
    assert [(f.position, f.seed_id) for f in rows] == [(1, seed.id), (1, None)]


def test_item_feedback_validation_and_privacy(client, db):
    h1, seed, c1, c2 = setup_user(client, db, "l5@example.com", "LD")
    lid = client.post("/lists/generate", headers=h1).json()["id"]
    assert client.post(f"/lists/{lid}/items/99/feedback", json={}, headers=h1).status_code == 404
    bad = client.post(f"/lists/{lid}/items/1/feedback", json={"seed_id": c2.id}, headers=h1)
    assert bad.status_code == 422
    assert client.post(
        f"/lists/{lid}/items/1/feedback", json={"kind": "x"}, headers=h1
    ).status_code == 422

    h2 = register(client, "l6@example.com")
    assert client.post(f"/lists/{lid}/items/1/feedback", json={}, headers=h2).status_code == 404


def _connect_spotify(db, email, monkeypatch, handler):
    import httpx

    from app.connect import get_http
    from app.models import ServiceConnection

    u = db.scalar(select(User).where(User.email == email))
    db.add(ServiceConnection(user_id=u.id, service="spotify", external_user_id="sp",
                             access_token_enc=b"x"))
    db.flush()
    monkeypatch.setattr("app.recommend.api.valid_access_value", lambda *_: "AT")
    app.dependency_overrides[get_http] = lambda: httpx.Client(
        transport=httpx.MockTransport(handler))


def test_item_open_resolves_track_then_falls_back_to_search(client, db, monkeypatch):
    import httpx

    h, seed, c1, c2 = setup_user(client, db, "l6@example.com", "LE")
    db.add(Track(isrc="ZZLE00000099", artist_id=c1.id))
    db.flush()
    lst = client.post("/lists/generate", headers=h).json()
    pos = {i["artist_id"]: i["position"] for i in lst["items"]}
    calls = []

    def handler(req):
        calls.append(req.url.params["q"])
        return httpx.Response(200, json={"tracks": {"items": [{"id": "T1"}]}})

    _connect_spotify(db, "l6@example.com", monkeypatch, handler)
    r = client.get(f"/lists/{lst['id']}/items/{pos[c1.id]}/open", headers=h)
    assert r.json() == {"kind": "track", "url": "spotify:track:T1"}
    assert calls == ["isrc:ZZLE00000099"]
    r = client.get(f"/lists/{lst['id']}/items/{pos[c2.id]}/open", headers=h)  # parçası yok
    assert r.json() == {"kind": "search", "url": "spotify:search:LEB"}  # ad eşleşen parça yok
    assert calls == ["isrc:ZZLE00000099"] + ['artist:"LEB"'] * 3  # eşleşme yok: 3 sayfa taranır


def test_item_open_search_fallback_on_service_error(client, db, monkeypatch):
    import httpx

    h, seed, c1, c2 = setup_user(client, db, "l7@example.com", "LF")
    db.add(Track(isrc="ZZLF00000099", artist_id=c1.id))
    db.flush()
    lst = client.post("/lists/generate", headers=h).json()
    pos = {i["artist_id"]: i["position"] for i in lst["items"]}
    _connect_spotify(db, "l7@example.com", monkeypatch, lambda r: httpx.Response(500))
    r = client.get(f"/lists/{lst['id']}/items/{pos[c1.id]}/open", headers=h)
    assert r.json() == {"kind": "search", "url": "spotify:search:LFA"}


def test_item_open_requires_connection_and_ownership(client, db):
    h1, *_ = setup_user(client, db, "l8@example.com", "LG")
    lid = client.post("/lists/generate", headers=h1).json()["id"]
    assert client.get(f"/lists/{lid}/items/1/open", headers=h1).status_code == 409
    assert client.get(f"/lists/{lid}/items/99/open", headers=h1).status_code == 404
    h2 = register(client, "l9@example.com")
    assert client.get(f"/lists/{lid}/items/1/open", headers=h2).status_code == 404


def _export_setup(client, db, monkeypatch, email, tag, handler):
    h, seed, c1, c2 = setup_user(client, db, email, tag)
    db.add(Track(isrc=f"ZZ{tag}00000099", artist_id=c1.id))
    db.flush()
    lst = client.post("/lists/generate", headers=h).json()
    _connect_spotify(db, email, monkeypatch, handler)
    return h, lst


def test_export_writes_playlist_and_reports_skipped(client, db, monkeypatch):
    import httpx

    posted = []

    def handler(req):
        if req.url.path == "/v1/search":
            return httpx.Response(200, json={"tracks": {"items": [{"id": "T1"}]}})
        if req.url.path == "/v1/me/playlists":
            return httpx.Response(201, json={"id": "PL1"})
        posted.append((req.url.path, req.content))
        return httpx.Response(201, json={})

    h, lst = _export_setup(client, db, monkeypatch, "e1@example.com", "EA", handler)
    r = client.post(f"/lists/{lst['id']}/export/spotify", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["playlist_id"] == "PL1" and body["added"] == 1 and len(body["skipped"]) == 1
    assert len(body["skipped_names"]) == 1 and body["skipped_names"][0] in {"EAA", "EAB"}
    assert posted[0][0] == "/v1/playlists/PL1/items" and b"spotify:track:T1" in posted[0][1]


def test_export_resolves_trackless_items_via_artist_search(client, db, monkeypatch):
    import httpx

    posted = []

    def handler(req):
        if req.url.path == "/v1/search":
            q = req.url.params["q"]
            if q.startswith("isrc:"):
                return httpx.Response(200, json={"tracks": {"items": []}})
            name = q.removeprefix('artist:"').removesuffix('"')
            item = {"id": f"S-{name}", "artists": [{"name": name}]}
            return httpx.Response(200, json={"tracks": {"items": [item]}})
        if req.url.path == "/v1/me/playlists":
            return httpx.Response(201, json={"id": "PL2"})
        posted.append(req.content)
        return httpx.Response(201, json={})

    h, lst = _export_setup(client, db, monkeypatch, "e5@example.com", "EE", handler)
    body = client.post(f"/lists/{lst['id']}/export/spotify", headers=h).json()
    assert body == {"playlist_id": "PL2", "added": 2, "skipped": [], "skipped_names": []}
    assert b"S-EEA" in posted[0] and b"S-EEB" in posted[0]


def test_export_with_nothing_resolvable_creates_no_playlist(client, db, monkeypatch):
    import httpx

    def handler(req):
        if req.url.path == "/v1/search":
            return httpx.Response(200, json={"tracks": {"items": []}})
        raise AssertionError("çalma listesi oluşturulmamalı")

    h, lst = _export_setup(client, db, monkeypatch, "e2@example.com", "EB", handler)
    r = client.post(f"/lists/{lst['id']}/export/spotify", headers=h)
    body = r.json()
    assert body["playlist_id"] is None and body["added"] == 0 and body["skipped"] == [1, 2]
    assert sorted(body["skipped_names"]) == ["EBA", "EBB"]


def test_export_maps_scope_error_and_checks_access(client, db, monkeypatch):
    import httpx

    def handler(req):
        if req.url.path == "/v1/search":
            return httpx.Response(200, json={"tracks": {"items": [{"id": "T1"}]}})
        return httpx.Response(403)

    h, lst = _export_setup(client, db, monkeypatch, "e3@example.com", "EC", handler)
    assert client.post(f"/lists/{lst['id']}/export/spotify", headers=h).status_code == 409
    assert client.post(f"/lists/{lst['id']}/export/nope", headers=h).status_code == 400
    h2 = register(client, "e4@example.com")
    assert client.post(f"/lists/{lst['id']}/export/spotify", headers=h2).status_code == 404


def test_generate_assigns_slots_and_unheard_uses_pooled_track(client, db):
    # Küçük yapay grafikte uzak yuva her şeyi alır; bu test bandit yuvalarını sınar.
    app.dependency_overrides[get_recommend_settings] = lambda: RecommendSettings(far_share=0.0)
    h, seed, c1, c2 = setup_user(client, db, "l5@example.com", "LS")
    pooled = library_track(db, "l5@example.com", "ZZLS00000050", c2)
    assert client.post("/votes/unheard", json={"track": pooled.id}, headers=h).status_code == 201

    body = client.post("/lists/generate", headers=h).json()
    items = {i["artist_id"]: i for i in body["items"]}
    assert items[c2.id]["slot"] == "unheard" and items[c2.id]["track_id"] == pooled.id
    assert items[c1.id]["slot"] in ("familiar", "explore")
    assert sum(body["params"]["slot_counts"].values()) == 2
    assert body["params"]["slot_outcomes"] == {}


def far_world(client, db, email, tag):
    """Rock evi (Amazing), caz bitişik (Good), elektronik ve rap hiç oylanmamış."""
    h = register(client, email)
    names = ("SeedR", "SeedJ", "R1", "R2", "J1", "J2", "E1", "H1")
    a = {n: mk_artist(db, f"{tag}{n}") for n in names}
    genre = {"R": "rock", "J": "jazz", "E": "electronic", "H": "hip hop"}
    for n, art in a.items():
        key = n[4] if n.startswith("Seed") else n[0]
        db.add(ArtistTag(artist_id=art.id, tag=genre[key], weight=100, source="musicbrainz"))
    pairs = [("SeedR", "R1"), ("SeedR", "R2"), ("SeedJ", "J1"), ("SeedJ", "J2"),
             ("R1", "E1"), ("J1", "H1")]
    db.add_all([edge(a[x], a[y]) for x, y in pairs])
    db.add(GraphSnapshot(edge_count=len(pairs), params={}))
    db.flush()
    for i, (seed, vote) in enumerate((("SeedR", 6), ("SeedJ", 4))):
        t = library_track(db, email, f"ZZ{tag}0000000{i}", a[seed])
        r = client.post("/votes", json={"track": t.id, "vote": vote}, headers=h)
        assert r.status_code == 201
    client.post("/profile/rebuild", headers=h)
    return h, a


def far_ids(body):
    return {i["artist_id"] for i in body["items"] if i["slot"] == "far"}


def test_generate_list5_far_slot_starts_from_unvoted_genres(client, db):
    cfg = RecommendSettings(_env_file=None, list_size=10, far_home_exclude=1)
    app.dependency_overrides[get_recommend_settings] = lambda: cfg
    h, a = far_world(client, db, "l6@example.com", "LF")
    body = client.post("/lists/generate", headers=h).json()
    assert body["algo_version"] == "list-5" and "nonce" not in body["params"]
    assert far_ids(body) == {a["E1"].id, a["H1"].id}
    assert body["params"]["max_cluster_share"] == 0.5


def test_generate_list6_far_slot_is_adjacent_plus_one_truly_far(client, db):
    cfg = RecommendSettings(
        _env_file=None, list6_enabled=True, list_size=10, far_home_exclude=1
    )
    app.dependency_overrides[get_recommend_settings] = lambda: cfg
    h, a = far_world(client, db, "l7@example.com", "LG")
    body = client.post("/lists/generate", headers=h).json()
    assert body["algo_version"] == "list-6"
    far = far_ids(body)
    assert len(far) == 2
    assert len(far & {a["J1"].id, a["J2"].id}) == 1  # bitişik olası: caz
    assert len(far & {a["E1"].id, a["H1"].id}) == 1  # tek gerçek uzak yuva
    p = body["params"]
    assert p["nonce"] == 0 and p["gumbel_tau"] == 0.0 and p["far_true_count"] == 1
    assert p["max_cluster_share"] == 0.35 and p["far_share"] == 0.2
    rock = sum(1 for i in body["items"] if i["artist_id"] in {a["R1"].id, a["R2"].id})
    assert rock <= 3  # tavan: int(10 × 0,35)

    again = client.post("/lists/generate", headers=h).json()
    assert again["params"]["nonce"] == 1 and again["params"]["gumbel_tau"] == cfg.list_gumbel_tau
    assert far_ids(again) == far  # uzak yuva seçimi nonce'tan bağımsız
