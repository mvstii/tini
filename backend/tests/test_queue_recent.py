"""PR-3: queue() `recent` parametresi (istemcide zaten olan parçalar)."""
# ruff: noqa: F811  (sabitler test_queue içe aktarımından gelir; repo kalıbı)
from test_queue import client, db, lib_track, mk_artist, register  # noqa: F401

from app.config import ProfileSettings
from app.profile.active import diversify


def test_recent_tracks_are_excluded_and_remaining_counts_the_rest(client, db):
    h = register(client, "r1@example.com")
    a, b, c = mk_artist(db, "RA"), mk_artist(db, "RB"), mk_artist(db, "RC")
    t1 = lib_track(db, "r1@example.com", "ZZR000000001", a, "Bir")
    t2 = lib_track(db, "r1@example.com", "ZZR000000002", b, "Iki")
    t3 = lib_track(db, "r1@example.com", "ZZR000000003", c, "Uc")
    r = client.get(f"/votes/queue?recent={t1.id}&recent={t2.id}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert [i["track"] for i in body["items"]] == [t3.id]
    assert body["remaining"] == 1


def test_without_recent_behaves_as_before(client, db):
    h = register(client, "r2@example.com")
    a, b = mk_artist(db, "RD"), mk_artist(db, "RE")
    lib_track(db, "r2@example.com", "ZZR000000011", a, "Bir")
    lib_track(db, "r2@example.com", "ZZR000000012", b, "Iki")
    body = client.get("/votes/queue", headers=h).json()
    assert len(body["items"]) == 2 and body["remaining"] == 2


def test_too_many_recent_is_422_and_unknown_ids_are_harmless(client, db):
    h = register(client, "r3@example.com")
    a = mk_artist(db, "RF")
    t = lib_track(db, "r3@example.com", "ZZR000000021", a, "Bir")
    too_many = "&".join(f"recent={n}" for n in range(1, ProfileSettings().queue_recent_max + 2))
    assert client.get(f"/votes/queue?{too_many}", headers=h).status_code == 422
    ok = client.get("/votes/queue?recent=999999999", headers=h)
    assert ok.status_code == 200 and [i["track"] for i in ok.json()["items"]] == [t.id]
    assert client.get("/votes/queue?recent=abc", headers=h).status_code == 422


def test_diversify_gap_window_starts_with_prior_artists():
    cfg = ProfileSettings(queue_artist_gap=2, queue_genre_gap=0, queue_explore_every=0)
    order = [1, 2, 3]
    artist_of = {1: 10, 2: 20, 3: 30}
    base = diversify(order, artist_of, {}, set(), 0, cfg, 3)
    assert base == [1, 2, 3]
    # İstemcide son iki parça 10 ve 20 sanatçısındaysa, 1 ve 2 ilk sıradan itilir.
    out = diversify(order, artist_of, {}, set(), 0, cfg, 3, prior_artists=[20, 10])
    assert out[0] == 3
    assert sorted(out) == [1, 2, 3]
