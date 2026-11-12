import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import ReleasesSettings, Settings
from app.deps import get_db
from app.main import app
from app.models import Artist, FetchLog, FollowedArtist, Release, ReleaseArtist, TasteProfile, User
from app.releases.follow import auto_follows, effective_follows
from app.releases.service import detect_releases
from app.sources.http import SourceError
from app.sources.musicbrainz import MbReleaseGroup, parse_release_groups

CFG = ReleasesSettings(_env_file=None)
NOW = datetime(2026, 11, 1, tzinfo=UTC)


def test_auto_follows_collects_anchors_clusters_and_unclustered():
    profile = {
        "anchors": [{"artist_id": 1}],
        "clusters": [{"artists": [{"artist_id": 2}, {"artist_id": 3}]}],
        "unclustered": [{"artist_id": 4}],
    }
    assert auto_follows(profile) == {1, 2, 3, 4}
    assert auto_follows({}) == set()


def test_effective_follows_mute_removes_auto_manual_adds():
    assert effective_follows({1, 2, 3}, {9}, {2}) == {1: "auto", 3: "auto", 9: "manual"}


def _rg(i, date_s, ptype="Album", credits=()):
    return {
        "id": str(uuid.UUID(int=i)), "title": f"T{i}", "primary-type": ptype,
        "first-release-date": date_s,
        "artist-credit": [{"artist": {"id": str(c)}} for c in credits],
    }


def test_parse_keeps_full_dates_and_allowed_types_only():
    data = {"release-groups": [
        _rg(1, "2026-10-01"), _rg(2, "2026-10"), _rg(3, ""), _rg(4, "2026-10-02", "Broadcast"),
        _rg(5, "2026-10-03", "Single", [uuid.UUID(int=77)]),
    ]}
    out = parse_release_groups(data, CFG.types)
    assert [g.title for g in out] == ["T1", "T5"]
    assert out[1].primary_type == "single" and out[1].artist_mbids == (uuid.UUID(int=77),)
    assert out[0].first_release_date == date(2026, 10, 1)
    assert parse_release_groups(None, CFG.types) == []


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


@pytest.fixture
def client(db, monkeypatch):
    cfg = Settings(_env_file=None, credential_key=Fernet.generate_key().decode())
    monkeypatch.setattr("app.auth.get_settings", lambda: cfg)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(c, email):
    r = c.post("/auth/register", json={"email": email, "password": "uzun-parola-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def mk_artist(db, name, mbid=True):
    a = Artist(name=name, name_norm=name.lower(), mbid=uuid.uuid4() if mbid else None)
    db.add(a)
    db.flush()
    return a


class FakeMb:
    def __init__(self, groups_by_mbid, fail=()):
        self.groups, self.fail, self.calls = groups_by_mbid, set(fail), []

    def release_groups(self, mbid, since, until, types, limit):
        self.calls.append((mbid, since, until))
        if mbid in self.fail:
            raise SourceError("503")
        return self.groups.get(mbid, [])


def _group(i, title, when, credits=()):
    return MbReleaseGroup(uuid.UUID(int=i), title, "single", when, tuple(credits))


def test_detect_stores_releases_dedups_and_caches(db):
    a = mk_artist(db, "DA")
    b = mk_artist(db, "DB")
    none = mk_artist(db, "DN", mbid=False)
    shared = _group(100, "Ortak", date(2026, 10, 5), [a.mbid, b.mbid])
    mb = FakeMb({a.mbid: [shared, _group(101, "Tek", date(2026, 10, 6))], b.mbid: [shared]})
    res = detect_releases(db, mb, CFG, NOW, {a.id, b.id, none.id})
    assert (res.queried, res.no_mbid, res.new_releases) == (2, 1, 2)
    assert db.scalar(select(func.count()).select_from(Release)) >= 2
    rel = db.scalar(select(Release).where(Release.mb_rgid == shared.mbid))
    linked = set(
        db.scalars(select(ReleaseArtist.artist_id).where(ReleaseArtist.release_id == rel.id))
    )
    assert linked == {a.id, b.id}
    assert mb.calls[0][1:] == (date(2026, 7, 4), date(2026, 11, 1))  # 120 gün pencere

    again = detect_releases(db, mb, CFG, NOW + timedelta(days=1), {a.id, b.id})
    assert (again.queried, again.skipped_cached, again.new_releases) == (0, 2, 0)
    later = detect_releases(db, mb, CFG, NOW + timedelta(days=8), {a.id, b.id})
    assert (later.queried, later.new_releases) == (2, 0)  # tekrar çekilir ama yinelenmez


def test_detect_error_is_not_cached_and_empty_is_cached(db):
    a, b = mk_artist(db, "EA"), mk_artist(db, "EB")
    mb = FakeMb({}, fail={a.mbid})
    res = detect_releases(db, mb, CFG, NOW, {a.id, b.id})
    assert (res.errors, res.queried) == (1, 1)
    assert db.get(FetchLog, ("mb_release", f"artist:{a.id}")) is None
    assert db.get(FetchLog, ("mb_release", f"artist:{b.id}")).status == "empty"


def test_following_api_auto_manual_mute_and_privacy(client, db):
    h = register(client, "r1@example.com")
    u = db.scalar(select(User).where(User.email == "r1@example.com"))
    a, b, c = mk_artist(db, "FA"), mk_artist(db, "FB"), mk_artist(db, "FC", mbid=False)
    db.add(TasteProfile(
        user_id=u.id, version=1, algo_version="p", graph_version=1,
        body={"anchors": [{"artist_id": a.id}], "clusters": [], "unclustered": []},
    ))
    db.flush()
    items = client.get("/releases/following", headers=h).json()["items"]
    assert [(i["artist_id"], i["source"], i["trackable"]) for i in items] == [(a.id, "auto", True)]

    assert client.put(f"/releases/following/{c.id}", headers=h).json()["source"] == "manual"
    assert client.delete(f"/releases/following/{a.id}", headers=h).status_code == 204
    items = client.get("/releases/following", headers=h).json()["items"]
    got = [(i["artist_id"], i["source"], i["trackable"]) for i in items]
    assert got == [(c.id, "manual", False)]
    assert client.put(f"/releases/following/{a.id}", headers=h).status_code == 200  # tekrar takip
    assert client.put("/releases/following/999999999", headers=h).status_code == 404

    h2 = register(client, "r2@example.com")
    assert client.get("/releases/following", headers=h2).json()["items"] == []
    client.delete(f"/releases/following/{b.id}", headers=h2)
    assert db.get(FollowedArtist, (u.id, b.id)) is None


def test_account_delete_removes_followed_artist(db):
    u = User(email="r3@example.com", password_hash="x")
    a = mk_artist(db, "GA")
    db.add(u)
    db.flush()
    db.add(FollowedArtist(user_id=u.id, artist_id=a.id, source="manual"))
    db.flush()
    db.delete(u)
    db.flush()
    assert db.scalar(select(func.count()).select_from(FollowedArtist).where(
        FollowedArtist.artist_id == a.id)) == 0
