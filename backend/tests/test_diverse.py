import numpy as np
from scipy import sparse

from app.graph.matrix import GraphMatrix
from app.recommend.diverse import cap_share, community_labels, home_weights, pick_far
from app.recommend.ppr import Candidate


def cand(a, score):
    return Candidate(a, score, score, 0.0, 0.0, [])


# 0-9 topluluk A, 10-19 B, 20-29 C: kendi içlerinde tam bağlı
LABELS = {a: a // 10 for a in range(30)}


def three_blocks() -> GraphMatrix:
    m = np.zeros((30, 30), dtype=np.float32)
    for b in range(3):
        m[b * 10:(b + 1) * 10, b * 10:(b + 1) * 10] = 1.0
    np.fill_diagonal(m, 0)
    return GraphMatrix(np.arange(30, dtype=np.int64), sparse.csr_matrix(m))


def test_community_labels_split_blocks_and_are_deterministic():
    a = community_labels(three_blocks(), 3, 0)
    assert a == community_labels(three_blocks(), 3, 0)
    assert len({a[i] for i in range(10)}) == 1 and a[0] != a[10] != a[20]


def test_home_weights_sum_positive_seed_weight_per_community():
    got = home_weights([(1, 1.0), (2, 0.5), (11, 0.2), (12, -1.0)], LABELS)
    assert got == {0: 1.5, 1: 0.2}


def test_pick_far_skips_home_and_takes_best_per_community_in_round_robin():
    home = {0: 5.0, 1: 0.3}
    cands = [cand(1, 9), cand(2, 8), cand(11, 7), cand(12, 6), cand(21, 5), cand(22, 4)]
    got = pick_far(cands, LABELS, home, 3, exclude_top=1)
    # topluluk 0 hariç; ev ağırlığı düşük olan C(0.0) önce, sonra B
    assert [c.artist_id for c in got] == [21, 11, 22]


def test_pick_far_empty_when_no_candidates_outside_home():
    assert pick_far([cand(1, 1)], LABELS, {0: 1.0}, 2, exclude_top=1) == []


def test_cap_share_limits_one_community_and_backfills_from_others():
    chosen = [cand(a, 10 - a) for a in range(6)]  # hepsi topluluk A
    spare = [cand(11, 3), cand(21, 2), cand(2, 1.5)]
    out = cap_share(chosen, spare, LABELS, size=8, max_share=0.5)  # tavan 4
    ids = [c.artist_id for c in out]
    assert sum(1 for i in ids if i < 10) == 4
    assert 11 in ids and 21 in ids and len(ids) == len(chosen)


def test_cap_share_noop_when_under_cap():
    chosen = [cand(1, 3), cand(11, 2), cand(21, 1)]
    assert cap_share(chosen, [], LABELS, size=6, max_share=0.5) == chosen
