# ruff: noqa: F811
from datetime import UTC, datetime, timedelta

import pytest
from test_lists_api import client, db, mk_artist, register, setup_user  # noqa: F401

from app.artwork import get_fetcher
from app.catalog.artist_images import cached_images, fill_images
from app.config import ArtworkSettings
from app.main import app
from app.models import ArtistImage
from app.sources.deezer import DeezerClient, check_error, pick_album_cover, pick_picture
from app.sources.http import SourceError

NOW = datetime(2026, 11, 3, tzinfo=UTC)
CFG = ArtworkSettings(_env_file=None)


def test_pick_album_cover_needs_exact_artist_and_skips_placeholder():
    data = {"data": [
        {"artist": {"name": "Other"}, "album": {"cover_xl": "http://x/other.jpg"}},
        {"artist": {"name": "Niche"}, "album": {"cover_xl": "http://x/cover//1000x1000.jpg"}},
        {"artist": {"name": "niche"}, "album": {"cover_big": "http://x/right.jpg"}},
    ]}
    assert pick_album_cover(data, "Niche") == "http://x/right.jpg"
    assert pick_album_cover({"data": []}, "Niche") is None
    assert pick_album_cover(None, "Niche") is None


def test_artist_picture_falls_back_to_album_cover_when_no_portrait():
    calls = []

    class Http:
        def get_json(self, url, params=None):
            calls.append(url)
            if url.endswith("/search/artist"):
                return {"data": []}
            return {"data": [{"artist": {"name": "Niche"}, "album": {"cover_big": "http://x/c.jpg"}}]}

    assert DeezerClient(Http(), "http://d").artist_picture("Niche") == "http://x/c.jpg"
    assert len(calls) == 2


def test_pick_picture_matches_exact_name_and_skips_placeholder():
    data = {"data": [
        {"name": "Radiohead Tribute", "picture_xl": "http://x/wrong.jpg"},
        {"name": "radiohead", "picture_xl": "http://x/right.jpg"},
    ]}
    assert pick_picture(data, "Radiohead") == "http://x/right.jpg"
    empty = {"data": [{"name": "Niche", "picture_xl": "https://cdn/images/artist//1000x1000.jpg"}]}
    assert pick_picture(empty, "Niche") is None
    assert pick_picture({"data": []}, "Niche") is None
    assert pick_picture(None, "Niche") is None


def test_deezer_quota_and_busy_errors_are_transient_not_a_miss():
    for code in (4, 700):
        with pytest.raises(SourceError):
            check_error({"error": {"type": "Exception", "message": "Quota", "code": code}})
    no_data = {"error": {"type": "DataException", "message": "no data", "code": 800}}
    assert check_error(no_data) == no_data  # "veri yok" gerçek bir yokluktur
    assert check_error({"data": []}) == {"data": []}
    assert check_error(None) is None


def test_fill_caches_hits_and_misses_and_respects_limit(db):
    a = [mk_artist(db, f"Art{n}") for n in range(3)]
    calls: list[str] = []

    def fetch(name):
        calls.append(name)
        return None if name == "Art1" else f"http://img/{name}"

    cfg = ArtworkSettings(_env_file=None, fill_limit=2)
    known, pending = fill_images(db, [x.id for x in a], fetch, cfg, NOW)
    assert calls == ["Art0", "Art1"] and pending == 1
    assert known == {a[0].id: "http://img/Art0", a[1].id: None}
    known, pending = fill_images(db, [x.id for x in a], fetch, cfg, NOW)
    assert calls == ["Art0", "Art1", "Art2"] and pending == 0  # önbellektekiler yeniden sorulmaz
    assert known[a[2].id] == "http://img/Art2"


def test_expired_rows_are_refetched(db):
    a = mk_artist(db, "Old")
    db.add(ArtistImage(artist_id=a.id, url="http://old", source="deezer", fetched_at=NOW,
                       expires_at=NOW - timedelta(days=1)))
    db.flush()
    assert cached_images(db, [a.id], NOW) == {}
    known, _ = fill_images(db, [a.id], lambda n: "http://new", CFG, NOW)
    assert known[a.id] == "http://new"


def test_source_error_stops_fill_without_recording(db):
    a = mk_artist(db, "Boom")

    def fetch(name):
        raise SourceError("HTTP 429")

    known, pending = fill_images(db, [a.id], fetch, CFG, NOW)
    assert known == {} and pending == 1
    assert cached_images(db, [a.id], NOW) == {}


def test_images_endpoint_and_list_includes_cached_photo(client, db):
    h, seed, c1, c2 = setup_user(client, db, "art1@example.com", "AW")
    app.dependency_overrides[get_fetcher] = lambda: (lambda name: f"http://img/{name}")
    r = client.get(f"/artists/images?ids={c1.id},{c2.id},abc", headers=h)
    assert r.status_code == 200
    assert r.json() == {
        "images": {str(c1.id): "http://img/AWA", str(c2.id): "http://img/AWB"}, "pending": 0}
    lst = client.post("/lists/generate", headers=h).json()
    photos = {i["name"]: i["artist_image"] for i in lst["items"]}
    assert photos["AWA"] == "http://img/AWA"
    daily = client.get("/recommend/daily", headers=h).json()
    assert daily["artist_image"] == f"http://img/{daily['name']}"
    assert daily["artist_id"] in {c1.id, c2.id}


def test_images_endpoint_requires_auth(client):
    assert client.get("/artists/images?ids=1").status_code == 401
    h = register(client, "art2@example.com")
    app.dependency_overrides[get_fetcher] = lambda: (lambda name: None)
    assert client.get("/artists/images?ids=", headers=h).json() == {"images": {}, "pending": 0}


def test_old_source_misses_are_rechecked_but_found_urls_stay(client, db):
    from app.models import ArtistImage
    a = mk_artist(db, "OldMissA")
    b = mk_artist(db, "OldMissB")
    far = NOW + timedelta(days=10)
    db.add_all([
        ArtistImage(artist_id=a.id, url=None, source="deezer", expires_at=far),
        ArtistImage(artist_id=b.id, url="http://x/b.jpg", source="deezer", expires_at=far),
    ])
    db.flush()
    assert cached_images(db, [a.id, b.id], NOW) == {b.id: "http://x/b.jpg"}
