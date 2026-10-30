"""Çapa sanatçının komşuluğu (saf): derinlik 1 doğrudan ağırlık, derinlik 2 yol çarpımı toplamı.

Derinlik 2'de yalnızca en güçlü `neighborhood_fanout` derinlik-1 komşu genişletilir; böylece
maliyet fanout × komşu başına satır uzunluğuyla sınırlı kalır. Eşit skorda küçük kimlik önce.
"""
from dataclasses import dataclass

import numpy as np

from app.config import GraphSettings
from app.graph.matrix import GraphMatrix


@dataclass(frozen=True)
class Neighbor:
    artist_id: int
    score: float
    via: int | None  # derinlik 2'de skora en çok katkı yapan derinlik-1 komşu


@dataclass(frozen=True)
class Neighborhood:
    anchor: int
    depth1: list[Neighbor]
    depth2: list[Neighbor]


def _top(idx: np.ndarray, score: np.ndarray, k: int) -> np.ndarray:
    """Skora göre azalan, eşitlikte idx'e göre artan ilk k konum."""
    return np.lexsort((idx, -score))[:k]


def neighborhood(
    gm: GraphMatrix, anchor_id: int, depth: int, cfg: GraphSettings
) -> Neighborhood | None:
    pos = gm.position(anchor_id)
    if pos is None:
        return None
    depth = max(1, min(depth, cfg.neighborhood_max_depth))
    m = gm.matrix
    lo, hi = m.indptr[pos], m.indptr[pos + 1]
    cols, vals = m.indices[lo:hi], m.data[lo:hi]  # cols sıralı → lexsort eşitlikleri deterministik
    top = _top(cols, vals, cfg.neighborhood_top_k)
    depth1 = [
        Neighbor(int(gm.node_ids[cols[o]]), float(vals[o]), None) for o in top
    ]
    if depth < 2 or cols.size == 0:
        return Neighborhood(anchor_id, depth1, [])

    fan = _top(cols, vals, cfg.neighborhood_fanout)
    sub = m[cols[fan]].multiply(vals[fan].reshape(-1, 1)).tocsr()
    scores = np.asarray(sub.sum(axis=0)).ravel()
    scores[pos] = 0.0
    scores[cols] = 0.0  # çapa ve tüm derinlik-1 komşular derinlik 2'de tekrar listelenmez
    cand = np.flatnonzero(scores > 0)
    best = cand[_top(cand, scores[cand], cfg.neighborhood_top_k)]
    via_row = np.asarray(sub.argmax(axis=0)).ravel()
    depth2 = [
        Neighbor(int(gm.node_ids[c]), float(scores[c]), int(gm.node_ids[cols[fan[via_row[c]]]]))
        for c in best
    ]
    return Neighborhood(anchor_id, depth1, depth2)
