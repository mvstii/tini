"""Oy olaylarından güncel oy, skor ve ağırlık. Saf fonksiyonlar: aynı girdi, aynı çıktı."""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.config import ProfileSettings


@dataclass(frozen=True)
class VoteEvt:
    id: int
    track_id: int
    vote: int
    created_at: datetime


@dataclass(frozen=True)
class ScoredVote:
    track_id: int
    vote: int
    score: float
    weight: float


def current_votes(events: Iterable[VoteEvt]) -> list[VoteEvt]:
    """Parça başına son olay (id sırasıyla); track_id'ye göre sıralı."""
    latest: dict[int, VoteEvt] = {}
    for e in sorted(events, key=lambda e: e.id):
        latest[e.track_id] = e
    return [latest[t] for t in sorted(latest)]


def _midrank_percentile(votes: list[int], v: int) -> float:
    """Aynı grupta v'nin mid-rank persentili (0–1); eşitler aynı değeri alır."""
    below = sum(1 for x in votes if x < v)
    equal = sum(1 for x in votes if x == v)
    return (below + equal / 2) / len(votes)


def _normalized_scores(votes: list[int], cfg: ProfileSettings) -> dict[int, float]:
    """Oy kademesi -> skor. Yeterli oy yoksa soğuk başlangıç skorları döner."""
    base = cfg.vote_scores
    if len(votes) < cfg.normalize_min_votes:
        return {v: base[v] for v in set(votes)}
    out: dict[int, float] = {}
    for positive in (True, False):
        group = [v for v in votes if (base[v] > 0) == positive]
        if not group:
            continue
        lo = min(base[v] for v in set(base) if (base[v] > 0) == positive)
        hi = max(base[v] for v in set(base) if (base[v] > 0) == positive)
        for v in set(group):
            target = lo + _midrank_percentile(group, v) * (hi - lo)
            out[v] = (1 - cfg.normalize_blend) * base[v] + cfg.normalize_blend * target
    return out


def decay_weight(vote: int, created_at: datetime, now: datetime, cfg: ProfileSettings) -> float:
    if vote in cfg.decay_exempt_votes:
        return 1.0
    age_days = max((now - created_at).total_seconds() / 86400, 0.0)
    return max(0.5 ** (age_days / cfg.decay_half_life_days), cfg.decay_floor)


def score_votes(events: Iterable[VoteEvt], now: datetime, cfg: ProfileSettings) -> list[ScoredVote]:
    current = current_votes(events)
    scores = _normalized_scores([e.vote for e in current], cfg)
    return [
        ScoredVote(e.track_id, e.vote, scores[e.vote], decay_weight(e.vote, e.created_at, now, cfg))
        for e in current
    ]
