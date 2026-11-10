import pytest

from app.config import ProfileSettings
from app.profile.sampler import (
    SOURCES,
    Cand,
    cell_scores,
    genre_targets,
    gumbel_order,
    rerank,
    source_mix,
)

CFG = ProfileSettings(_env_file=None)
ALL = dict.fromkeys(SOURCES, True)


# --- source_mix ---


def test_mix_warm_and_mature_endpoints_sum_to_size():
    warm = source_mix(0, 20, ALL, CFG)
    mature = source_mix(500, 20, ALL, CFG)
    assert warm == {"library": 8, "neighborhood": 2, "probe": 8, "joker": 2}
    assert mature == {"library": 6, "neighborhood": 8, "probe": 4, "joker": 2}
    for size in (1, 7, 19, 100):
        for votes in (0, 60, 125, 999):
            assert sum(source_mix(votes, size, ALL, CFG).values()) == size


def test_mix_redistributes_empty_source_and_never_shrinks_batch():
    got = source_mix(0, 20, {**ALL, "library": False, "probe": False}, CFG)
    assert got["library"] == 0 and got["probe"] == 0 and sum(got.values()) == 20
    none = source_mix(0, 20, dict.fromkeys(SOURCES, False), CFG)
    assert none["library"] == 20 and sum(none.values()) == 20


# --- cell_scores / gumbel_order ---


def test_cell_score_prefers_less_shown_cells_and_liked_genres():
    cells = {("rock", "grunge", "top"): 0, ("rock", "punk", "top"): 8}
    s = cell_scores(cells, {"rock": 0.2}, 1.0)
    assert s[("rock", "grunge", "top")] > s[("rock", "punk", "top")]
    s2 = cell_scores({("rap", None, "top"): 0}, {"rap": 0.5, "rock": 0.0}, 1.0)
    assert s2[("rap", None, "top")] == pytest.approx(1.5)


def test_gumbel_tau_zero_is_pure_score_order_and_seeded_otherwise():
    scores = {"a": 1.0, "b": 3.0, "c": 2.0}
    assert gumbel_order(scores, 0.0, 1) == ["b", "c", "a"]
    assert gumbel_order(scores, 0.0, 99) == ["b", "c", "a"]
    assert gumbel_order(scores, 1.0, 5) == gumbel_order(scores, 1.0, 5)
    orders = {tuple(gumbel_order(scores, 5.0, s)) for s in range(30)}
    assert len(orders) > 1


# --- genre_targets ---


def test_targets_mix_user_share_and_uniform_and_sum_to_one():
    t = genre_targets({"rock": 3.0, "rap": 1.0}, ["rock", "rap", "pop"], 0.3)
    assert sum(t.values()) == pytest.approx(1.0)
    assert t["rock"] > t["rap"] > t["pop"] > 0
    flat = genre_targets({}, ["rock", "rap"], 0.0)
    assert flat == {"rock": 0.5, "rap": 0.5}


# --- rerank ---


def c(track, artist, genre, sub=None, source="library", key=None):
    return Cand(track, artist, genre, sub, source, key)


def test_rerank_respects_artist_gap_and_unique_song_key():
    cands = [c(1, 1, "rock", "a"), c(2, 1, "rock", "b"), c(3, 2, "rock", "c", key="s"),
             c(4, 3, "rock", "d", key="s"), c(5, 4, "rock", "e"), c(6, 5, "rock", "f")]
    out = rerank(cands, {"rock": 1.0}, 10, CFG)
    ids = [x.track for x in out]
    assert ids.index(1) == 0 and ids.index(2) > ids.index(1) + 1  # sanatçı 1 hemen tekrar etmez
    assert not ({3, 4} <= set(ids))  # aynı şarkı bir kez


def test_rerank_calibrates_and_does_not_exhaust_minority_first():
    cands = [c(i, i, "rock", f"r{i}") for i in range(10)] + [
        c(100 + i, 100 + i, "jazz_blues", f"j{i}") for i in range(10)
    ]
    out = rerank(cands, {"rock": 0.5, "jazz_blues": 0.5}, 10, CFG)
    genres = [x.genre for x in out]
    assert genres.count("rock") == 5 and genres.count("jazz_blues") == 5
    assert all(a != b for a, b in zip(genres, genres[1:], strict=False))


def test_rerank_no_consecutive_same_sub_then_relaxes():
    cands = [c(i, i, "rock", "same") for i in range(4)]
    out = rerank(cands, {"rock": 1.0}, 4, CFG)
    assert len(out) == 4  # tek alt tür kalsa da parti küçülmez


def test_rerank_prior_artists_and_similarity_window():
    cands = [c(1, 7, "rock", "a"), c(2, 8, "rock", "b"), c(3, 9, "rock", "c")]
    out = rerank(cands, {"rock": 1.0}, 3, CFG, prior_artists=[7])
    assert out[0].track != 1
    sims = {frozenset((8, 9)): 0.99}
    out2 = rerank(
        [c(2, 8, "rock", "b"), c(3, 9, "rock", "c"), c(4, 10, "rock", "d")], {"rock": 1.0}, 3,
        CFG, sim=lambda a, b: sims.get(frozenset((a, b)), 0.0),
    )
    assert [x.track for x in out2] == [2, 4, 3]


def test_rerank_is_deterministic_and_limit_bounded():
    cands = [c(i, i, "rock" if i % 2 else "rap", f"s{i}") for i in range(12)]
    t = {"rock": 0.5, "rap": 0.5}
    assert rerank(cands, t, 7, CFG) == rerank(cands, t, 7, CFG)
    assert len(rerank(cands, t, 7, CFG)) == 7


def test_queue_sim_metrics():
    from app.jobs.queue_sim import longest_run, metrics, overlap, window_distinct

    assert longest_run(["a", "a", "b", "a", "a", "a"]) == 3
    assert window_distinct(["a", "b", "a", "b"], 2) == 2.0
    assert overlap([1, 2, 3], [3, 4, 5]) == 1 / 3
    m = metrics([1, 2, 3], {1: 10, 2: 10, 3: 11}, {10: ("rock", "x"), 11: ("pop", "y")},
                [None, "probe", "joker"])
    assert m["artist_repeats"] == 1 and m["longest_same_genre_run"] == 2
    assert m["discovery_share"] == 0.667
