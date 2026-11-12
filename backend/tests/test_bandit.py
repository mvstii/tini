from datetime import UTC, datetime, timedelta

from app.config import RecommendSettings
from app.recommend.bandit import SLOTS, allocate, far_share, slot_shares
from app.recommend.outcomes import ArtistVote, ItemRef, derive_outcomes
from app.recommend.ppr import Candidate
from app.recommend.service import split_slots

CFG = RecommendSettings(_env_file=None)
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_shares_are_prior_below_threshold_and_sum_to_one():
    shares = slot_shares({"familiar": (3, 1)}, CFG, seed=1)  # 4 < 10 sonuç
    assert abs(sum(shares.values()) - 1) < 1e-9
    assert shares["familiar"] > shares["explore"]
    assert shares == slot_shares({}, CFG, seed=99)  # eşik altında tohum etkisiz


def test_shares_deterministic_per_seed_and_shift_toward_winner():
    out = {"familiar": (1, 9), "unheard": (1, 9), "explore": (40, 0)}
    a = slot_shares(out, CFG, seed=7)
    assert a == slot_shares(out, CFG, seed=7)
    assert abs(sum(a.values()) - 1) < 1e-9
    assert a["explore"] > a["familiar"] and a["explore"] > a["unheard"]
    assert all(v >= CFG.slot_floor_share for v in a.values())
    assert any(slot_shares(out, CFG, seed=s) != a for s in range(8, 20))


def test_allocate_sums_to_size_and_respects_availability():
    shares = {"familiar": 0.4, "unheard": 0.35, "explore": 0.25}
    out = allocate(20, shares, {"familiar": 50, "unheard": 50, "explore": 50})
    assert sum(out.values()) == 20 and out == {"familiar": 8, "unheard": 7, "explore": 5}
    capped = allocate(20, shares, {"familiar": 50, "unheard": 0, "explore": 50})
    assert capped["unheard"] == 0 and sum(capped.values()) == 20
    short = allocate(20, shares, {"familiar": 3, "unheard": 2, "explore": 4})
    assert short == {"familiar": 3, "unheard": 2, "explore": 4}
    assert allocate(20, shares, {s: 0 for s in SLOTS}) == {s: 0 for s in SLOTS}


def test_outcomes_success_failure_feedback_and_pending():
    items = [
        ItemRef(1, 1, 10, "familiar", T0),
        ItemRef(1, 2, 20, "familiar", T0),
        ItemRef(1, 3, 30, "unheard", T0),
        ItemRef(1, 4, 40, "explore", T0),
        ItemRef(1, 5, 50, "explore", T0),
    ]
    later = T0 + timedelta(days=1)
    votes = [
        ArtistVote(1, 10, 5, later),
        ArtistVote(2, 20, 2, later),
        ArtistVote(3, 30, 4, T0 - timedelta(days=1)),  # listeden önce: sayılmaz
        ArtistVote(4, 40, 6, later),  # itiraz var -> başarısız
        ArtistVote(5, 50, 3, later),  # Meh: sonuç değil
    ]
    out = derive_outcomes(items, votes, {(1, 4)})
    assert out == {"familiar": (1, 1), "unheard": (0, 0), "explore": (0, 1)}


def test_outcomes_use_latest_vote_after_list():
    items = [ItemRef(1, 1, 10, "familiar", T0)]
    v = [
        ArtistVote(1, 10, 5, T0 + timedelta(hours=1)),
        ArtistVote(2, 10, 1, T0 + timedelta(hours=2)),
    ]
    assert derive_outcomes(items, v, set()) == {"familiar": (0, 1)}


def _cand(a, score):
    return Candidate(a, score, score, 0.0, 0.0, [])


def test_split_slots_pool_first_then_top_fraction_familiar():
    cands = [_cand(1, 0.9), _cand(2, 0.8), _cand(3, 0.7), _cand(4, 0.6), _cand(5, 0.5)]
    out = split_slots(cands, {3: 99}, 0.5)
    assert [c.artist_id for c in out["unheard"]] == [3]
    assert [c.artist_id for c in out["familiar"]] == [1, 2]
    assert [c.artist_id for c in out["explore"]] == [4, 5]


def test_far_share_is_fixed_below_threshold():
    assert far_share({"far": (2, 1)}, CFG, seed=1) == CFG.far_share
    assert far_share({}, CFG, seed=5) == CFG.far_share


def test_far_share_bounded_deterministic_and_follows_far_outcomes():
    liked = {"familiar": (5, 5), "far": (30, 0)}
    disliked = {"familiar": (5, 5), "far": (0, 30)}
    a = far_share(liked, CFG, seed=3)
    assert a == far_share(liked, CFG, seed=3)
    assert any(far_share(liked, CFG, seed=s) != a for s in range(4, 12))
    for s in range(20):
        hi, lo = far_share(liked, CFG, seed=s), far_share(disliked, CFG, seed=s)
        assert CFG.far_floor_share <= lo < hi <= CFG.far_max_share
