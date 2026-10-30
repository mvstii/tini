"""Seyrek komşuluk matrisi kurucusu (saf, vektörel): aynı kenarlar her zaman aynı matrisi verir.

Adımlar: eşik/öz-döngü süzme → çift kenarlarda en büyük ağırlık → simetrikleştirme →
derece normalizasyonu. Düğümler sıralı kimlik dizisine eşlenir (dict yok, arama O(log n)).
"""
from dataclasses import dataclass

import numpy as np
from scipy import sparse

from app.config import GraphSettings


@dataclass(frozen=True)
class GraphMatrix:
    node_ids: np.ndarray  # artık artist.id'ler, sıralı; matris satır/sütun i ↔ node_ids[i]
    matrix: sparse.csr_matrix  # float32, kanonik CSR (sıralı indeks)

    def position(self, artist_id: int) -> int | None:
        i = int(np.searchsorted(self.node_ids, artist_id))
        if i < len(self.node_ids) and self.node_ids[i] == artist_id:
            return i
        return None


def _empty() -> GraphMatrix:
    return GraphMatrix(
        np.empty(0, dtype=np.int64), sparse.csr_matrix((0, 0), dtype=np.float32)
    )


def build_matrix(
    src: np.ndarray, dst: np.ndarray, weight: np.ndarray, cfg: GraphSettings
) -> GraphMatrix:
    src = np.asarray(src, dtype=np.int64)
    dst = np.asarray(dst, dtype=np.int64)
    w = np.asarray(weight, dtype=np.float64)
    keep = (w > 0) & (w >= cfg.edge_min_weight) & (src != dst)
    src, dst, w = src[keep], dst[keep], w[keep]
    if src.size == 0:
        return _empty()

    node_ids = np.unique(np.concatenate([src, dst]))
    n = node_ids.size
    i = np.searchsorted(node_ids, src)
    j = np.searchsorted(node_ids, dst)

    # Aynı (i, j) birden çok kaynaktan gelirse en büyük ağırlık kalır.
    key = i * n + j
    order = np.lexsort((w, key))
    key_s = key[order]
    last = np.empty(key_s.size, dtype=bool)
    last[:-1] = key_s[1:] != key_s[:-1]
    last[-1] = True
    sel = order[last]
    a = sparse.csr_matrix((w[sel], (i[sel], j[sel])), shape=(n, n))

    if cfg.matrix_symmetrize == "max":
        s = a.maximum(a.T)
    elif cfg.matrix_symmetrize == "mean":
        s = (a + a.T) * 0.5
    else:
        raise ValueError(f"matrix_symmetrize: {cfg.matrix_symmetrize!r}")

    deg = np.asarray(s.sum(axis=1)).ravel()  # her düğümün en az bir kenarı var, deg > 0
    if cfg.matrix_normalization == "sym":
        d = sparse.diags(1.0 / np.sqrt(deg))
        s = d @ s @ d
    elif cfg.matrix_normalization == "row":
        s = sparse.diags(1.0 / deg) @ s
    elif cfg.matrix_normalization != "none":
        raise ValueError(f"matrix_normalization: {cfg.matrix_normalization!r}")

    s = s.tocsr().astype(np.float32)
    s.sort_indices()
    return GraphMatrix(node_ids, s)
