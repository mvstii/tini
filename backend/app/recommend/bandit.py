"""Slot dağılımı (saf): Thompson sampling ile liste kontenjanını slotlara böler.

Slotlar: familiar (yüksek PPR), unheard (havuzdaki parçanın sanatçısı), explore (daha uzak).
Toplam sonuç sayısı eşiğin altındayken pay yapılandırmadaki önceldir; eşikten sonra her slot için
Beta(a0 + başarı, b0 + başarısızlık) sonsalından tohumlu örnek alınır, taban payla harmanlanır.
Aynı girdi ve tohum, aynı dağılımı verir.
"""
import random
from collections.abc import Mapping

from app.config import RecommendSettings

SLOTS = ("familiar", "unheard", "explore")


def slot_shares(
    outcomes: Mapping[str, tuple[int, int]], cfg: RecommendSettings, seed: int
) -> dict[str, float]:
    """Slot başına pay (toplam 1). outcomes: slot -> (başarı, başarısızlık)."""
    total = sum(s + f for s, f in outcomes.values())
    if total < cfg.bandit_min_outcomes:
        prior = {s: cfg.slot_prior_shares[s] for s in SLOTS}
        norm = sum(prior.values())
        return {s: v / norm for s, v in prior.items()}
    rng = random.Random(seed)
    theta = {}
    for s in SLOTS:  # sabit sıra: tohum aynıysa örnekler aynı
        succ, fail = outcomes.get(s, (0, 0))
        theta[s] = rng.betavariate(cfg.slot_prior_a + succ, cfg.slot_prior_b + fail)
    norm = sum(theta.values())
    free = 1.0 - cfg.slot_floor_share * len(SLOTS)
    return {s: cfg.slot_floor_share + free * theta[s] / norm for s in SLOTS}


def far_share(
    outcomes: Mapping[str, tuple[int, int]], cfg: RecommendSettings, seed: int
) -> float:
    """Uzak yuvanın liste payı (list-6). Toplam sonuç eşiğin altındayken sabit `far_share`;
    sonra taban + (tavan - taban) × theta, theta ~ Beta(a0 + Good+, b0 + Bad-) (uzak yuva)."""
    total = sum(s + f for s, f in outcomes.values())
    if total < cfg.bandit_min_outcomes:
        return cfg.far_share
    succ, fail = outcomes.get("far", (0, 0))
    theta = random.Random(f"far:{seed}").betavariate(
        cfg.slot_prior_a + succ, cfg.slot_prior_b + fail
    )
    return cfg.far_floor_share + (cfg.far_max_share - cfg.far_floor_share) * theta


def _largest_remainder(total: int, weights: dict[str, float]) -> dict[str, int]:
    norm = sum(weights.values())
    raw = {s: total * w / norm for s, w in weights.items()}
    out = {s: int(v) for s, v in raw.items()}
    order = sorted(weights, key=lambda s: (-(raw[s] - out[s]), SLOTS.index(s)))
    for s in order[: total - sum(out.values())]:
        out[s] += 1
    return out


def allocate(
    size: int, shares: Mapping[str, float], available: Mapping[str, int]
) -> dict[str, int]:
    """Kontenjanı paylara göre böler; slotun aday sayısını aşan kısım kalanlara dağıtılır."""
    out = {s: 0 for s in SLOTS}
    remaining = min(size, sum(available.get(s, 0) for s in SLOTS))
    active = {s: shares[s] for s in SLOTS if available.get(s, 0) > 0 and shares[s] > 0}
    for s in SLOTS:  # payı 0 ama adayı olan slotlar yalnız taşma için son çare
        if available.get(s, 0) > 0 and s not in active:
            active[s] = 1e-9
    while remaining > 0 and active:
        trial = _largest_remainder(remaining, active)
        over = [s for s in active if trial[s] > available[s] - out[s]]
        if not over:
            for s, n in trial.items():
                out[s] += n
            break
        for s in over:
            take = available[s] - out[s]
            out[s] += take
            remaining -= take
            del active[s]
    return out
