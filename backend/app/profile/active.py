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
