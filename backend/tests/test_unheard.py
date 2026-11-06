from datetime import UTC, datetime, timedelta

from app.config import ProfileSettings
from app.profile.scoring import ScoredVote, decay_weight, implicit_negatives, implicit_positives
from app.profile.unheard import UnheardEvt, next_state, resolve

NOW = datetime(2026, 12, 1, tzinfo=UTC)
CFG = ProfileSettings(_env_file=None)


def ue(i, track, state, days_ago=0):
    return UnheardEvt(i, track, state, NOW - timedelta(days=days_ago))


def test_next_state_first_is_pooled_then_presented():
    assert next_state(0) == "pooled"
    assert next_state(1) == "presented"
    assert next_state(5) == "presented"


def test_resolve_counts_presentations_and_expires_at_threshold():
    events = [ue(1, 7, "pooled"), ue(2, 7, "presented"), ue(3, 8, "pooled")]
    got = {s.track_id: s for s in resolve(events, {}, expire_after=3)}
    assert (got[7].state, got[7].presentations) == ("presented", 2)
    assert (got[8].state, got[8].presentations) == ("pooled", 1)

    events.append(ue(4, 7, "presented"))
    got = {s.track_id: s for s in resolve(events, {}, expire_after=3)}
    assert (got[7].state, got[7].presentations) == ("expired", 3)


def test_vote_after_last_event_resolves_track_out_of_pool():
    events = [ue(1, 7, "pooled", 5), ue(2, 7, "presented", 4), ue(3, 7, "presented", 3)]
    voted = {7: NOW - timedelta(days=1)}
    assert resolve(events, voted, expire_after=3) == []


def test_unheard_after_an_older_vote_stays_in_pool():
    events = [ue(1, 7, "pooled", 1)]
    voted = {7: NOW - timedelta(days=9)}
    assert [s.track_id for s in resolve(events, voted, expire_after=3)] == [7]


def test_resolve_is_deterministic_regardless_of_event_order():
    events = [ue(3, 7, "presented"), ue(1, 7, "pooled"), ue(2, 7, "presented"), ue(4, 2, "pooled")]
    assert resolve(events, {}, 3) == resolve(list(reversed(events)), {}, 3)
    assert [s.track_id for s in resolve(events, {}, 3)] == [2, 7]


def test_implicit_negatives_only_for_expired_with_decay_and_config_score():
    events = [ue(1, 7, "pooled", 400), ue(2, 7, "presented", 400), ue(3, 7, "presented", 400),
              ue(4, 8, "pooled", 1)]
    statuses = resolve(events, {}, expire_after=3)
    got = implicit_negatives(statuses, NOW, CFG)
    weight = decay_weight(0, NOW - timedelta(days=400), NOW, CFG)
    assert got == [ScoredVote(7, 0, CFG.unheard_expired_score, weight)]
    assert got[0].score == -0.05 and 0.25 <= got[0].weight < 1.0


def test_implicit_negative_is_not_exempt_from_decay_like_awful():
    old = NOW - timedelta(days=3650)
    assert decay_weight(0, old, NOW, CFG) == CFG.decay_floor
    assert decay_weight(1, old, NOW, CFG) == 1.0


def test_algo_version_bumped():
    assert CFG.profile_algo_version == "profile-3"


def test_vote_at_same_instant_as_last_event_resolves_track():
    events = [ue(1, 7, "pooled")]
    assert resolve(events, {7: NOW}, expire_after=3) == []


def test_implicit_positives_skip_voted_and_use_config_score_with_decay():
    old = NOW - timedelta(days=400)
    got = implicit_positives([(1, old), (2, NOW)], {2}, NOW, CFG)
    assert got == [ScoredVote(1, 0, CFG.like_score, decay_weight(0, old, NOW, CFG))]
    assert got[0].score > 0
