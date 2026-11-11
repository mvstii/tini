"""Parça sanatçısı kuralı: paylaşılan, yoksa kullanıcıya özel bağ."""
from app.profile.track_artists import merge_track_artists


def test_shared_artist_wins_and_private_link_fills_the_gap():
    shared = {1: 10, 2: None, 3: None, 4: 40}
    private = {1: 99, 2: 20}
    assert merge_track_artists(shared, private) == {1: 10, 2: 20, 4: 40}


def test_track_without_any_artist_is_absent():
    assert merge_track_artists({7: None}, {}) == {}
    assert merge_track_artists({}, {}) == {}


# --- Kuyruk aynı kuralı kullanır (SPEC 5c-3) ---
# ruff: noqa: E402, F811  (sabitler test_queue içe aktarımından gelir; repo kalıbı)
from sqlalchemy import select
from test_queue import client, db, lib_track, mk_artist, register  # noqa: F401

from app.config import ProfileSettings
from app.models import User, UserTrackArtist
from app.profile.sampled_queue import _rerank_items


def link(db, email, track, artist):
    u = db.scalar(select(User).where(User.email == email))
    db.add(UserTrackArtist(user_id=u.id, track_id=track.id, artist_id=artist.id,
                           confidence=0.9, method="lastfm"))
    db.flush()
    return u


def test_queue_treats_user_linked_track_as_resolved(client, db):
    """Kademe B bağlı parça `unresolved`'a düşmez: gerçekten sanatçısızlardan önce gelir."""
    email = "ta1@example.com"
    h = register(client, email)
    for k in range(3):
        lib_track(db, email, f"ZZTA1U{k:06d}", None, f"Sanatcisiz {k}")
    linked = lib_track(db, email, "ZZTA1L000001", None, "Bagli")
    link(db, email, linked, mk_artist(db, "TA1 Bagli"))
    for seed in range(5):
        body = client.get(f"/votes/queue?seed={seed}", headers=h).json()
        assert body["items"][0]["track"] == linked.id, seed
        assert len(body["items"]) == 4


def test_rerank_spaces_tracks_sharing_a_user_linked_artist(db):
    """Sanatçı aralığı, sanatçısı yalnız kullanıcıya özel bağdan gelen parçalara da uygulanır."""
    email = "ta2@example.com"
    db.add(User(email=email, password_hash="x"))
    db.flush()
    same = mk_artist(db, "TA2 Ortak")
    a = lib_track(db, email, "ZZTA2L000001", None, "Bagli Bir")
    b = lib_track(db, email, "ZZTA2L000002", None, "Bagli Iki")
    link(db, email, a, same)
    u = link(db, email, b, same)
    others = [
        lib_track(db, email, f"ZZTA2O{k:06d}", mk_artist(db, f"TA2 Diger {k}"), f"Diger {k}")
        for k in range(4)
    ]
    items = [{"track": t.id, "title": f"T{t.id}", "artists": ["X"], "pool": "library"}
             for t in [a, b, *others]]
    cfg = ProfileSettings(_env_file=None)
    out = [i["track"] for i in _rerank_items(db, u, items, [], [], 6, cfg)]
    assert len(out) == 6
    assert abs(out.index(a.id) - out.index(b.id)) >= 4
