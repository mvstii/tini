"""Unheard durum makinesi (saf): olay kaydından parça başına durum türetilir.

Durumlar: pooled (ilk sola kaydırma), presented (havuzdan yeniden sunuldu), awaiting (Faz 5 S2:
oylama bekliyor), expired (N sunumda oy gelmedi). "Oylandı" ayrı durum değildir: son
Unheard olayından sonra gelen oy parçayı havuzdan çıkarır.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

STATES = ("pooled", "presented", "awaiting", "expired")
_PRESENTING = ("pooled", "presented")  # kullanıcıya gösterilip oylanmadan geçilen olaylar


@dataclass(frozen=True)
class UnheardEvt:
    id: int
    track_id: int
    state: str
    created_at: datetime


@dataclass(frozen=True)
class UnheardStatus:
    track_id: int
    state: str
    presentations: int
    last_at: datetime


def next_state(history_count: int) -> str:
    """Parçanın önceki Unheard olay sayısına göre yeni olayın durumu."""
    return "pooled" if history_count == 0 else "presented"


def resolve(
    events: Iterable[UnheardEvt], last_vote_at: Mapping[int, datetime], expire_after: int
) -> list[UnheardStatus]:
    """Havuzdaki parçaların güncel durumu (track_id'ye göre sıralı).

    last_vote_at: parça -> son oy zamanı. Son Unheard olayından sonra oy verilmişse parça
    havuzdan çıkar. Sunum sayısı expire_after'a ulaşırsa durum `expired` olur.
    """
    by_track: dict[int, list[UnheardEvt]] = {}
    for e in sorted(events, key=lambda e: e.id):
        by_track.setdefault(e.track_id, []).append(e)
    out = []
    for track in sorted(by_track):
        evs = by_track[track]
        last = evs[-1]
        voted = last_vote_at.get(track)
        if voted is not None and voted >= last.created_at:
            continue
        n = sum(1 for e in evs if e.state in _PRESENTING)
        out.append(
            UnheardStatus(
                track, "expired" if n >= expire_after else last.state, n, last.created_at
            )
        )
    return out
