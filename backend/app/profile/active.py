"""Aktif öğrenme kuyruğu sıralaması (saf): en belirsiz parçalar önce; aynı girdi, aynı sıra.

Belirsizlik = karar sınırına yakınlık: sanatçının PPR skorunun, grafikteki sinyalli sanatçıların
skor dağılımındaki mid-rank persentili p ise 1 - |2p - 1| (medyanda 1, uçlarda 0). Sinyali olmayan
(grafikte olmayan veya skoru 0) sanatçıya yapılandırmadaki sabit değer verilir.
"""
import hashlib
import math
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence

from app.config import ProfileSettings
from app.profile.sampler import seeded_unit


def _key(seed: int, ident: int) -> str:
    return hashlib.sha256(f"{seed}:{ident}".encode()).hexdigest()


def uncertainty(score: float | None, ref_sorted: Sequence[float], unknown: float) -> float:
    if score is None or not ref_sorted:
        return unknown
    below = bisect_left(ref_sorted, score)
    equal = bisect_right(ref_sorted, score) - below
    p = (below + equal / 2) / len(ref_sorted)
    return 1.0 - abs(2.0 * p - 1.0)


def order_unresolved(tracks: Sequence[int], pool: set[int], seed: int) -> list[int]:
    """Sanatçısı eşlenmemiş parçalar (belirsizlik hesaplanamaz): havuzdakiler önce, sonra
    tohumlu özet sırası. Eşlenmişlerden sonra gösterilir; oy olay olarak kaydolur, profil
    sanatçı eşlenince bunu kullanır."""
    return sorted(tracks, key=lambda t: (t not in pool, _key(seed, t)))


def diversify(
    order: Sequence[int],
    artist_of: Mapping[int, int],
    genre_of: Mapping[int, str],
    pool: set[int],
    seed: int,
    cfg: ProfileSettings,
    limit: int,
    prior_artists: Sequence[int] = (),
) -> list[int]:
    """Öncelik sırasını (`order`) bozmadan yan yana benzerliği azaltır; ilk `limit` parçayı döner.

    Kural: bir parça, son `queue_artist_gap` parçadakilerden farklı sanatçıdan ve son
    `queue_genre_gap` parçadakilerden farklı türden olmalı (türü bilinmeyen kısıtlanmaz).
    Her `queue_explore_every`'inci yuva keşif yuvasıdır: tohumlu rastgele sıradan (havuzdaki
    parçalar önce) seçilir. Uygun parça yoksa önce tür, sonra sanatçı kuralı gevşer.
    `prior_artists`: istemcide zaten olan parçaların sanatçıları (eskiden yeniye); aralık
    pencereleri bunlarla başlar. Aynı girdi ve tohum, aynı sıra."""
    random_order = sorted(order, key=lambda t: (t not in pool, _key(seed + 7919, t)))
    used: set[int] = set()
    out: list[int] = []

    def pick(candidates: Sequence[int], artists: set[int], genres: set[str]) -> int | None:
        for strict in (True, False):  # önce sanatçı+tür, sonra yalnız sanatçı
            for t in candidates:
                if t in used:
                    continue
                if artist_of.get(t) in artists:
                    continue
                if strict and genre_of.get(artist_of.get(t, -1)) in genres:
                    continue
                return t
        return next((t for t in candidates if t not in used), None)

    seq: list[int] = list(prior_artists)  # sanatçı dizisi: önceki + seçilenler
    for i in range(min(limit, len(order))):
        artists = set(seq[-cfg.queue_artist_gap:]) if cfg.queue_artist_gap > 0 else set()
        genres = (
            {genre_of[a] for a in seq[-cfg.queue_genre_gap:] if a in genre_of}
            if cfg.queue_genre_gap > 0 else set()
        )
        explore = cfg.queue_explore_every > 0 and (i + 1) % cfg.queue_explore_every == 0
        chosen = pick(random_order if explore else order, artists, genres)
        if chosen is None:
            break
        used.add(chosen)
        out.append(chosen)
        seq.append(artist_of[chosen])
    return out


def order_active(
    cands: list[tuple[int, int]],
    unc: Mapping[int, float],
    pool: set[int],
    voted_artists: set[int],
    seed: int,
    cfg: ProfileSettings,
    tau: float = 0.0,
) -> list[int]:
    """cands: (track_id, artist_id). Oy almamış sanatçılar önce; her sanatçıdan sırayla birer
    parça (çeşitlilik). Tur içinde sıra: belirsizlik + havuz bonusu (azalan), eşitlikte tohumlu
    özet. Sanatçı içinde havuzdaki parça önce gelir.

    `tau` > 0 ise puana tohumlu Gumbel gürültüsü (τ·G) eklenir: oturumlar arası tazelik için
    baş taraf tohumla değişir, tur ve oy almamış-önce kuralı korunur. τ=0 saf puan sırası."""
    by_artist: dict[int, list[int]] = {}
    for track, artist in cands:
        by_artist.setdefault(artist, []).append(track)
    ranked = []
    for artist, tracks in by_artist.items():
        tier = 1 if artist in voted_artists else 0
        base = unc.get(artist, cfg.active_unknown_uncertainty)
        ordered = sorted(tracks, key=lambda t: (t not in pool, _key(seed, t)))
        for idx, track in enumerate(ordered):
            score = base + (cfg.active_pool_bonus if track in pool else 0.0)
            if tau > 0:
                score += tau * -math.log(-math.log(seeded_unit(seed, f"active:{track}")))
            ranked.append((idx, tier, -score, _key(seed, track), track))
    ranked.sort()
    return [r[4] for r in ranked]
