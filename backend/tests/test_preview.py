# ruff: noqa: F811
import itertools

from test_lists_api import client, db, mk_artist, register, setup_user  # noqa: F401

from app.main import app
from app.models import Track
from app.preview import get_preview_fetcher
from app.sources.deezer import pick_preview
from app.sources.http import SourceError


def test_pick_preview_single_track_and_artist_search():
    one = {"preview": "http://p/1.mp3", "title": "Song"}
    assert pick_preview(one) == ("http://p/1.mp3", "Song")
    assert pick_preview({"id": 1, "preview": ""}) is None
    assert pick_preview(None) is None
    search = {"data": [
        {"preview": "http://p/a.mp3", "title": "A", "artist": {"name": "Cover Band"}},
        {"preview": "http://p/b.mp3", "title": "B", "artist": {"name": "Radiohead"}},
    ]}
    assert pick_preview(search, "radiohead") == ("http://p/b.mp3", "B")
    assert pick_preview(search, "Nobody") is None


_n = itertools.count()


def _call(client, fetch, **params):
    app.dependency_overrides[get_preview_fetcher] = lambda: fetch
    try:
        h = register(client, f"p{next(_n)}@x.com")
        return client.get("/preview", params=params, headers=h)
    finally:
        app.dependency_overrides.pop(get_preview_fetcher, None)


def test_preview_uses_isrc_and_artist_name(client, db):
    a = mk_artist(db, "Sade")
    t = Track(isrc="USABC1", artist_id=a.id)
    db.add(t)
    db.flush()
    seen = []

    def fetch(isrc, name):
        seen.append((isrc, name))
        return "http://p/x.mp3", "Smooth"

    r = _call(client, fetch, artist_id=a.id, track_id=t.id)
    assert r.status_code == 200
    assert r.json() == {"url": "http://p/x.mp3", "title": "Smooth"}
    assert seen == [("USABC1", "Sade")]


def test_preview_empty_when_unknown_or_source_fails(client, db):
    a = mk_artist(db, "Ghost")

    def boom(isrc, name):
        raise SourceError("x")

    assert _call(client, boom, artist_id=a.id).json() == {"url": None, "title": None}
    assert _call(client, lambda i, n: None).json() == {"url": None, "title": None}


def test_preview_requires_auth(client):
    assert client.get("/preview", params={"artist_id": 1}).status_code == 401
