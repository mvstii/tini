import numpy as np
import pytest

from app.config import GraphSettings, RecommendSettings
from app.graph.matrix import build_matrix
from app.recommend import ppr
from app.recommend.ppr import explain, score_candidates

GCFG = GraphSettings(_env_file=None)
CFG = RecommendSettings(_env_file=None)


def graph(edges):
    src, dst, w = zip(*edges, strict=True)
    return build_matrix(np.array(src), np.array(dst), np.array(w), GCFG)


def profile(pos=(), anchors=(), avoid=()):
    return {
        "clusters": [{"id": 0, "weight": 1.0,
                      "artists": [{"artist_id": a, "affinity": f} for a, f in pos]}],
        "unclustered": [],
        "anchors": [{"artist_id": a, "weight": 1.0} for a in anchors],
        "avoid": [{"artist_id": a, "strength": s, "hard": h} for a, s, h in avoid],
    }


# 1 ─ 10 ─ 12 zinciri, 1 ─ 11, 2 ─ 11 ; 20 ayrı bileşen
EDGES = [(1, 10, 0.9), (10, 12, 0.8), (1, 11, 0.3), (2, 11, 0.9), (20, 21, 0.5)]


def by_id(cands):
    return {c.artist_id: c for c in cands}


def test_neighbors_of_anchor_ranked_and_seeds_excluded():
    got = score_candidates(graph(EDGES), profile([(1, 0.7)], anchors=[1]), set(), CFG)
    ids = [c.artist_id for c in got]
    assert 1 not in ids and 20 not in ids and 21 not in ids  # tohum ve ayrı bileşen yok
    assert ids.index(10) < ids.index(11)  # güçlü komşu önce


def test_score_is_sum_of_seed_contributions():
    cfg = RecommendSettings(_env_file=None, reason_count=10)
    got = by_id(score_candidates(graph(EDGES), profile([(1, 0.7), (2, 0.35)]), set(), cfg))
    c = got[11]  # iki tohumdan da erişilir
    assert {r.seed_id for r in c.reasons} == {1, 2}
    assert sum(r.contribution for r in c.reasons) == pytest.approx(c.raw, rel=1e-5)
    assert sum(r.share for r in c.reasons) == pytest.approx(1.0)
    assert c.penalty == 0.0


def test_reasons_limited_flag_anchor_and_sorted_by_share():
    got = by_id(score_candidates(graph(EDGES), profile([(1, 0.7), (2, 0.35)], anchors=[2]),
                                 set(), RecommendSettings(_env_file=None, reason_count=1)))
    (r,) = got[11].reasons
    assert r.is_anchor and r.seed_id == 2  # çapa ×2 boost + güçlü kenar


def test_known_artists_excluded():
    got = score_candidates(graph(EDGES), profile([(1, 0.7)]), {10}, CFG)
    assert 10 not in [c.artist_id for c in got]


def test_hard_avoid_prunes_node_and_blocks_propagation():
    base = by_id(score_candidates(graph(EDGES), profile([(1, 0.7)]), set(), CFG))
    assert 12 in base  # 1 → 10 → 12
    pruned = by_id(
        score_candidates(graph(EDGES), profile([(1, 0.7)], avoid=[(10, 1.0, True)]), set(), CFG)
    )
    assert 10 not in pruned and 12 not in pruned  # düğüm budandı, içinden yayılım yok
    assert 11 in pruned


def test_soft_avoid_penalizes_and_is_excluded():
    edges = EDGES + [(3, 11, 0.2), (3, 30, 0.9)]
    base = by_id(score_candidates(graph(edges), profile([(1, 0.7)]), set(), CFG))
    pen = by_id(score_candidates(graph(edges), profile([(1, 0.7)], avoid=[(3, 0.6, False)]),
                                 set(), CFG))
    assert 3 not in pen  # kaçınma sanatçısı aday olmaz
    assert pen[11].raw < base[11].raw
    assert pen[11].penalty > 0
    assert 30 not in pen  # yalnızca cezalı yoldan erişilen aday pozitif skor almaz


def test_novelty_leaf_beats_hub_multiplier():
    # 100 merkez (derece 4), 101 yaprak (derece 1); ikisi de 1'e komşu
    edges = [(1, 100, 0.5), (1, 101, 0.5), (100, 102, 0.5), (100, 103, 0.5), (100, 104, 0.5)]
    got = by_id(score_candidates(graph(edges), profile([(1, 0.7)]), set(), CFG))
    assert got[101].novelty > got[100].novelty
    for c in got.values():
        assert c.score == pytest.approx(c.raw * (1 + CFG.novelty_gamma * c.novelty), rel=1e-5)


def test_gamma_zero_score_equals_raw():
    cfg = RecommendSettings(_env_file=None, novelty_gamma=0.0)
    for c in score_candidates(graph(EDGES), profile([(1, 0.7)]), set(), cfg):
        assert c.score == pytest.approx(c.raw)


def test_no_seed_in_graph_returns_empty():
    assert score_candidates(graph(EDGES), profile([(999, 0.7)]), set(), CFG) == []


def test_deterministic_regardless_of_seed_order():
    a = score_candidates(graph(EDGES), profile([(1, 0.7), (2, 0.35)]), set(), CFG)
    b = score_candidates(graph(EDGES[::-1]), profile([(2, 0.35), (1, 0.7)]), set(), CFG)
    assert a == b


def test_top_n_limit():
    cfg = RecommendSettings(_env_file=None, candidate_top_n=1)
    assert len(score_candidates(graph(EDGES), profile([(1, 0.7)]), set(), cfg)) == 1


def test_explain_without_artists_skips_propagation(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("boş kümede PPR çalışmamalı")

    monkeypatch.setattr(ppr, "propagate", boom)
    assert explain(graph(EDGES), profile([(1, 0.7)]), set(), CFG) == {}


def test_explain_matches_score_candidates_for_same_artist():
    gm, prof = graph(EDGES), profile([(1, 0.7)])
    cand = by_id(score_candidates(gm, prof, set(), CFG))[10]
    score, reasons = explain(gm, prof, {10}, CFG)[10]
    assert score == pytest.approx(cand.score)
    assert [r.seed_id for r in reasons] == [r.seed_id for r in cand.reasons]


def test_shared_propagation_is_reused_and_gives_same_result(monkeypatch):
    gm, prof = graph(EDGES), profile([(1, 0.7)], anchors=[1])
    prop = ppr.propagate(gm, prof, CFG)
    want_explain = explain(gm, prof, {10}, CFG)
    want_cands = score_candidates(gm, prof, set(), CFG)

    def boom(*a, **k):
        raise AssertionError("paylaşılan yayılım varken PPR yeniden çalışmamalı")

    monkeypatch.setattr(ppr, "propagate", boom)
    assert explain(gm, prof, {10}, CFG, prop) == want_explain
    assert score_candidates(gm, prof, set(), CFG, prop) == want_cands
