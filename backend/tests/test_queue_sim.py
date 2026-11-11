
"""queue_sim saf ölçütleri: KESIF_PLANI kabul ölçütleriyle (Çeşitlilik, Tazelik) birebir."""
from app.jobs.queue_sim import (
    artist_gap_violations,
    discovery_positions,
    duplicate_keys,
    gate,
    longest_run,
    max_per_window,
    metrics,
    min_window_distinct,
    overlap,
    queue_url,
    sub_runs,
)


def test_longest_run_ignores_unknown():
    assert longest_run(["a", "a", "b", "a", "a", "a"]) == 3
    assert longest_run([None, None, None, "a"]) == 1
    assert longest_run(["a", None, "a"]) == 1  # bilinmeyen seriyi böler
    assert longest_run([]) == 0


def test_min_window_distinct_is_worst_window():
    labels = ["a", "b", "c", "a", "a", "a"]
    assert min_window_distinct(labels, 3) == 1
    assert min_window_distinct(["a", None, None], 3) == 1  # bilinmeyen tür sayılmaz
    assert min_window_distinct(["a", "b"], 20) == 2  # kısa liste tek pencere


def test_max_per_window():
    assert max_per_window([1, 2, 1, 3, 1, 4], 3) == 2
    assert max_per_window([1, 2, 3, 1], 3) == 1
    assert max_per_window([None, None, None], 3) == 0


def test_artist_gap_violations():
    assert artist_gap_violations([1, 2, 3, 4, 5, 1], 4) == 0  # arada 4 kart var
    assert artist_gap_violations([1, 2, 3, 4, 1], 4) == 1
    assert artist_gap_violations([1, 1, 1], 4) == 2
    assert artist_gap_violations([None, None], 4) == 0


def test_duplicate_keys():
    assert duplicate_keys(["x", "y", "x", None, None, "x"]) == 2


def test_overlap_first_n():
    assert overlap([1, 2, 3], [3, 4, 5]) == 1 / 3
    assert overlap([], []) == 0.0


def _cards(n, artists, mains, subs):
    return [
        {"track": i, "artist": artists[i % len(artists)], "main": mains[i % len(mains)],
         "sub": subs[i % len(subs)], "key": f"k{i}", "source": None}
        for i in range(n)
    ]


def test_metrics_and_gate_pass():
    cards = _cards(
        40, list(range(10)), ["rock", "pop", "jazz", "folk", "rap"],
        ["r1", "p1", "j1", "f1", "h1"],
    )
    m = metrics(cards)
    assert m["cards"] == 40
    assert m["min_main_genres_per_20"] == 5
    assert m["max_same_artist_per_20"] == 2
    assert m["artist_gap_violations"] == 0
    assert m["longest_same_sub_genre_run"] == 1
    assert m["duplicate_songs"] == 0
    assert m["unknown_genre_share"] == 0.0
    g = gate(m, first_overlap=0.1, same_seed_identical=True)
    assert all(ok for ok, _ in g.values())


def test_gate_fails_each_criterion():
    cards = _cards(40, [1, 2], ["rock"], ["r1"])
    cards[3]["key"] = cards[2]["key"]
    m = metrics(cards)
    g = gate(m, first_overlap=0.5, same_seed_identical=False)
    assert {k for k, (ok, _) in g.items() if not ok} == {
        "main_genres_per_20", "same_artist_per_20", "artist_gap", "duplicate_songs",
        "sub_genre_run", "freshness", "determinism",
    }


def test_discovery_share_counts_non_library():
    cards = _cards(3, [1, 2, 3], ["rock"], ["r1"])
    cards[1]["source"] = "probe"
    cards[2]["source"] = "library"
    assert metrics(cards)["discovery_share"] == 0.333


def test_sub_runs_and_discovery_positions_locate_runs_and_sources():
    cards = [
        {"sub": "a"}, {"sub": None, "source": "suggested"}, {"sub": None},
        {"sub": "b", "source": "probe"}, {"sub": "b", "source": "joker"}, {"sub": "c"},
        {"sub": "c", "source": "library"},
    ]
    assert sub_runs(cards) == [
        {"at": 3, "sub": "b", "sources": ["probe", "joker"]},
        {"at": 5, "sub": "c", "sources": ["library", "library"]},
    ]
    assert discovery_positions(cards) == [1, 3, 4]


def test_queue_url_sends_seen_cards_as_recent():
    assert queue_url(100, 2) == "/votes/queue?limit=100&seed=2"
    assert queue_url(20, 1, [7, 9]) == "/votes/queue?limit=20&seed=1&recent=7&recent=9"
