import numpy as np
import pytest

from app.config import GraphSettings
from app.graph.matrix import build_matrix
from app.recommend.ppr import Candidate
from app.recommend.select import select_mmr

GCFG = GraphSettings(_env_file=None)


def graph(edges):
    src, dst, w = zip(*edges, strict=True)
    return build_matrix(np.array(src), np.array(dst), np.array(w), GCFG)


def cand(a, score):
    return Candidate(a, score, score, 0.0, 0.0, [])


# 1,2 aynı hub'lara bağlı (çok benzer); 3 başka hub'lara bağlı
EDGES = [(1, 100, 0.9), (1, 101, 0.9), (2, 100, 0.9), (2, 101, 0.9), (3, 200, 0.9), (3, 201, 0.9)]


def ids(cands):
    return [c.artist_id for c in cands]


def test_lambda_one_is_pure_relevance_order():
    gm = graph(EDGES)
    cs = [cand(1, 3.0), cand(2, 2.0), cand(3, 1.0)]
    assert ids(select_mmr(cs, gm, 3, 1.0)) == [1, 2, 3]


def test_diversity_promotes_dissimilar_candidate():
    gm = graph(EDGES)
    cs = [cand(1, 3.0), cand(2, 2.9), cand(3, 2.0)]
    assert ids(select_mmr(cs, gm, 3, 0.5)) == [1, 3, 2]


def test_size_limit_and_no_duplicates():
    gm = graph(EDGES)
    cs = [cand(1, 3.0), cand(2, 2.0), cand(3, 1.0)]
    got = ids(select_mmr(cs, gm, 2, 0.7))
    assert len(got) == 2 and len(set(got)) == 2
    assert len(select_mmr(cs, gm, 10, 0.7)) == 3


def test_empty_and_zero_size():
    gm = graph(EDGES)
    assert select_mmr([], gm, 5, 0.7) == []
    assert select_mmr([cand(1, 1.0)], gm, 0, 0.7) == []


def test_deterministic():
    gm = graph(EDGES)
    cs = [cand(1, 3.0), cand(2, 2.9), cand(3, 2.0)]
    assert select_mmr(cs, gm, 3, 0.6) == select_mmr(list(cs), gm, 3, 0.6)


def test_first_pick_is_top_scorer_for_any_lambda():
    gm = graph(EDGES)
    cs = [cand(1, 3.0), cand(2, 2.9), cand(3, 2.0)]
    for lam in (0.2, 0.7, 1.0):
        assert select_mmr(cs, gm, 1, lam)[0].artist_id == pytest.approx(1)


def test_gumbel_noise_is_seeded_and_changes_pick_across_seeds():
    edges = [(a, 100 + a, 0.9) for a in range(1, 13)]  # birbirine benzemeyen 12 aday
    gm = graph(edges)
    cands = [cand(a, 1.0 - 0.01 * a) for a in range(1, 13)]
    base = ids(select_mmr(cands, gm, 4, 0.6))
    assert ids(select_mmr(cands, gm, 4, 0.6, tau=0.0, seed=9)) == base  # tau=0: gürültü yok
    a = ids(select_mmr(cands, gm, 4, 0.6, tau=0.1, seed=1))
    assert a == ids(select_mmr(cands, gm, 4, 0.6, tau=0.1, seed=1))
    picks = {tuple(ids(select_mmr(cands, gm, 4, 0.6, tau=0.1, seed=s))) for s in range(1, 9)}
    assert len(picks) > 1
