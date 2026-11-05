import httpx
from sqlalchemy import func, select
from test_lists_api import _connect_spotify, client, db, register  # noqa: F401
from test_queue import lib_track, mk_artist

from app.models import ListenLater, Track, TrackComment, User, UserTrackMeta


def _uid(db, email):  # noqa: F811
    return db.scalar(select(User.id).where(User.email == email))


def _item(isrc, name="Şarkı", artist="Sanatçı", with_isrc=True):
    return {
        "id": "S" + isrc, "name": name, "artists": [{"name": artist}],
        "external_ids": {"isrc": isrc} if with_isrc else {},
        "album": {"images": [{"url": "https://i.scdn.co/x", "width": 300}]},
    }


# ---- Sonra dinle -------------------------------------------------------------------------------


def test_later_add_list_remove_is_idempotent_and_private(client, db):  # noqa: F811
    h = register(client, "t1@example.com")
    t = lib_track(db, "t1@example.com", "ZZT000000001", mk_artist(db, "TA"), "Bir")
    assert client.post("/later", json={"track": t.id}, headers=h).status_code == 201
    again = client.post("/later", json={"track": t.id}, headers=h)
    assert again.status_code == 201  # tekrar: sorun yok
    items = client.get("/later", headers=h).json()["items"]
    assert [i["track"] for i in items] == [t.id] and items[0]["title"] == "Bir"
    h2 = register(client, "t2@example.com")
    assert client.get("/later", headers=h2).json()["items"] == []
    assert client.delete(f"/later/{t.id}", headers=h2).status_code == 204  # başkasınınkine dokunmaz
    assert len(client.get("/later", headers=h).json()["items"]) == 1
    assert client.delete(f"/later/{t.id}", headers=h).status_code == 204
    assert client.get("/later", headers=h).json()["items"] == []


def test_later_unknown_track_404_and_requires_auth(client, db):  # noqa: F811
    h = register(client, "t3@example.com")
    assert client.post("/later", json={"track": 999999999}, headers=h).status_code == 404
    assert client.post("/later", json={"track": 1}).status_code == 401


def test_later_track_leaves_vote_queue_and_returns_on_remove(client, db):  # noqa: F811
    h = register(client, "t4@example.com")
    t = lib_track(db, "t4@example.com", "ZZT000000002", mk_artist(db, "TB"), "Iki")
    assert [i["track"] for i in client.get("/votes/queue", headers=h).json()["items"]] == [t.id]
    client.post("/later", json={"track": t.id}, headers=h)
    assert client.get("/votes/queue", headers=h).json()["items"] == []
    client.delete(f"/later/{t.id}", headers=h)
    assert [i["track"] for i in client.get("/votes/queue", headers=h).json()["items"]] == [t.id]


def test_later_export_writes_playlist_and_skips_unresolved(client, db, monkeypatch):  # noqa: F811
    h = register(client, "t5@example.com")
    a = lib_track(db, "t5@example.com", "ZZT000000003", mk_artist(db, "TC"), "Uc")
    b = lib_track(db, "t5@example.com", "ZZT000000004", mk_artist(db, "TD"), "Dort")
    for t in (a, b):
        client.post("/later", json={"track": t.id}, headers=h)
    posted = []

    def handler(req):
        if req.url.path == "/v1/search":
            hit = "ZZT000000003" in req.url.params["q"]
            return httpx.Response(200, json={"tracks": {"items": [{"id": "T1"}] if hit else []}})
        if req.url.path == "/v1/me/playlists":
            return httpx.Response(201, json={"id": "PL1"})
        posted.append(req.content)
        return httpx.Response(201, json={})

    _connect_spotify(db, "t5@example.com", monkeypatch, handler)
    r = client.post("/later/export/spotify", headers=h)
    assert r.status_code == 201
    assert r.json() == {"playlist_id": "PL1", "added": 1, "skipped": [b.id]}
    assert b"spotify:track:T1" in posted[0]


def test_later_export_without_connection_is_409(client, db):  # noqa: F811
    h = register(client, "t6@example.com")
    assert client.post("/later/export/spotify", headers=h).status_code == 409


# ---- Arama -------------------------------------------------------------------------------------


