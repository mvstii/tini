"""Maruziyet haritası (saf): ana tür × alt tür × bant hücrelerinde kullanıcının olay sayıları.

Olaylar oy, Unheard ve "sonra dinle"dir. Parçanın sanatçısının türü bilinmiyorsa tür "unknown";
parçanın bandı (yalnız omurga parçalarında vardır) bilinmiyorsa bant "unknown" olur.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

UNKNOWN = "unknown"
KINDS = ("vote", "unheard", "later")


@dataclass(frozen=True)
class ExposureEvt:
    track_id: int
    artist_id: int | None
    kind: str  # "vote" | "unheard" | "later"


def exposure_map(
    events: Iterable[ExposureEvt],
    genre_of: Mapping[int, tuple[str, str | None]],
    band_of: Mapping[int, str],
) -> dict[tuple[str, str, str], dict[str, int]]:
    """(ana tür, alt tür, bant) -> {olay türü: sayı}. `genre_of`: sanatçı -> (ana tür, alt tür)."""
    out: dict[tuple[str, str, str], dict[str, int]] = {}
    for e in events:
        if e.kind not in KINDS:
            raise ValueError(f"bilinmeyen olay türü: {e.kind}")
        main, sub = genre_of.get(e.artist_id, (UNKNOWN, None)) if e.artist_id is not None else (
            UNKNOWN, None,
        )
        key = (main, sub or UNKNOWN, band_of.get(e.track_id, UNKNOWN))
        cell = out.setdefault(key, dict.fromkeys(KINDS, 0))
        cell[e.kind] += 1
    return dict(sorted(out.items()))
