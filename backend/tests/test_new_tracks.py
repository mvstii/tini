# ruff: noqa: F811
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from test_releases import client, db, mk_artist, register  # noqa: F401

from app.main import app
from app.models import FollowedArtist, Release, ReleaseArtist, User
from app.preview import get_deezer, get_preview_by_id
from app.releases import api as releases_api
from app.sources.deezer import DeezerClient, pick_album
from app.sources.http import SourceError


def test_pick_album_requires_artist_and_title_match():
    data = {"data": [
        {"id": 1, "title": "Other", "artist": {"name": "Sade"}},
        {"id": 2, "title": "Hello", "artist": {"name": "Cover Band"}},
        {"id": 3, "title": "Hello!", "artist": {"name": "sade"}},
    ]}
    assert pick_album(data, "Sade", "Hello") == 3
    assert pick_album(data, "Sade", "Nope") is None
    assert pick_album(None, "Sade", "Hello") is None


class _Src:
    def __init__(self, replies):
        self.replies, self.urls = replies, []

    def get_json(self, url, params=None):
        self.urls.append(url)
        return self.replies[url.split("deezer.test")[1]]


def test_album_tracks_skips_rows_without_id_or_title():
    src = _Src({
        "/search/album": {"data": [{"id": 9, "title": "Hello", "artist": {"name": "Sade"}}]},
        "/album/9/tracks": {"data": [
            {"id": 1, "title": "A"}, {"id": 0, "title": "x"}, {"id": 2, "title": ""},
        ]},
    })
    got = DeezerClient(src, "http://deezer.test").album_tracks("Sade", "Hello")
    assert got == [{"id": 1, "title": "A"}]
    assert DeezerClient(_Src({"/search/album": {"data": []}}), "http://deezer.test") \
        .album_tracks("Sade", "Hello") == []


class FakeDeezer:
    def __init__(self, tracks, fail=False):
        self.tracks, self.fail, self.calls = tracks, fail, 0

    def album_tracks(self, artist, title):
        self.calls += 1
        if self.fail:
            raise SourceError("503")
        return self.tracks


def _setup(client, db, email, days_ago):
    h = register(client, email)
    u = db.scalar(select(User).where(User.email == email))
    a = mk_artist(db, "Sade")
    db.add(FollowedArtist(user_id=u.id, artist_id=a.id, source="manual"))
    day = (datetime.now(UTC) - timedelta(days=days_ago)).date()
    rel = Release(mb_rgid=uuid.uuid4(), title="Hello", primary_type="Album", first_release_date=day)
    db.add(rel)
    db.flush()
    db.add(ReleaseArtist(release_id=rel.id, artist_id=a.id))
    db.flush()
    return h


def test_new_tracks_lists_recent_tracks_caches_and_skips_old(client, db):
    releases_api._TRACKS.clear()
    fake = FakeDeezer([{"id": 11, "title": "A"}, {"id": 12, "title": "B"}])
    app.dependency_overrides[get_deezer] = lambda: fake
    h = _setup(client, db, "nt1@x.com", days_ago=2)
    r = client.get("/releases/new-tracks", headers=h).json()
    assert [(i["deezer_id"], i["title"], i["artist"], i["release"]) for i in r["items"]] == [
        (11, "A", "Sade", "Hello"), (12, "B", "Sade", "Hello")]
    client.get("/releases/new-tracks", headers=h)
    assert fake.calls == 1  # ikinci istek önbellekten
    one = client.get("/releases/new-tracks?limit=1", headers=h).json()["items"]
    assert [i["deezer_id"] for i in one] == [11]


def test_new_tracks_window_and_source_errors(client, db):
    releases_api._TRACKS.clear()
    fake = FakeDeezer([{"id": 1, "title": "A"}])
    app.dependency_overrides[get_deezer] = lambda: fake
    h = _setup(client, db, "nt2@x.com", days_ago=30)
    assert client.get("/releases/new-tracks", headers=h).json()["items"] == []  # 7 gün dışında
    assert fake.calls == 0
    h = _setup(client, db, "nt3@x.com", days_ago=1)
    app.dependency_overrides[get_deezer] = lambda: FakeDeezer([], fail=True)
    assert client.get("/releases/new-tracks", headers=h).json()["items"] == []
    assert releases_api._TRACKS == {}  # hata önbelleğe yazılmaz


def test_preview_by_deezer_id(client, db):
    h = register(client, "nt4@x.com")
    app.dependency_overrides[get_preview_by_id] = lambda: lambda i: (f"http://p/{i}.mp3", "T")
    r = client.get("/preview", params={"deezer_id": 5}, headers=h)
    assert r.json() == {"url": "http://p/5.mp3", "title": "T"}

    def boom(i):
        raise SourceError("x")

    app.dependency_overrides[get_preview_by_id] = lambda: boom
    assert client.get("/preview", params={"deezer_id": 5}, headers=h).json()["url"] is None
