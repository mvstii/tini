from datetime import UTC, datetime, timedelta

from app.config import ProfileSettings
from app.profile.scoring import VoteEvt, current_votes, decay_weight, score_votes

NOW = datetime(2026, 12, 1, tzinfo=UTC)
CFG = ProfileSettings(_env_file=None)


def ev(i, track, vote, days_ago=0):
    return VoteEvt(i, track, vote, NOW - timedelta(days=days_ago))


def test_current_vote_is_last_event_by_id():
    got = current_votes([ev(3, 1, 2), ev(1, 1, 6), ev(2, 2, 4)])
    assert [(e.track_id, e.vote) for e in got] == [(1, 2), (2, 4)]


def test_cold_start_scores_below_threshold():
    scored = score_votes([ev(1, 1, 6), ev(2, 2, 1), ev(3, 3, 3)], NOW, CFG)
    assert [s.score for s in scored] == [1.0, -1.0, -0.15]


def test_deterministic_regardless_of_event_order():
    events = [ev(i, i, 4 + i % 3) for i in range(1, 41)]
    assert score_votes(events, NOW, CFG) == score_votes(list(reversed(events)), NOW, CFG)


def test_normalization_preserves_sign_and_ties():
    # 40 oy: hepsi Good/Great; persentil sonrası aynı kademe aynı skoru alır, işaret pozitif kalır
    events = [ev(i, i, 4 if i <= 30 else 5) for i in range(1, 41)]
    scored = score_votes(events, NOW, CFG)
    goods = {s.score for s in scored if s.vote == 4}
    greats = {s.score for s in scored if s.vote == 5}
    assert len(goods) == 1 and len(greats) == 1
    assert 0 < min(goods) < min(greats)


def test_normalization_blend_zero_equals_cold_start():
    cfg = ProfileSettings(_env_file=None, normalize_blend=0.0)
    events = [ev(i, i, 4) for i in range(1, 41)]
    assert {s.score for s in score_votes(events, NOW, cfg)} == {0.35}


def test_decay_half_life_and_floor():
    assert decay_weight(4, NOW, NOW, CFG) == 1.0
    assert abs(decay_weight(4, NOW - timedelta(days=365), NOW, CFG) - 0.5) < 1e-9
    assert decay_weight(4, NOW - timedelta(days=5000), NOW, CFG) == CFG.decay_floor


def test_awful_does_not_decay():
    assert decay_weight(1, NOW - timedelta(days=5000), NOW, CFG) == 1.0
