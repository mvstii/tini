from collections import Counter

from app.jobs.coverage_sim import coverage_at, gate, vote_for


def _v(main, sub, vote=4):
    return {"main": main, "sub": sub, "vote": vote}


def test_vote_for_is_deterministic_seeded_and_in_range():
    assert [vote_for(1, t) for t in range(50)] == [vote_for(1, t) for t in range(50)]
    assert any(vote_for(1, t) != vote_for(2, t) for t in range(50))
    counts = Counter(vote_for(7, t) for t in range(5000))
    assert set(counts) == {1, 2, 3, 4, 5, 6}
    assert 0.05 < counts[1] / 5000 < 0.15  # ~%10 Awful


def test_coverage_counts_distinct_and_unknown():
    votes = [_v("rock", "indie"), _v("rock", "punk"), _v("pop", "synth"), _v(None, None)]
    c = coverage_at(votes, 10)
    assert (c["votes"], c["main_genres"], c["sub_genres"], c["unknown_genre"]) == (4, 2, 3, 1)


def test_coverage_only_looks_at_first_n_votes():
    votes = [_v("rock", "indie"), _v("pop", "synth")]
    assert coverage_at(votes, 1)["main_genres"] == 1


def test_hard_avoided_sub_and_main_are_excluded():
    votes = [
        _v("rock", "indie", 6), _v("rock", "punk", 1),   # punk sert kaçınıldı
        _v("metal", "doom", 1), _v("metal", "doom", 1),  # tüm ana tür kaçınıldı
    ]
    c = coverage_at(votes, 10)
    assert c["sub_genres"] == 3 and c["sub_excl_avoided"] == 1
    assert c["main_genres"] == 2 and c["main_excl_avoided"] == 1


def test_gate_requires_enough_votes_and_thresholds():
    many = [_v(f"m{i % 12}", f"s{i % 40}") for i in range(200)]
    assert all(ok for ok, _ in gate(many).values())
    assert not any(ok for ok, _ in gate(many[:30]).values())  # oy yetmiyor: ölçülemez
    narrow = [_v("m1", f"s{i % 40}") for i in range(200)]
    ok = {k: v[0] for k, v in gate(narrow).items()}
    assert ok["main_genres_first_50"] is False and ok["sub_genres_first_200"] is True
