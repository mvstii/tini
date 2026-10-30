"""PPR aday skoru (saf): profil + grafik matrisi + bilinen sanatçılar -> gerekçeli adaylar.

Skor, tohum vektörlerine göre doğrusaldır: ham skor = Σ_i w_i · r_i, r_i = (1-α) Σ_k α^k S^k e_i.
Bu yüzden her adayın skoru tohum katkılarının toplamıdır; gerekçe bu toplamdan okunur, sonradan
uydurulmaz. Awful (sert kaçınma) düğümleri her adımda maskelenir (budanır, içinden yayılım olmaz);
Bad/Meh gibi yumuşak kaçınma sanatçıları negatif tohumdur (ceza). Yenilik bonusu adaya özgü bir
çarpandır, payları değiştirmez.
"""
from dataclasses import dataclass

import numpy as np

from app.config import RecommendSettings
from app.graph.matrix import GraphMatrix


@dataclass(frozen=True)
class Reason:
    seed_id: int
    share: float  # bu tohumun pozitif katkılar içindeki payı (0–1)
    contribution: float  # w_i · r_i[aday]
    is_anchor: bool


@dataclass(frozen=True)
class Candidate:
    artist_id: int
    score: float  # nihai (yenilik dahil)
    raw: float  # Σ katkılar (ceza dahil)
    novelty: float
    penalty: float  # kaçınma tohumlarından gelen ceza (>= 0, ham ölçekte)
    reasons: list[Reason]


def _seeds(profile: dict, cfg: RecommendSettings) -> tuple[dict[int, float], dict[int, float]]:
    """(pozitif tohum -> ağırlık, negatif tohum -> ağırlık<0). Sert kaçınma tohum olmaz."""
    anchors = {a["artist_id"] for a in profile.get("anchors", [])}
    pos: dict[int, float] = {}
    for c in profile.get("clusters", []):
        for a in c["artists"]:
            pos[a["artist_id"]] = a["affinity"]
    for a in profile.get("unclustered", []):
        pos[a["artist_id"]] = a["affinity"]
    pos = {k: v * (cfg.anchor_boost if k in anchors else 1.0) for k, v in pos.items()}
    neg = {
        a["artist_id"]: -cfg.bad_penalty_beta * a["strength"]
        for a in profile.get("avoid", [])
        if not a["hard"]
    }
    return pos, neg


def _top(weights: dict[int, float], limit: int, sign: int) -> list[tuple[int, float]]:
    return sorted(weights.items(), key=lambda kv: (-sign * kv[1], kv[0]))[:limit]


def _novelty(gm: GraphMatrix) -> np.ndarray:
    deg = np.diff(gm.matrix.indptr)
    srt = np.sort(deg)
    pct = (np.searchsorted(srt, deg, "left") + np.searchsorted(srt, deg, "right")) / (2 * deg.size)
    return 1.0 - pct


def score_candidates(
    gm: GraphMatrix, profile: dict, known: set[int], cfg: RecommendSettings
) -> list[Candidate]:
    pos_w, neg_w = _seeds(profile, cfg)
    pos = [(a, w) for a, w in _top(pos_w, cfg.max_seeds, +1) if gm.position(a) is not None]
    neg = [(a, w) for a, w in _top(neg_w, cfg.max_negative_seeds, -1) if gm.position(a) is not None]
    if not pos:
        return []

    seeds = sorted(pos + neg)  # artist_id'ye göre: sütun sırası girdi sırasından bağımsız
    seed_ids = np.array([a for a, _ in seeds], dtype=np.int64)
    w = np.array([x for _, x in seeds], dtype=np.float32)
    seed_pos = np.array([gm.position(int(a)) for a in seed_ids])

    n = gm.node_ids.size
    mask = np.ones(n, dtype=np.float32)
    for a in profile.get("avoid", []):
        if a["hard"] and (p := gm.position(a["artist_id"])) is not None:
            mask[p] = 0.0

    cur = np.zeros((n, seed_ids.size), dtype=np.float32)
    cur[seed_pos, np.arange(seed_ids.size)] = 1.0
    cur *= mask[:, None]
    acc = cur.copy()
    for _ in range(cfg.ppr_iterations):
        cur = cfg.ppr_alpha * (gm.matrix @ cur)
        cur *= mask[:, None]
        acc += cur
    acc *= 1.0 - cfg.ppr_alpha

    raw = acc @ w
    novelty = _novelty(gm)
    final = raw * (1.0 + cfg.novelty_gamma * novelty)

    blocked = np.zeros(n, dtype=bool)
    blocked[mask == 0.0] = True
    blocked[seed_pos] = True
    for a in profile.get("avoid", []):
        if (p := gm.position(a["artist_id"])) is not None:
            blocked[p] = True
    for a in known:
        if (p := gm.position(a)) is not None:
            blocked[p] = True

    cand = np.flatnonzero((final > 0) & ~blocked)
    order = cand[np.lexsort((gm.node_ids[cand], -final[cand]))][: cfg.candidate_top_n]

    anchors = {a["artist_id"] for a in profile.get("anchors", [])}
    out: list[Candidate] = []
    for c in order:
        contrib = acc[c] * w
        positive = np.where(contrib > 0, contrib, 0.0)
        total = float(positive.sum())
        top = np.lexsort((seed_ids, -positive))[: cfg.reason_count]
        reasons = [
            Reason(int(seed_ids[i]), float(positive[i] / total), float(contrib[i]),
                   int(seed_ids[i]) in anchors)
            for i in top
            if positive[i] > 0
        ]
        out.append(
            Candidate(
                int(gm.node_ids[c]), float(final[c]), float(raw[c]), float(novelty[c]),
                float(-contrib[contrib < 0].sum()), reasons,
            )
        )
    return out
