"""Aktif öğrenme kuyruğu sıralaması (saf): en belirsiz parçalar önce; aynı girdi, aynı sıra.

Belirsizlik = karar sınırına yakınlık: sanatçının PPR skorunun, grafikteki sinyalli sanatçıların
skor dağılımındaki mid-rank persentili p ise 1 - |2p - 1| (medyanda 1, uçlarda 0). Sinyali olmayan
(grafikte olmayan veya skoru 0) sanatçıya yapılandırmadaki sabit değer verilir.
"""
import hashlib
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence

from app.config import ProfileSettings


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
) -> list[int]:
    """Öncelik sırasını (`order`) bozmadan yan yana benzerliği azaltır; ilk `limit` parçayı döner.

    Kural: bir parça, son `queue_artist_gap` parçadakilerden farklı sanatçıdan ve son
    `queue_genre_gap` parçadakilerden farklı türden olmalı (türü bilinmeyen kısıtlanmaz).
    Her `queue_explore_every`'inci yuva keşif yuvasıdır: tohumlu rastgele sıradan (havuzdaki
    parçalar önce) seçilir. Uygun parça yoksa önce tür, sonra sanatçı kuralı gevşer.
    Aynı girdi ve tohum, aynı sıra."""
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

    for i in range(min(limit, len(order))):
        artists = (
            {artist_of[t] for t in out[-cfg.queue_artist_gap:]} if cfg.queue_artist_gap > 0
            else set()
        )
        genres = (
            {genre_of[artist_of[t]] for t in out[-cfg.queue_genre_gap:]
             if artist_of[t] in genre_of} if cfg.queue_genre_gap > 0 else set()
        )
        explore = cfg.queue_explore_every > 0 and (i + 1) % cfg.queue_explore_every == 0
        chosen = pick(random_order if explore else order, artists, genres)
        if chosen is None:
            break
        used.add(chosen)
        out.append(chosen)
    return out


def order_active(
    cands: list[tuple[int, int]],
    unc: Mapping[int, float],
    pool: set[int],
    voted_artists: set[int],
    seed: int,
    cfg: ProfileSettings,
) -> list[int]:
    """cands: (track_id, artist_id). Oy almamış sanatçılar önce; her sanatçıdan sırayla birer
    parça (çeşitlilik). Tur içinde sıra: belirsizlik + havuz bonusu (azalan), eşitlikte tohumlu
    özet. Sanatçı içinde havuzdaki parça önce gelir."""
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
            ranked.append((idx, tier, -score, _key(seed, track), track))
    ranked.sort()
    return [r[4] for r in ranked]
