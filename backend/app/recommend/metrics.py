"""Faz 5 değerlendirme ölçütleri (saf): olay kayıtlarından hesaplanır, veritabanına dokunmaz.

Liste öğesinin sonucu, sanatçısına liste tarihinden sonra verilen son oydur (`outcomes.py` ile
aynı tanım). Örnek sayıları her zaman raporlanır; `min_sample` altındaki oranlar güvenilmez
sayılır (rapor "yetersiz veri" der).
"""
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from app.recommend.outcomes import ArtistVote


@dataclass(frozen=True)
class EvalItem:
    list_id: int
    position: int
    artist_id: int
    slot: str
    score: float
    list_created_at: datetime


@dataclass(frozen=True)
class TrackVote:
    id: int
    track_id: int
    vote: int
    created_at: datetime


@dataclass(frozen=True)
class PoolEvent:
    track_id: int
    state: str
    created_at: datetime


@dataclass
class SlotStat:
    presented: int = 0
    voted: int = 0  # liste sonrası oyu olan öğe
    good: int = 0  # liste sonrası son oy >= good
    objected: int = 0  # gerekçe itirazı

    @property
    def good_rate(self) -> float | None:
        return self.good / self.voted if self.voted else None


@dataclass
class Report:
    slots: dict[str, SlotStat] = field(default_factory=dict)
    overall: SlotStat = field(default_factory=SlotStat)
    rank_corr: float | None = None  # skor <-> sonraki oy (Spearman)
    rank_corr_n: int = 0
    unheard_pooled: int = 0
    unheard_voted: int = 0
    unheard_good: int = 0

    @property
    def objection_rate(self) -> float | None:
        o = self.overall
        return o.objected / o.presented if o.presented else None

    @property
    def unheard_good_rate(self) -> float | None:
        return self.unheard_good / self.unheard_voted if self.unheard_voted else None


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1  # bağlarda ortalama sıra
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Sıra korelasyonu; 3'ten az çift veya sabit dizi için None."""
    n = len(xs)
    if n < 3:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy) ** 0.5


def evaluate_items(
    items: Iterable[EvalItem],
    votes: Iterable[ArtistVote],
    feedback: set[tuple[int, int]],
    good: int = 4,
) -> Report:
    by_artist: dict[int, list[ArtistVote]] = {}
    for v in sorted(votes, key=lambda v: v.id):
        by_artist.setdefault(v.artist_id, []).append(v)
    rep = Report()
    scores: list[float] = []
    last_votes: list[float] = []
    for it in items:
        stat = rep.slots.setdefault(it.slot, SlotStat())
        for s in (stat, rep.overall):
            s.presented += 1
            if (it.list_id, it.position) in feedback:
                s.objected += 1
        later = [v for v in by_artist.get(it.artist_id, []) if v.created_at > it.list_created_at]
        if not later:
            continue
        last = later[-1].vote
        for s in (stat, rep.overall):
            s.voted += 1
            if last >= good:
                s.good += 1
        if it.slot != "fresh":  # albüm kartı skoru PPR skoru değil, yenilik çarpanlıdır
            scores.append(it.score)
            last_votes.append(float(last))
    rep.rank_corr = spearman(scores, last_votes)
    rep.rank_corr_n = len(scores)
    return rep


def evaluate_unheard(
    rep: Report, pool_events: Iterable[PoolEvent], votes: Iterable[TrackVote], good: int = 4
) -> None:
    """Havuza giren (sola kaydırılan) parçalardan sonradan oylananların Good+ oranı."""
    first_pooled: dict[int, datetime] = {}
    for e in pool_events:
        if e.state == "pooled":
            first_pooled[e.track_id] = min(
                e.created_at, first_pooled.get(e.track_id, e.created_at)
            )
    last: dict[int, TrackVote] = {}
    for v in sorted(votes, key=lambda v: v.id):
        t = first_pooled.get(v.track_id)
        if t is not None and v.created_at > t:
            last[v.track_id] = v
    rep.unheard_pooled = len(first_pooled)
    rep.unheard_voted = len(last)
    rep.unheard_good = sum(1 for v in last.values() if v.vote >= good)


def _pct(x: float | None) -> str:
    return "—" if x is None else f"%{x * 100:.0f}"


def format_report(rep: Report, min_sample: int) -> list[str]:
    def rate(s: SlotStat) -> str:
        warn = " (yetersiz veri)" if s.voted < min_sample else ""
        return f"Good+ {_pct(s.good_rate)} ({s.good}/{s.voted} oylanan){warn}"

    o = rep.overall
    lines = [
        f"Sunulan öğe: {o.presented}, liste sonrası oylanan: {o.voted}",
        f"Önerilenin Good+ oranı: {rate(o)}",
    ]
    for name in ("familiar", "unheard", "explore", "fresh"):
        s = rep.slots.get(name)
        if s is None:
            continue
        if name == "fresh":  # albüm kartı, oylanamaz
            lines.append(
                f"  {name:<9} sunulan {s.presented}, sanatçıya sonradan Good+ {s.good}/{s.voted}"
            )
        else:
            lines.append(f"  {name:<9} sunulan {s.presented}; {rate(s)}")
    corr_warn = " (yetersiz veri)" if rep.rank_corr_n < min_sample else ""
    corr = "—" if rep.rank_corr is None else f"{rep.rank_corr:+.2f}"
    lines.append(f"Skor ↔ sonraki oy sıra korelasyonu: {corr} (n={rep.rank_corr_n}){corr_warn}")
    lines.append(
        f"Gerekçe itiraz oranı: {_pct(rep.objection_rate)} ({o.objected}/{o.presented})"
    )
    warn = " (yetersiz veri)" if rep.unheard_voted < min_sample else ""
    lines.append(
        f"Unheard'in sonradan Good+ oranı: {_pct(rep.unheard_good_rate)} "
        f"({rep.unheard_good}/{rep.unheard_voted} oylanan, havuz {rep.unheard_pooled}){warn}"
    )
    return lines
