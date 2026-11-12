"""MMR ile çeşitli seçim (saf): alaka ve seçilmişlere benzerlik arasında denge.

Benzerlik, grafik matrisi satırlarının kosinüsüdür. Her aday bir sanatçı olduğundan sanatçı başına
en çok bir öğe zaten garantidir (üst sınır = 1). Eşitlikte aday sırası (skor, kimlik) kazanır.
"""
import math

import numpy as np
from sklearn.preprocessing import normalize

from app.graph.matrix import GraphMatrix
from app.profile.sampler import seeded_unit
from app.recommend.ppr import Candidate


def select_mmr(
    cands: list[Candidate], gm: GraphMatrix, size: int, mmr_lambda: float,
    tau: float = 0.0, seed: int = 0,
) -> list[Candidate]:
    """`tau` > 0 ise alakaya tohumlu Gumbel gürültüsü eklenir (Gumbel-top-k tazelik): aynı tohum
    aynı seçimi verir, farklı tohum yakın skorlu adaylar arasında sırayı değiştirir."""
    if not cands or size <= 0:
        return []
    pos = np.array([gm.position(c.artist_id) for c in cands])
    rows = normalize(gm.matrix[pos], norm="l2")
    sim = (rows @ rows.T).toarray()
    rel = np.array([c.score for c in cands], dtype=np.float64)
    rel /= rel.max()
    if tau > 0:
        rel += tau * np.array(
            [-math.log(-math.log(seeded_unit(seed, f"mmr:{c.artist_id}"))) for c in cands]
        )

    chosen: list[int] = []
    max_sim = np.zeros(len(cands))
    free = np.ones(len(cands), dtype=bool)
    for _ in range(min(size, len(cands))):
        mmr = mmr_lambda * rel - (1.0 - mmr_lambda) * max_sim
        mmr[~free] = -np.inf
        best = int(np.argmax(mmr))  # eşitlikte ilk (aday sırası deterministik)
        chosen.append(best)
        free[best] = False
        max_sim = np.maximum(max_sim, sim[best])
    return [cands[i] for i in chosen]
