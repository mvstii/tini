"""Oylama kuyruğu sıralaması (saf): aynı girdi ve tohum aynı sırayı üretir."""
import hashlib


def _key(seed: int, ident: int) -> str:
    return hashlib.sha256(f"{seed}:{ident}".encode()).hexdigest()


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
