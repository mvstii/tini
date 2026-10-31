"""Taze liste sıralaması (saf): takip edilen sanatçıların son yayınları -> gerekçeli sıra.

Skor = sanatçının PPR skoru (negatifse 0) x yenilik çarpanı 0.5^(yaş/yarılanma). Gerekçe, sanatçının
PPR doğrusal ayrışımından gelir. Aynı yayın ve aynı sanatçı listede bir kez yer alır.
"""
from dataclasses import dataclass
from datetime import date

from app.config import RecommendSettings
from app.recommend.ppr import Reason


@dataclass(frozen=True)
class FreshRelease:
    release_id: int
    artist_id: int
    released: date


@dataclass(frozen=True)
class FreshItem:
    release_id: int
    artist_id: int
    released: date
    score: float
    reasons: list[Reason]


def recency(released: date, today: date, half_life_days: float) -> float:
    age = max((today - released).days, 0)
    return 0.5 ** (age / half_life_days)


def rank_fresh(
    releases: list[FreshRelease],
    artist: dict[int, tuple[float, list[Reason]]],
    today: date,
    cfg: RecommendSettings,
) -> list[FreshItem]:
    """Pencere dışı yayınlar elenir; sanatçı başına en iyi yayın kalır; en çok fresh_list_size."""
    window_start = today.toordinal() - cfg.fresh_window_days
    scored: list[FreshItem] = []
    for r in releases:
        if r.released.toordinal() < window_start or r.released > today:
            continue
        base, reasons = artist.get(r.artist_id, (0.0, []))
        score = max(base, 0.0) * recency(r.released, today, cfg.fresh_half_life_days)
        scored.append(FreshItem(r.release_id, r.artist_id, r.released, score, reasons))
    scored.sort(key=lambda i: (-i.score, -i.released.toordinal(), i.release_id, i.artist_id))
    out: list[FreshItem] = []
    seen_releases: set[int] = set()
    seen_artists: set[int] = set()
    for i in scored:
        if i.release_id in seen_releases or i.artist_id in seen_artists:
            continue
        seen_releases.add(i.release_id)
        seen_artists.add(i.artist_id)
        out.append(i)
        if len(out) == cfg.fresh_list_size:
            break
    return out
