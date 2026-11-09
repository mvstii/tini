"""Tür bandit'i (saf): her ana tür bir kol; Thompson sampling ile tohumlu tür payı.

theta_g ~ Beta(a0 + Good+_g, b0 + Bad-_g). Pay = taban + serbest × theta_g / Σtheta. Taban, Awful
alan türün sıfırlanmasını önler. Aynı sonuçlar ve tohum, aynı payı verir.
"""
import random
from collections.abc import Iterable, Mapping, Sequence

from app.config import RecommendSettings


def genre_outcomes(
    votes: Iterable[tuple[str, int]], good: int = 4, bad: int = 2
) -> dict[str, tuple[int, int]]:
    """(tür, oy) çiftlerinden tür -> (Good+ sayısı, Bad- sayısı). Meh sonuç sayılmaz."""
    out: dict[str, list[int]] = {}
    for genre, vote in votes:
        tally = out.setdefault(genre, [0, 0])
        if vote >= good:
            tally[0] += 1
        elif vote <= bad:
            tally[1] += 1
    return {g: (a, b) for g, (a, b) in out.items()}


def sample_genre_scores(
    outcomes: Mapping[str, tuple[int, int]],
    genres: Sequence[str],
    seed: int,
    cfg: RecommendSettings,
) -> dict[str, float]:
    """Tür başına pay (toplam 1). `genres` tüm kolları verir; denenmemiş kol öncülden örneklenir."""
    rng = random.Random(seed)
    theta = {}
    for g in sorted(genres):  # sabit sıra: tohum aynıysa örnekler aynı
        succ, fail = outcomes.get(g, (0, 0))
        theta[g] = rng.betavariate(cfg.genre_prior_a + succ, cfg.genre_prior_b + fail)
    norm = sum(theta.values())
    free = 1.0 - cfg.genre_floor_share * len(theta)
    if free < 0:
        raise ValueError("genre_floor_share × tür sayısı 1'i aşamaz")
    return {g: cfg.genre_floor_share + free * t / norm for g, t in theta.items()}
