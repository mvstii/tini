"""Slot sonuçları (saf): liste öğelerinden, oy ve itiraz olaylarından türetilir; ek tablo yok.

Başarı: öğenin sanatçısına liste tarihinden sonra verilen son oy Good+ (>= 4).
Başarısızlık: gerekçe itirazı veya liste sonrası son oy Bad- (<= 2). Meh ve oysuz öğe henüz sonuç
sayılmaz. İtiraz, sonraki oydan bağımsız olarak başarısızlıktır.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ItemRef:
    list_id: int
    position: int
    artist_id: int
    slot: str
    list_created_at: datetime


@dataclass(frozen=True)
class ArtistVote:
    id: int
    artist_id: int
    vote: int
    created_at: datetime


def derive_outcomes(
    items: Iterable[ItemRef],
    votes: Iterable[ArtistVote],
    feedback: set[tuple[int, int]],
    good: int = 4,
    bad: int = 2,
) -> dict[str, tuple[int, int]]:
    by_artist: dict[int, list[ArtistVote]] = {}
    for v in sorted(votes, key=lambda v: v.id):
        by_artist.setdefault(v.artist_id, []).append(v)
    out: dict[str, list[int]] = {}
    for it in items:
        tally = out.setdefault(it.slot, [0, 0])
        if (it.list_id, it.position) in feedback:
            tally[1] += 1
            continue
        later = [v for v in by_artist.get(it.artist_id, []) if v.created_at > it.list_created_at]
        if not later:
            continue
        last = later[-1].vote
        if last >= good:
            tally[0] += 1
        elif last <= bad:
            tally[1] += 1
    return {s: (a, b) for s, (a, b) in out.items()}
