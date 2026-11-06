import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from test_lists_api import client, db, register, setup_user  # noqa: F401

from app.config import RecommendSettings
from app.models import GeneratedList, Release, ReleaseArtist
from app.recommend.fresh import FreshRelease, rank_fresh, recency
from app.recommend.ppr import Reason

CFG = RecommendSettings(_env_file=None)
TODAY = date(2026, 11, 1)
R = [Reason(1, 1.0, 0.5, True)]


def fr(rid, aid, days_ago):
    return FreshRelease(rid, aid, TODAY - timedelta(days=days_ago))


def test_recency_halves_every_half_life():
    assert recency(TODAY, TODAY, 14) == 1.0
    assert abs(recency(TODAY - timedelta(days=14), TODAY, 14) - 0.5) < 1e-9
    assert recency(TODAY + timedelta(days=3), TODAY, 14) == 1.0  # gelecek yaşı 0


def test_rank_orders_by_score_times_recency_and_is_deterministic():
    art = {1: (1.0, R), 2: (0.8, R), 3: (0.5, R)}
    rel = [fr(10, 1, 28), fr(11, 2, 1), fr(12, 3, 0)]
    out = rank_fresh(rel, art, TODAY, CFG)
    assert [i.release_id for i in out] == [11, 12, 10]
    assert out == rank_fresh(list(reversed(rel)), art, TODAY, CFG)
    assert out[0].reasons == R


def test_rank_filters_window_dedups_release_and_artist_and_limits():
    art = {1: (1.0, R), 2: (0.9, R)}
    rel = [
        fr(1, 1, 40),  # pencere dışı
        fr(2, 1, 3), fr(3, 1, 2),  # aynı sanatçı: yalnız biri
        fr(4, 2, 1), FreshRelease(4, 1, TODAY),  # ortak yayın: iyi skorlu sanatçıya, bir kez
        fr(6, 2, 4),
        FreshRelease(5, 2, TODAY + timedelta(days=2)),  # gelecek
    ]
    out = rank_fresh(rel, art, TODAY, CFG)
    assert sorted(i.artist_id for i in out) == [1, 2]
    assert {i.release_id for i in out} == {4, 6}
    assert all(i.release_id not in (1, 5) for i in out)
    small = RecommendSettings(_env_file=None, fresh_list_size=1)
    assert len(rank_fresh(rel, art, TODAY, small)) == 1


def test_rank_unknown_or_negative_artist_scores_zero_and_ranks_last():
    art = {1: (-0.2, []), 2: (0.1, R)}
    out = rank_fresh([fr(1, 1, 0), fr(2, 2, 5), fr(3, 9, 0)], art, TODAY, CFG)
    assert out[0].artist_id == 2
    assert [i.score for i in out[1:]] == [0.0, 0.0]


def add_release(session, artist, title, days_ago):
    r = Release(
        mb_rgid=uuid.uuid4(), title=title, primary_type="album",
        first_release_date=datetime.now(UTC).date() - timedelta(days=days_ago),
    )
    session.add(r)
    session.flush()
    session.add(ReleaseArtist(release_id=r.id, artist_id=artist.id))
    session.flush()
    return r


def test_generate_fresh_persists_release_items_and_skips_seen(client, db):  # noqa: F811
    h, seed, c1, c2 = setup_user(client, db, "f1@example.com", "FR")
    assert client.post("/lists/generate-fresh", headers=h).status_code == 409  # yayın yok
    r1 = add_release(db, seed, "Yeni Albüm", 2)
    add_release(db, c1, "Eski", 90)  # pencere dışı

    r = client.post("/lists/generate-fresh", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "fresh" and body["algo_version"] == "fresh-1"
    [item] = body["items"]
    assert item["slot"] == "fresh" and item["artist_id"] == seed.id
    assert item["release"]["id"] == r1.id and item["release"]["title"] == "Yeni Albüm"
    assert item["reasons"][0]["seed_name"] == "FRSeed" and item["reasons"][0]["is_anchor"]
    assert client.get(f"/lists/{body['id']}", headers=h).json() == body

    # aynı yayın bir sonraki Taze listede tekrarlanmaz
    assert client.post("/lists/generate-fresh", headers=h).status_code == 409
    # ana liste çıktıları Taze listeden etkilenmez
    main = client.post("/lists/generate", headers=h).json()
    assert main["kind"] == "main" and main["params"]["slot_outcomes"] == {}
    kinds = set(db.scalars(select(GeneratedList.kind)))
    assert {"main", "fresh"} <= kinds


def test_generate_fresh_requires_profile(client, db):  # noqa: F811
    h = register(client, "f0@example.com")
    assert client.post("/lists/generate-fresh", headers=h).status_code == 404


def test_new_releases_feed_follows_only_newest_first_and_private(client, db):  # noqa: F811
    h, seed, c1, c2 = setup_user(client, db, "f2@example.com", "FN")
    add_release(db, seed, "Eski Albüm", 10)
    add_release(db, seed, "Yeni Single", 1)
    add_release(db, c1, "Takipsiz", 1)  # c1 profilde değil
    body = client.get("/releases/new", headers=h).json()
    assert [i["title"] for i in body["items"]] == ["Yeni Single", "Eski Albüm"]
    assert body["items"][0]["follow"] == "auto" and body["total"] == 2
    h2 = register(client, "f3@example.com")
    assert client.get("/releases/new", headers=h2).json() == {"items": [], "total": 0}


def test_main_list_reserves_fresh_slot_at_the_end(client, db):  # noqa: F811
    h, seed, c1, c2 = setup_user(client, db, "f4@example.com", "FM")
    base = client.post("/lists/generate", headers=h).json()
    assert base["params"]["fresh_count"] == 0
    assert {i["slot"] for i in base["items"]} <= {"familiar", "unheard", "explore", "far"}

    rel = add_release(db, seed, "Yeni Albüm", 3)
    body = client.post("/lists/generate", headers=h).json()
    assert body["algo_version"] == "list-5" and body["params"]["fresh_count"] == 1
    last = body["items"][-1]
    assert last["slot"] == "fresh" and last["release"]["id"] == rel.id
    assert last["track_id"] is None and last["reasons"][0]["seed_name"] == "FMSeed"
    assert {i["artist_id"] for i in body["items"][:-1]} == {c1.id, c2.id}
    assert "fresh" not in body["params"]["slot_outcomes"]  # fresh slot banditi etkilemez

    # ana listede çıkan yayın Taze listede tekrarlanmaz
    assert client.post("/lists/generate-fresh", headers=h).status_code == 409


def test_fresh_slot_artist_is_removed_from_other_slots(client, db):  # noqa: F811
    from app.models import UserTrackLink  # noqa: F401

    h, seed, c1, c2 = setup_user(client, db, "f5@example.com", "FD")
    client.put(f"/releases/following/{c1.id}", headers=h)  # c1 elle takip, aday da
    add_release(db, c1, "C1 Albüm", 1)
    body = client.post("/lists/generate", headers=h).json()
    by_artist = [i["artist_id"] for i in body["items"]]
    assert by_artist.count(c1.id) == 1
    assert next(i for i in body["items"] if i["artist_id"] == c1.id)["slot"] == "fresh"
    assert c2.id in by_artist
