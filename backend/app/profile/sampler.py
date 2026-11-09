"""Kuyruk örnekleyicisi (saf, `queue-8`): kaynak karışımı, hücre skoru, Gumbel-top-k, rerank.

Rastgelelik yalnızca tohumdan gelir (özet tabanlı); aynı girdi ve tohum, aynı sıra.
"""
import hashlib
import math
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass

from app.config import ProfileSettings

SOURCES = ("library", "neighborhood", "probe", "joker")


@dataclass(frozen=True)
class Cand:
    """Rerank adayı. `genre`/`sub` bilinmiyorsa None; `song_key` aynı şarkı sürümlerini eşler."""

    track: int
    artist: int | None
    genre: str | None
    sub: str | None
    source: str
    song_key: str | None = None


def seeded_unit(seed: int, key: str) -> float:
    """(0, 1) açık aralığında tohumlu, kararlı düzgün sayı."""
    h = int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()[:13], 16)
    return (h + 0.5) / float(1 << 52)


def source_mix(
    votes: int, size: int, available: Mapping[str, bool], cfg: ProfileSettings
) -> dict[str, int]:
    """Kaynak başına kart sayısı (toplam = `size`). Oy sayısına göre ısınma→olgun doğrusal geçiş.

    Boş kaynağın (`available[s]` False) payı diğerlerine orantılı dağıtılır; hiçbiri yoksa
    kütüphane payı alır. En büyük kalan yöntemiyle tamsayıya çevrilir (deterministik)."""
    lo, hi = cfg.queue_mix_warm_votes, cfg.queue_mix_mature_votes
    t = 0.0 if hi <= lo else min(max((votes - lo) / (hi - lo), 0.0), 1.0)
    w = {
        s: (1 - t) * a + t * b
        for s, a, b in zip(SOURCES, cfg.queue_mix_warm, cfg.queue_mix_mature, strict=True)
    }
    live = {s: v for s, v in w.items() if available.get(s, False) and v > 0}
    if not live:
        return {s: (size if s == "library" else 0) for s in SOURCES}
    total = sum(live.values())
    exact = {s: size * live.get(s, 0.0) / total for s in SOURCES}
    out = {s: int(exact[s]) for s in SOURCES}
    left = size - sum(out.values())
    order = sorted(SOURCES, key=lambda s: (-(exact[s] - out[s]), SOURCES.index(s)))
    for s in order[:left]:
        out[s] += 1
    return out


def cell_scores(
    shown: Mapping[Hashable, int], theta: Mapping[str, float], kappa: float
) -> dict[Hashable, float]:
    """puan(hücre) = κ / √(1 + o) + θ(ana tür). Hücre = (ana tür, alt tür, bant)."""
    return {
        cell: kappa / math.sqrt(1 + o) + theta.get(cell[0], 0.0) for cell, o in shown.items()
    }


def gumbel_order(scores: Mapping[Hashable, float], tau: float, seed: int) -> list:
    """Sıra = argsort(skor + τ·G) azalan; G = −ln(−ln U). τ=0 saf skor sırası. Eşitlikte anahtar."""
    def key(item: Hashable) -> tuple[float, str]:
        k = repr(item)
        g = -math.log(-math.log(seeded_unit(seed, k))) if tau > 0 else 0.0
        return (-(scores[item] + tau * g), k)

    return sorted(scores, key=key)


def genre_targets(
    shares: Mapping[str, float], genres: Sequence[str], epsilon: float
) -> dict[str, float]:
    """hedef(g) = (1 − ε)·p_kullanıcı(g) + ε·eşit(g); p, `genres` üzerinde yeniden normalize."""
    total = sum(max(shares.get(g, 0.0), 0.0) for g in genres)
    k = len(genres)
    return {
        g: (1 - epsilon) * (max(shares.get(g, 0.0), 0.0) / total if total > 0 else 1 / k)
        + epsilon / k
        for g in genres
    }


def rerank(
    cands: Sequence[Cand],
    target: Mapping[str, float],
    limit: int,
    cfg: ProfileSettings,
    prior_artists: Sequence[int] = (),
    prior_subs: Sequence[str | None] = (),
    sim: Callable[[int, int], float] | None = None,
) -> list[Cand]:
    """Aday sırasını (öncelik) koruyup yuva yuva seçer; ilk `limit` aday.

    Her yuvada en büyük hedef açığı olan ana tür seçilir (açık = hedef·(n+1) − seçilen).
    Kısıtlar: sanatçı aralığı, art arda aynı alt tür yok, graf benzerlik penceresi, şarkı tekilliği.
    Uygun aday yoksa kademeli gevşeme: alt tür, benzerlik, ana tür (kalibrasyon), sanatçı."""
    pool = list(cands)
    out: list[Cand] = []
    artists = list(prior_artists)
    subs = list(prior_subs)
    keys: set[str] = set()
    counts: dict[str, int] = {}
    levels = (
        {"sub", "sim", "main", "artist"},
        {"sim", "main", "artist"},
        {"main", "artist"},
        {"artist"},
        set(),
    )
    gap = cfg.queue_artist_gap
    while pool and len(out) < limit:
        pool = [c for c in pool if c.song_key is None or c.song_key not in keys]
        if not pool:
            break
        n = len(out) + 1
        deficit = {g: target.get(g, 0.0) * n - counts.get(g, 0) for g in target}
        recent_artists = set(artists[-gap:]) if gap > 0 else set()
        window = [a for a in artists[-cfg.queue_sim_window:]] if cfg.queue_sim_window > 0 else []
        chosen: Cand | None = None
        for active in levels:
            ok = [
                c for c in pool
                if not ("artist" in active and c.artist is not None and c.artist in recent_artists)
                and not ("sub" in active and c.sub is not None and subs and c.sub == subs[-1])
                and not ("sim" in active and sim is not None and c.artist is not None
                         and any(sim(c.artist, a) > cfg.queue_sim_max for a in window))
            ]
            if not ok:
                continue
            if "main" in active:
                best = max(deficit.get(c.genre, -1e9) if c.genre else -1e9 for c in ok)
                ok = [c for c in ok if (deficit.get(c.genre, -1e9) if c.genre else -1e9) == best]
            chosen = ok[0]
            break
        if chosen is None:
            chosen = pool[0]
        pool.remove(chosen)
        out.append(chosen)
        if chosen.artist is not None:
            artists.append(chosen.artist)
        subs.append(chosen.sub)
        if chosen.song_key is not None:
            keys.add(chosen.song_key)
        if chosen.genre:
            counts[chosen.genre] = counts.get(chosen.genre, 0) + 1
    return out
