"""Oylama kuyruğu sıralaması (saf): aynı girdi ve tohum aynı sırayı üretir."""
import hashlib
import re
from collections.abc import Iterable

from app.catalog.names import normalize_name


def _key(seed: int, ident: int) -> str:
    return hashlib.sha256(f"{seed}:{ident}".encode()).hexdigest()


def song_key(title: str, artists: list[str] | None, markers: Iterable[str]) -> tuple[str, str]:
    """Aynı şarkının sürümlerini (remaster, mono, deluxe...) tek anahtara indirir:
    (normalize başlık, normalize birincil sanatçı). Canlı/remix/akustik ayrı şarkıdır, atılmaz."""
    alt = "|".join(re.escape(m) for m in markers)
    stripped = title
    if alt:
        stripped = re.sub(
            rf"\s*[(\[][^)\]]*\b(?:{alt})[^)\]]*[)\]]", "", stripped, flags=re.I
        )
        stripped = re.sub(
            rf"\s+[-–—]\s+[^-–—]*\b(?:{alt})[^-–—]*$", "", stripped, flags=re.I
        )
    name = normalize_name(stripped) or normalize_name(title)
    return name, normalize_name(artists[0]) if artists else ""


def pick_versions(
    entries: Iterable[tuple[int, str, list[str] | None]],
    voted: Iterable[tuple[str, list[str] | None]],
    pool: set[int],
    markers: Iterable[str],
) -> set[int]:
    """entries: (track_id, başlık, sanatçılar). Oylanmış bir sürümü olan şarkıyı eler; kalan
    her şarkıdan tek parça bırakır (havuzdaki, yoksa en düşük kimlik). Dönen: korunan kimlikler."""
    markers = tuple(markers)
    seen = {song_key(t, a, markers) for t, a in voted}
    best: dict[tuple[str, str], int] = {}
    for track, title, artists in sorted(entries, key=lambda e: e[0]):
        key = song_key(title, artists, markers)
        if key in seen:
            continue
        cur = best.get(key)
        if cur is None or (track in pool and cur not in pool):
            best[key] = track
    return set(best.values())


def order_queue(
    cands: list[tuple[int, int]], voted_artists: set[int], seed: int
) -> list[int]:
    """cands: (track_id, artist_id). Oy almamış sanatçılar önce; her sanatçıdan sırayla birer
    parça (çeşitlilik), sanatçı içi ve sanatçılar arası sıra tohumlu özetle belirlenir."""
    by_artist: dict[int, list[int]] = {}
    for track, artist in cands:
        by_artist.setdefault(artist, []).append(track)
    ranked = []
    for artist, tracks in by_artist.items():
        tier = 1 if artist in voted_artists else 0
        for idx, track in enumerate(sorted(tracks, key=lambda t: _key(seed, t))):
            ranked.append((tier, idx, _key(seed, artist), track))
    ranked.sort()
    return [r[3] for r in ranked]
