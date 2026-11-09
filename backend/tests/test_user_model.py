import pytest

from app.config import ProfileSettings, RecommendSettings
from app.profile.build import ProfileVote, build_profile
from app.profile.exposure import ExposureEvt, exposure_map
from app.recommend.genre_bandit import genre_outcomes, sample_genre_scores
from app.recommend.genres import GENRES

PCFG = ProfileSettings(_env_file=None)
RCFG = RecommendSettings(_env_file=None)
ARMS = list(GENRES)
GENRE_OF = {1: ("jazz_blues", "jazz"), 2: ("rock", "grunge"), 3: ("rock", None)}


def pv(track, artist, vote):
    return ProfileVote(track, artist, vote, 0.0, 1.0)


# --- exposure_map ---


def test_exposure_map_counts_cells_and_unknown_band_and_genre():
    events = [
        ExposureEvt(10, 1, "vote"),
        ExposureEvt(11, 1, "vote"),
        ExposureEvt(12, 2, "unheard"),
        ExposureEvt(13, 99, "later"),  # tür bilinmiyor
        ExposureEvt(14, None, "vote"),  # sanatçı çözülmemiş
    ]
    got = exposure_map(events, GENRE_OF, {10: "top"})
    assert got[("jazz_blues", "jazz", "top")] == {"vote": 1, "unheard": 0, "later": 0}
    assert got[("jazz_blues", "jazz", "unknown")]["vote"] == 1
    assert got[("rock", "grunge", "unknown")]["unheard"] == 1
    assert got[("unknown", "unknown", "unknown")] == {"vote": 1, "unheard": 0, "later": 1}


def test_exposure_map_is_order_independent_and_rejects_bad_kind():
    ev = [ExposureEvt(1, 1, "vote"), ExposureEvt(2, 2, "later")]
    assert exposure_map(ev, GENRE_OF, {}) == exposure_map(list(reversed(ev)), GENRE_OF, {})
    with pytest.raises(ValueError):
        exposure_map([ExposureEvt(1, 1, "x")], GENRE_OF, {})


# --- genre_bandit ---


def test_genre_outcomes_counts_good_bad_and_ignores_meh():
    got = genre_outcomes([("jazz_blues", 1), ("jazz_blues", 2), ("jazz_blues", 3), ("rock", 5)])
    assert got == {"jazz_blues": (0, 2), "rock": (1, 0)}


def test_bad_genre_shrinks_but_never_reaches_zero():
    outcomes = {"jazz_blues": (0, 40), "rock": (10, 0)}
    shares = [sample_genre_scores(outcomes, ARMS, s, RCFG)["jazz_blues"] for s in range(200)]
    assert max(shares) < 0.1
    assert min(shares) >= RCFG.genre_floor_share
    neutral = sample_genre_scores({}, ARMS, 0, RCFG)
    assert sum(sample_genre_scores(outcomes, ARMS, 0, RCFG).values()) == pytest.approx(1.0)
    assert sum(neutral.values()) == pytest.approx(1.0)


def test_untried_genre_is_optimistic_vs_disliked_genre():
    outcomes = {"jazz_blues": (1, 8)}
    seeds = range(300)
    untried = sum(sample_genre_scores(outcomes, ARMS, s, RCFG)["reggae"] for s in seeds)
    disliked = sum(sample_genre_scores(outcomes, ARMS, s, RCFG)["jazz_blues"] for s in seeds)
    assert untried > disliked


def test_sampling_is_deterministic_and_seed_sensitive():
    outcomes = {"rock": (3, 1), "rap": (0, 2)}
    a = sample_genre_scores(outcomes, ARMS, 7, RCFG)
    assert a == sample_genre_scores(outcomes, list(reversed(ARMS)), 7, RCFG)
    assert a != sample_genre_scores(outcomes, ARMS, 8, RCFG)


def test_floor_times_arms_over_one_is_rejected():
    cfg = RecommendSettings(_env_file=None, genre_floor_share=0.5)
    with pytest.raises(ValueError):
        sample_genre_scores({}, ARMS, 0, cfg)


# --- profile genres block ---


def test_profile_genres_block_is_smoothed_and_counts_only_real_votes():
    votes = [
        pv(1, 1, 6), pv(2, 1, 4), pv(3, 1, 1),  # caz: 2 pozitif, 1 negatif
        pv(4, 2, 5),  # rock/grunge
        pv(5, 3, 2),  # rock (alt tür yok): negatif
        pv(6, 99, 5),  # etiketsiz
        ProfileVote(7, 1, 0, 0.25, 1.0),  # örtük (vote 0): sayılmaz
    ]
    g = build_profile(votes, None, PCFG, None, GENRE_OF)["genres"]
    main = {x["genre"]: x for x in g["main"]}
    assert main["jazz_blues"]["positive"] == 2 and main["jazz_blues"]["negative"] == 1
    assert main["rock"]["positive"] == 1 and main["rock"]["negative"] == 1
    assert g["unlabeled_votes"] == 1 and g["main_positive_total"] == 3
    denom = 3 + 1.0 * len(GENRES)
    assert main["jazz_blues"]["share"] == pytest.approx((2 + 1) / denom, abs=1e-6)
    assert {x["genre"] for x in g["sub"]} == {"jazz", "grunge"}


def test_profile_without_genre_map_has_empty_genres_and_version_4():
    body = build_profile([pv(1, 1, 5)], None, PCFG, None)
    assert body["algo_version"] == "profile-4"
    assert body["genres"]["main"] == [] and body["genres"]["unlabeled_votes"] == 1
