"""Sentetik uçtan uca kapı testleri (saf, veritabanı yok): oy -> profil -> aday -> liste.

Üç topluluk (A: 1–30, B: 101–130, C: 201–230) kendi içinde sık, aralarında seyrek bağlıdır.
Kullanıcı A'yı sever, C'den nefret eder; B tarafsızdır. Tohum sabit, sonuç deterministiktir.
"""
import numpy as np
import pytest

from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.matrix import build_matrix
from app.profile.build import ProfileVote, build_profile
from app.recommend.ppr import score_candidates
from app.recommend.select import select_mmr

GCFG = GraphSettings(_env_file=None)
PCFG = ProfileSettings(_env_file=None, cluster_count=3, cluster_min_artists=2)
RCFG = RecommendSettings(_env_file=None)

A, B, C = range(1, 31), range(101, 131), range(201, 231)


def world():
    rng = np.random.default_rng(7)
    src, dst, w = [], [], []
    for group in (A, B, C):
        g = list(group)
        for a in g:
            for b in rng.choice(g, size=6, replace=False):
                if a != b:
                    src.append(a), dst.append(int(b)), w.append(float(rng.uniform(0.5, 1.0)))
    for a, b in ((A[0], B[0]), (A[1], B[1]), (B[2], C[2])):  # köprüler
        src.append(a), dst.append(b), w.append(0.4)
    return build_matrix(np.array(src), np.array(dst), np.array(w), GCFG)


def votes():
    out, t = [], 0
    for a in list(A)[:8]:  # A'dan 8 sanatçı: 2 Amazing, geri kalanı Great
        t += 1
        out.append(ProfileVote(t, a, 6 if a <= 2 else 5, 1.0 if a <= 2 else 0.7, 1.0))
    for a in list(C)[:3]:  # C'den Awful (sert) ve Bad (yumuşak)
        t += 1
        hard = a == C[0]
        out.append(ProfileVote(t, a, 1 if hard else 2, -1.0 if hard else -0.6, 1.0))
    return out


def run(shuffle=False):
    gm = world()
    vs = votes()
    if shuffle:
        vs = vs[::-1]
    prof = build_profile(vs, gm, PCFG, graph_version=1)
    known = {v.artist_id for v in vs}
    cands = score_candidates(gm, prof, known, RCFG)
    return gm, prof, known, cands, select_mmr(cands, gm, RCFG.list_size, RCFG.mmr_lambda)


def test_end_to_end_is_deterministic_regardless_of_vote_order():
    *_, a = run()
    *_, b = run(shuffle=True)
    assert a == b


def test_recommendations_come_from_liked_community():
    _, _, _, cands, lst = run()
    assert cands and lst
    top = [c.artist_id for c in lst[:10]]
    assert sum(x in A for x in top) >= 8  # sevilen topluluk baskın
    assert not any(x in C for x in top)  # nefret edilen topluluk yok


def test_known_and_avoid_never_listed():
    _, prof, known, _, lst = run()
    listed = {c.artist_id for c in lst}
    assert not listed & known
    assert not listed & {a["artist_id"] for a in prof["avoid"]}


def test_reasons_decompose_score_and_point_to_liked_seeds():
    cfg = RecommendSettings(_env_file=None, reason_count=50)
    gm = world()
    vs = votes()
    prof = build_profile(vs, gm, PCFG, 1)
    liked = {v.artist_id for v in vs if v.score > 0}
    for c in score_candidates(gm, prof, {v.artist_id for v in vs}, cfg):
        assert {r.seed_id for r in c.reasons} <= liked
        assert sum(r.share for r in c.reasons) == pytest.approx(1.0, abs=1e-5)
        assert sum(r.contribution for r in c.reasons) - c.penalty == pytest.approx(c.raw, rel=1e-4)


def test_hard_avoid_blocks_path_through_it():
    gm = world()
    vs = votes()
    prof = build_profile(vs, gm, PCFG, 1)
    hard = {a["artist_id"] for a in prof["avoid"] if a["hard"]}
    assert hard == {C[0]}
    # sert kaçınma düğümü hiç aday olmaz ve bilinenlerden bağımsız olarak dışarıda kalır
    got = {c.artist_id for c in score_candidates(gm, prof, set(), RCFG)}
    assert not got & hard


def _mean_sim(ids, gm):
    from sklearn.preprocessing import normalize

    rows = normalize(gm.matrix[[gm.position(a) for a in ids]], norm="l2")
    sim = (rows @ rows.T).toarray()
    n = len(ids)
    return (sim.sum() - n) / (n * (n - 1))


def test_mmr_lowers_similarity_of_top_picks():
    gm, _, _, cands, lst = run()
    assert len(lst) == RCFG.list_size and len({c.artist_id for c in lst}) == len(lst)
    k = 8
    mmr = _mean_sim([c.artist_id for c in lst[:k]], gm)
    rel = _mean_sim([c.artist_id for c in cands[:k]], gm)
    assert mmr < rel
