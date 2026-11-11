import pytest

from app.config import ProfileSettings
from app.profile.active import order_active, uncertainty

CFG = ProfileSettings(_env_file=None)
REF = [float(i) for i in range(1, 11)]  # 1..10


def test_uncertainty_peaks_at_median_and_falls_to_extremes():
    mid = uncertainty(5.5, REF, 0.75)
    low = uncertainty(1.0, REF, 0.75)
    high = uncertainty(10.0, REF, 0.75)
    assert mid == pytest.approx(1.0)
    assert low < 0.25 and high < 0.25
    assert uncertainty(5.0, REF, 0.75) > uncertainty(2.0, REF, 0.75)


def test_unknown_artist_or_empty_reference_gets_unknown_value():
    assert uncertainty(None, REF, 0.75) == 0.75
    assert uncertainty(3.0, [], 0.75) == 0.75


def test_ties_share_midrank_so_equal_scores_equal_uncertainty():
    ref = [1.0, 2.0, 2.0, 2.0, 9.0]
    assert uncertainty(2.0, ref, 0.5) == uncertainty(2.0, ref, 0.5)
    assert 0.0 <= uncertainty(2.0, ref, 0.5) <= 1.0


def test_order_prefers_uncertain_artists_and_is_deterministic():
    cands = [(1, 10), (2, 20), (3, 30)]
    unc = {10: 0.1, 20: 0.9, 30: 0.5}
    a = order_active(cands, unc, set(), set(), 0, CFG)
    assert a == [2, 3, 1]
    assert a == order_active(list(reversed(cands)), unc, set(), set(), 0, CFG)


def test_pool_bonus_lifts_pooled_track_above_more_uncertain_artist():
    cands = [(1, 10), (2, 20), (3, 30)]
    unc = {10: 0.5, 20: 0.9, 30: 0.4}  # 0.5 + 0.5 bonus > 0.9
    order = order_active(cands, unc, pool={1}, voted_artists=set(), seed=0, cfg=CFG)
    assert order == [1, 2, 3]


def test_voted_artists_go_after_unvoted_and_one_track_per_artist_per_round():
    cands = [(1, 10), (2, 10), (3, 20), (4, 30)]
    unc = {10: 0.9, 20: 0.8, 30: 0.1}
    order = order_active(cands, unc, set(), voted_artists={20}, seed=0, cfg=CFG)
    assert order[:2] == [order[0], 4] and order[0] in (1, 2)  # 10 ve 30'dan birer parça
    assert order[2] == 3 or order[3] == 3
    assert order.index(3) > order.index(4)  # oy almış sanatçı 20 turun sonunda


def test_pooled_track_comes_first_within_its_artist():
    cands = [(1, 10), (2, 10)]
    for seed in range(5):
        assert order_active(cands, {10: 0.5}, pool={2}, voted_artists=set(), seed=seed,
                            cfg=CFG)[0] == 2


def test_unknown_artists_use_config_default():
    cands = [(1, 10), (2, 20)]
    order = order_active(cands, {10: 0.2}, set(), set(), 0, CFG)  # 20 bilinmiyor -> 0.75
    assert order == [2, 1]


def test_diversify_spreads_artists_and_genres_deterministically():
    from app.profile.active import diversify

    # sanatçı 10'un 4 parçası art arda gelirdi; 20/30/40 farklı sanatçı
    order = [1, 2, 3, 4, 5, 6, 7]
    artist_of = {1: 10, 2: 10, 3: 10, 4: 10, 5: 20, 6: 30, 7: 40}
    genre_of = {10: "rock", 20: "rock", 30: "jazz", 40: "pop"}
    cfg = ProfileSettings(_env_file=None, queue_explore_every=0, queue_artist_gap=1,
                          queue_genre_gap=1)
    out = diversify(order, artist_of, genre_of, set(), 0, cfg, 7)
    assert sorted(out) == order
    assert all(artist_of[a] != artist_of[b] for a, b in zip(out, out[1:], strict=False))
    assert all(genre_of[artist_of[a]] != genre_of[artist_of[b]]
               for a, b in zip(out[:4], out[1:4], strict=False))
    assert out == diversify(order, artist_of, genre_of, set(), 0, cfg, 7)


def test_diversify_relaxes_when_one_artist_only_and_respects_limit():
    from app.profile.active import diversify

    out = diversify([1, 2, 3], {1: 10, 2: 10, 3: 10}, {}, set(), 0, CFG, 2)
    assert len(out) == 2 and set(out) <= {1, 2, 3}


def test_diversify_explore_slots_are_seeded_random_and_prefer_pool():
    from app.profile.active import diversify

    order = list(range(1, 13))
    artist_of = {t: t for t in order}
    cfg = ProfileSettings(_env_file=None, queue_explore_every=3, queue_artist_gap=1,
                          queue_genre_gap=0)
    a = diversify(order, artist_of, {}, {9}, 0, cfg, 6)
    assert a[2] == 9  # ilk keşif yuvası havuzdaki parçayı alır
    assert a != order[:6]
    assert a == diversify(order, artist_of, {}, {9}, 0, cfg, 6)
    assert any(diversify(order, artist_of, {}, set(), s, cfg, 6) != a for s in range(1, 10))


def _spread_cands(n=100):
    cands = [(t, 1000 + t) for t in range(n)]  # her parça ayrı sanatçı
    unc = {1000 + t: t / n for t in range(n)}
    return cands, unc


def test_order_without_noise_ignores_seed_when_scores_differ():
    cands, unc = _spread_cands()
    assert order_active(cands, unc, set(), set(), 1, CFG) == order_active(
        cands, unc, set(), set(), 2, CFG
    )


def test_gumbel_noise_refreshes_head_across_seeds_and_stays_deterministic():
    cands, unc = _spread_cands()
    a = order_active(cands, unc, set(), set(), 1, CFG, tau=0.5)
    b = order_active(cands, unc, set(), set(), 2, CFG, tau=0.5)
    assert a == order_active(cands, unc, set(), set(), 1, CFG, tau=0.5)
    assert sorted(a) == sorted(b) == list(range(100))
    assert len(set(a[:20]) & set(b[:20])) / 20 < 0.5
    # Gürültü belirsizliği silmez: baş taraf ortalamada kuyruktan daha belirsizdir.
    mean = lambda ts: sum(unc[1000 + t] for t in ts) / len(ts)  # noqa: E731
    assert mean(a[:20]) > mean(a[-20:])


def test_gumbel_noise_keeps_voted_artists_after_unvoted():
    cands, unc = _spread_cands(20)
    voted = {1000 + t for t in range(10)}
    out = order_active(cands, unc, set(), voted, 3, CFG, tau=0.5)
    assert set(out[:10]) == set(range(10, 20))
