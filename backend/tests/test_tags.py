import uuid

from app.catalog.tags import fetch_artist_tags, normalize_tags
from app.config import GraphSettings
from app.models import Artist, ArtistTag, ArtistTagFetch
from app.sources.musicbrainz import parse_artist_tags
from tests.test_lists_api import db  # noqa: F401


def test_normalize_scales_musicbrainz_and_filters():
    raw = [("rap", 10), ("hip hop", 20), ("zzz", 1), ("", 5)]
    out = normalize_tags(raw, relative=True, min_weight=20, max_n=8)
    assert out == [("hip hop", 100), ("rap", 50)]


def test_normalize_lastfm_absolute_and_cap():
    raw = [("a", 90), ("b", 80), ("c", 70), ("d", 10)]
    assert normalize_tags(raw, relative=False, min_weight=20, max_n=2) == [("a", 90), ("b", 80)]


def test_parse_artist_tags_merges_genres_and_tags():
    data = {
        "genres": [{"name": "Rock", "count": 3}],
        "tags": [{"name": "rock", "count": 5}, {"name": "x", "count": 1}],
    }
    assert parse_artist_tags(data) == [("rock", 5), ("x", 1)]
    assert parse_artist_tags(None) == []


class FakeMb:
    def artist_tags(self, mbid):
        return [("hip hop", 4)] if str(mbid).startswith("1") else []


class FakeLfm:
    def get_top_tags(self, name=None, mbid=None):
        return [("metal", 80)] if mbid else []


def test_fetch_prefers_musicbrainz_falls_back_to_lastfm_and_records_misses(db):  # noqa: F811
    a = Artist(mbid=uuid.UUID("10000000-0000-0000-0000-000000000000"), name="TagA")
    b = Artist(mbid=uuid.UUID("20000000-0000-0000-0000-000000000000"), name="TagB")
    c = Artist(mbid=None, name="TagC")
    db.add_all([a, b, c])
    db.flush()
    stats = fetch_artist_tags(db, FakeMb(), FakeLfm(), GraphSettings(), 1000000)
    assert stats["musicbrainz"] >= 1 and stats["lastfm"] >= 1 and stats["none"] >= 1
    tags = {(t.artist_id, t.tag, t.source) for t in db.query(ArtistTag)}
    assert (a.id, "hip hop", "musicbrainz") in tags and (b.id, "metal", "lastfm") in tags
    assert db.get(ArtistTagFetch, c.id).found is False
    again = fetch_artist_tags(db, FakeMb(), FakeLfm(), GraphSettings(), 1000000)
    assert again["tried"] == 0
