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


def source_quota(mix: Mapping[str, int], have: Mapping[str, int], size: int) -> dict[str, int]:
    """Kaynak başına kart kotası: karışım payı, havuzda olanla sınırlı; açık kalan yuvalar
    `SOURCES` sırasıyla fazlası olan kaynaklara verilir. Toplam ≤ `size` (aday yetmezse az)."""
    out = {s: min(mix.get(s, 0), have.get(s, 0)) for s in SOURCES}
    left = size - sum(out.values())
    for s in SOURCES:
        add = min(left, have.get(s, 0) - out[s])
        if add > 0:
            out[s] += add
            left -= add
    return out


def interleave(pools: Mapping[str, Sequence], quota: Mapping[str, int], oversample: int) -> list:
    """Kaynak başına en çok kota × `oversample` aday; kaynaklar kotalarıyla orantılı aralıkla
    harmanlanır (rerank eşitlikte bu sırayı korur, kaynak tek yere yığılmaz)."""
    keyed = [
        ((i + 0.5) / quota[s], SOURCES.index(s), i, item)
        for s in SOURCES if quota.get(s, 0) > 0
        for i, item in enumerate(pools[s][: quota[s] * max(oversample, 1)])
    ]
    return [item for *_, item in sorted(keyed, key=lambda k: k[:3])]


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


def noisy_rank(items: Sequence, tau: float, seed: int, key: Callable[[object], Hashable]) -> list:
    """Sıralı listeyi tohumla sarsar: puan = −i/n + τ·G (G Gumbel). τ=0 sırayı korur; baştaki
    öğeler başa yakın kalır ama oturumdan oturuma aynı öğe aynı yere düşmez."""
    if tau <= 0 or len(items) < 2:
        return list(items)
    n = len(items)
    scores = {i: -i / n for i in range(n)}
    noise = {
        i: -math.log(-math.log(seeded_unit(seed, f"rank:{key(items[i])}"))) for i in range(n)
    }
    return [items[i] for i in sorted(scores, key=lambda i: (-(scores[i] + tau * noise[i]), i))]


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
    quota: Mapping[str, int] | None = None,
    seed: int = 0,
    jitter: float = 0.0,
) -> list[Cand]:
    """Aday sırasını (öncelik) koruyup yuva yuva seçer; ilk `limit` aday. Havuz `limit`ten
    büyükse kısıtları bozan adaylar elenir (yalnız sıralama değil, seçim).

    Her yuvada en büyük hedef açığı olan ana tür seçilir (açık = hedef·(n+1) − seçilen).
    Türü bilinmeyen aday nötrdür: havuzdaki payı (u) kadar hedef alır, bilinen türlerin hedefi
    (1 − u) ile ölçeklenir; böylece bilinenler başa yığılmaz.
    Kısıtlar: sanatçı aralığı, art arda aynı alt tür yok, graf benzerlik penceresi, şarkı
    tekilliği, kaynak kotası (`quota[kaynak]` dolunca o kaynaktan alınmaz).
    Kota aynı zamanda tempodur: her yuvada en geride kalan kaynak seçilir, tür kalibrasyonu
    o kaynağın adayları içinde çalışır.
    Uygun aday yoksa kademeli gevşeme: alt tür, benzerlik, ana tür (kalibrasyon), kota, sanatçı.
    `jitter` > 0 ise her türün açığına tohumlu sabit bir kayma (±jitter/2 kart) eklenir: türün
    partideki payı en çok o kadar oynar, ama az adaylı tür her oturumda aynı yuvaya düşmez."""
    pool = list(cands)
    out: list[Cand] = []
    artists = list(prior_artists)
    subs = list(prior_subs)
    keys: set[str] = set()
    counts: dict[str | None, int] = {}
    used: dict[str, int] = {}
    unknown = sum(1 for c in pool if not c.genre) / len(pool) if pool else 0.0
    levels = (
        {"quota", "sub", "sim", "main", "artist"},
        {"quota", "sim", "main", "artist"},
        {"quota", "main", "artist"},
        {"quota", "artist"},
        {"artist"},
        set(),
    )
    gap = cfg.queue_artist_gap
    shift: dict[str | None, float] = {
        g: jitter * (seeded_unit(seed, f"genre:{g}") - 0.5) if jitter > 0 else 0.0
        for g in (*target, None)
    }

    def full(c: Cand) -> bool:
        return quota is not None and used.get(c.source, 0) >= quota.get(c.source, 0)

    while pool and len(out) < limit:
        pool = [c for c in pool if c.song_key is None or c.song_key not in keys]
        if not pool:
            break
        n = len(out) + 1
        deficit: dict[str | None, float] = {
            g: target.get(g, 0.0) * (1 - unknown) * n - counts.get(g, 0) + shift[g]
            for g in target
        }
        deficit[None] = unknown * n - counts.get(None, 0) + shift[None]
        recent_artists = set(artists[-gap:]) if gap > 0 else set()
        window = [a for a in artists[-cfg.queue_sim_window:]] if cfg.queue_sim_window > 0 else []
        chosen: Cand | None = None
        for active in levels:
            ok = [
                c for c in pool
                if not ("quota" in active and full(c))
                and not ("artist" in active and c.artist is not None and c.artist in recent_artists)
                and not ("sub" in active and c.sub is not None and subs and c.sub == subs[-1])
                and not ("sim" in active and sim is not None and c.artist is not None
                         and any(sim(c.artist, a) > cfg.queue_sim_max for a in window))
            ]
            if not ok:
                continue
            if quota is not None and "quota" in active:
                # Tempo: en geride kalan kaynak (kota·n/limit − kullanılan) önce; kaynaklar
                # partiye yayılır, keşif kartları sona yığılmaz.
                lag = {c.source: quota.get(c.source, 0) * n / limit - used.get(c.source, 0)
                       for c in ok}
                top = max(lag.values())
                ok = [c for c in ok if lag[c.source] == top]
            if "main" in active:
                best = max(deficit.get(c.genre or None, -1e9) for c in ok)
                ok = [c for c in ok if deficit.get(c.genre or None, -1e9) == best]
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
        counts[chosen.genre or None] = counts.get(chosen.genre or None, 0) + 1
        used[chosen.source] = used.get(chosen.source, 0) + 1
    return out
