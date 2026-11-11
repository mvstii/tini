"""Parça sanatçısı kuralı: paylaşılan, yoksa kullanıcıya özel bağ."""
from app.profile.track_artists import merge_track_artists


def test_shared_artist_wins_and_private_link_fills_the_gap():
    shared = {1: 10, 2: None, 3: None, 4: 40}
    private = {1: 99, 2: 20}
    assert merge_track_artists(shared, private) == {1: 10, 2: 20, 4: 40}


def test_track_without_any_artist_is_absent():
    assert merge_track_artists({7: None}, {}) == {}
    assert merge_track_artists({}, {}) == {}