def test_search_returns_cards_and_caches_without_link(client, db, monkeypatch):  # noqa: F811
    h = register(client, "t7@example.com")

    def handler(req):
        assert req.url.params["q"] == "tarkan"
        return httpx.Response(200, json={"tracks": {"items": [
            _item("ZZS000000001", "Şımarık"), _item("ZZS000000001", "Çift"),  # aynı ISRC tek kez
            _item("ZZS000000002", with_isrc=False),  # ISRC'siz atlanır
            _item("ZZS000000003", "Kuzu Kuzu"),
        ]}})

    _connect_spotify(db, "t7@example.com", monkeypatch, handler)
    r = client.get("/search?q=tarkan", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["title"] for i in items] == ["Şımarık", "Kuzu Kuzu"]
    assert items[0]["image"] == "https://i.scdn.co/x"
    uid = _uid(db, "t7@example.com")
    assert db.scalar(
        select(func.count()).select_from(UserTrackMeta).where(UserTrackMeta.user_id == uid)
    ) == 2
    assert {t.isrc for t in db.scalars(select(Track).where(Track.isrc.like("ZZS%")))} == {
        "ZZS000000001", "ZZS000000003"
    }


def test_search_validates_query_and_maps_service_errors(client, db, monkeypatch):  # noqa: F811
    h = register(client, "t8@example.com")
    assert client.get("/search?q=a", headers=h).status_code == 422
    assert client.get("/search?q=abc").status_code == 401
    assert client.get("/search?q=abc", headers=h).status_code == 409  # servis bağlı değil
    _connect_spotify(db, "t8@example.com", monkeypatch, lambda r: httpx.Response(403))
    assert client.get("/search?q=abc", headers=h).status_code == 409
    _connect_spotify_500 = lambda r: httpx.Response(500)  # noqa: E731
    from app.connect import get_http
    from app.main import app

    app.dependency_overrides[get_http] = lambda: httpx.Client(
        transport=httpx.MockTransport(_connect_spotify_500)
    )
    assert client.get("/search?q=abc", headers=h).status_code == 502


# ---- Yorumlar ----------------------------------------------------------------------------------


def test_comments_are_public_pseudonymous_and_ownership_checked(client, db):  # noqa: F811
    h1 = register(client, "c1@example.com")
    h2 = register(client, "c2@example.com")
    t = lib_track(db, "c1@example.com", "ZZC000000001", mk_artist(db, "CA"), "Yorumlu")
    r = client.post(f"/tracks/{t.id}/comments", json={"body": "  Harika  "}, headers=h1)
    assert r.status_code == 201
    c = r.json()
    assert c["body"] == "Harika" and c["mine"] is True and c["author"].startswith("Tını #")
    assert "c1@example.com" not in str(c)
    # başka kullanıcı görür ama kendi değildir
    body = client.get(f"/tracks/{t.id}/comments", headers=h2).json()
    assert [(i["body"], i["mine"]) for i in body["items"]] == [("Harika", False)]
    assert client.patch(f"/comments/{c['id']}", json={"body": "x"}, headers=h2).status_code == 403
    assert client.delete(f"/comments/{c['id']}", headers=h2).status_code == 403
    e = client.patch(f"/comments/{c['id']}", json={"body": "Düzenlendi"}, headers=h1).json()
    assert e["body"] == "Düzenlendi" and e["edited_at"] is not None
    assert client.delete(f"/comments/{c['id']}", headers=h1).status_code == 204
    assert client.get(f"/tracks/{t.id}/comments", headers=h1).json()["items"] == []
    assert client.delete(f"/comments/{c['id']}", headers=h1).status_code == 404


def test_comments_validation(client, db):  # noqa: F811
    h = register(client, "c3@example.com")
    t = lib_track(db, "c3@example.com", "ZZC000000002", mk_artist(db, "CB"), "V")
    url = f"/tracks/{t.id}/comments"
    assert client.post(url, json={"body": ""}, headers=h).status_code == 422
    assert client.post(url, json={"body": "   "}, headers=h).status_code == 422
    assert client.post(url, json={"body": "a" * 1001}, headers=h).status_code == 422
    missing = client.post("/tracks/999999999/comments", json={"body": "x"}, headers=h)
    assert missing.status_code == 404
    assert client.post(url, json={"body": "x"}).status_code == 401


def test_account_deletion_removes_later_and_comments(client, db):  # noqa: F811
    h = register(client, "c4@example.com")
    t = lib_track(db, "c4@example.com", "ZZC000000003", mk_artist(db, "CC"), "S")
    client.post("/later", json={"track": t.id}, headers=h)
    client.post(f"/tracks/{t.id}/comments", json={"body": "x"}, headers=h)
    db.delete(db.get(User, _uid(db, "c4@example.com")))
    db.flush()
    assert db.scalar(select(func.count()).select_from(ListenLater)) == 0
    assert db.scalar(select(func.count()).select_from(TrackComment)) == 0
