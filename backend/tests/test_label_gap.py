"""label_gap saf sayımı: türsüz sanatçıların nedenlere bölünmesi."""
from app.jobs.label_gap import artistless_breakdown, label_gap


def test_label_gap_splits_artists_by_cause_and_counts_tracks():
    track_artists = [1, 1, 2, 3, 3, 3, 4, None]
    attempted = {2, 3, 4}
    tags = {3: [("zzz unknown tag", 80), ("another oddity", 40)], 4: [("rock", 90)]}
    out = label_gap(track_artists, attempted, tags, with_mbid={3, 4}, top=1)
    assert out["never_tried"] == {"artists": 1, "tracks": 2, "no_mbid": 1}
    assert out["tried_no_tags"] == {"artists": 1, "tracks": 1, "no_mbid": 1}
    assert out["tags_unmapped"] == {"artists": 1, "tracks": 3, "no_mbid": 0}
    assert out["labeled"] == {"artists": 1, "tracks": 1, "no_mbid": 0}
    assert out["tracks_without_artist"] == 1
    assert len(out["top_unmapped_tags"]) == 1 and out["top_unmapped_tags"][0][1] == 1


def test_artistless_breakdown_puts_each_track_in_one_cause():
    rows = [
        ("empty", "empty", True),   # bağ varsa başka gruba girmez
        (None, None, False),
        ("error", None, False),
        ("ok", None, False),
        ("empty", None, False),
        ("empty", "empty", False),
        ("empty", "error", False),
        ("empty", "error", False),
    ]
    out = artistless_breakdown(rows)
    assert out == {
        "user_linked": 1, "mb_never_tried": 1, "mb_error": 1, "mb_ok_no_artist": 1,
        "mb_empty_lastfm_never_tried": 1, "mb_empty_lastfm_empty": 1, "mb_empty_lastfm_error": 2,
    }
    assert sum(out.values()) == len(rows)
    assert sum(artistless_breakdown([]).values()) == 0


def test_label_gap_empty_library():
    out = label_gap([], set(), {}, set())
    assert out["labeled"]["artists"] == 0 and out["top_unmapped_tags"] == []
