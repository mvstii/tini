"""Örnekleyicinin veritabanı katmanı (PR-6): maruziyet sayımı, tür bandit θ'sı, omurga
(sonda/joker) adayları ve kartlarının önceden çözülmesi.

Sonda ve joker adayları paylaşılan omurgadan (`genre_seed`) gelir; kart (başlık/kapak) yalnızca
kullanıcıya özel TTL'li `UserTrackMeta`'dan okunur. Kart ISRC'den çözülemezse parça sunulmaz
(sanatçı aramasına düşmek farklı bir parça gösterip oyu yanlış parçaya yazdırırdı).
"""
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.catalog.tags import GenrePairs, load_genre_pairs
from app.config import ProfileSettings, RecommendSettings, get_settings
from app.models import (
    GenreSeed,
    ListenLater,
    TasteProfile,
    Track,
    TrackPopularity,
    UnheardEvent,
    UserTrackMeta,
    VoteEvent,
)
from app.profile.exposure import ExposureEvt, exposure_map
from app.profile.sampler import cell_scores, gumbel_order, seeded_unit
from app.recommend.genre_bandit import genre_outcomes, sample_genre_scores
from app.recommend.genres import GENRES

log = logging.getLogger("tini.probe")

PROBE_BANDS = ("top", "mid")  # tanınır bantlar; joker tüm bantları (niş dahil) kullanır
Cell = tuple[str, str, str]  # (ana tür, alt tür, bant)


def exposure_counts(
    db: Session, user_id, cfg: ProfileSettings, *,
    vote_tracks: Sequence[int] | None = None, genres: GenrePairs | None = None,
) -> dict[Cell, int]:
    """Hücre başına gösterilen kart sayısı (oy + dinlemedim + sonra dinle), en yeni
    `queue_history_size` olay üzerinden. Hücre = (ana tür, alt tür, bant); bilinmeyen "unknown".
    `vote_tracks` (oy olaylarının parçaları, yeniden eskiye) verilirse oy tablosu okunmaz."""
    n = cfg.queue_history_size
    events: list[ExposureEvt] = []
    for kind, model in (("vote", VoteEvent), ("unheard", UnheardEvent)):
        if kind == "vote" and vote_tracks is not None:
            ids_desc: Iterable[int] = vote_tracks[:n]
        else:
            ids_desc = db.scalars(
                select(model.track_id).where(model.user_id == user_id)
                .order_by(model.id.desc()).limit(n)
            )
        for track_id in ids_desc:
            events.append(ExposureEvt(track_id, None, kind))
    events += [
        ExposureEvt(t, None, "later")
        for t in db.scalars(
            select(ListenLater.track_id).where(ListenLater.user_id == user_id)
            .order_by(ListenLater.created_at.desc()).limit(n)
        )
    ]
    ids = {e.track_id for e in events}
    artist_of = dict(db.execute(select(Track.id, Track.artist_id).where(Track.id.in_(ids))).all())
    events = [ExposureEvt(e.track_id, artist_of.get(e.track_id), e.kind) for e in events]
    wanted = {a for a in artist_of.values() if a is not None}
    genre_of = genres.get(wanted) if genres is not None else load_genre_pairs(db, wanted)
    band_of = dict(
        db.execute(
            select(TrackPopularity.track_id, TrackPopularity.band)
            .where(TrackPopularity.track_id.in_(ids))
        ).all()
    )
    return {
        cell: sum(c.values()) for cell, c in exposure_map(events, genre_of, band_of).items()
    }


def genre_theta(
    db: Session, user_id, seed: int, rcfg: RecommendSettings, *,
    votes: Sequence[tuple[int, int]] | None = None,
    artist_of: Mapping[int, int | None] | None = None, genres: GenrePairs | None = None,
) -> dict[str, float]:
    """θ(ana tür): PR-5 tür-bandit örneği (güncel oylardan; Good+/Bad- sayımı).
    `votes` ((parça, güncel oy), parça sıralı) ve `artist_of` (parça -> paylaşılan sanatçı)
    verilirse yeniden okunmaz."""
    rows = votes
    if rows is None:
        rows = db.execute(
            select(VoteEvent.track_id, VoteEvent.vote)
            .where(VoteEvent.user_id == user_id)
            .ext(distinct_on(VoteEvent.track_id))
            .order_by(VoteEvent.track_id, VoteEvent.id.desc())
        ).all()
    if artist_of is None:
        artist_of = dict(
            db.execute(
                select(Track.id, Track.artist_id).where(Track.id.in_([r[0] for r in rows]))
            ).all()
        )
    wanted = {artist_of.get(t) for t, _ in rows} - {None}
    genre_of = genres.get(wanted) if genres is not None else load_genre_pairs(db, wanted)
    pairs = [
        (genre_of[artist_of[t]][0], v) for t, v in rows
        if artist_of.get(t) is not None and artist_of[t] in genre_of
    ]
    return sample_genre_scores(genre_outcomes(pairs), list(GENRES), seed, rcfg)


def genre_shares(body: Mapping | None) -> dict[str, float]:
    """Profil gövdesindeki ana tür payları (yoksa boş)."""
    main = ((body or {}).get("genres") or {}).get("main") or []
    return {m["genre"]: float(m["share"]) for m in main}


def profile_genre_shares(db: Session, user_id) -> dict[str, float]:
    """Son profil anlık görüntüsündeki ana tür payları (yoksa boş)."""
    return genre_shares(
        db.scalar(
            select(TasteProfile.body).where(TasteProfile.user_id == user_id)
            .order_by(TasteProfile.version.desc()).limit(1)
        )
    )


def _seed_rows(db: Session, user_id, now: datetime, exclude: set[int], ready: bool):
    """Omurga parçaları (ISRC'li, sanatçılı). `ready`: yalnız süresi dolmamış kartı olanlar;
    değilse kartı olmayanlar (çözülecekler)."""
    q = (
        select(
            GenreSeed.sub_genre, GenreSeed.main_genre, GenreSeed.band, GenreSeed.track_id,
            GenreSeed.artist_id, Track.isrc, UserTrackMeta.title, UserTrackMeta.artist_names,
            UserTrackMeta.image_url,
        )
        .join(Track, Track.id == GenreSeed.track_id)
        .outerjoin(
            UserTrackMeta,
            (UserTrackMeta.track_id == GenreSeed.track_id) & (UserTrackMeta.user_id == user_id)
            & (UserTrackMeta.expires_at > now),
        )
        .where(Track.isrc.is_not(None))
    )
    q = q.where(UserTrackMeta.track_id.is_not(None) if ready else UserTrackMeta.track_id.is_(None))
    rows = db.execute(q.order_by(GenreSeed.sub_genre, GenreSeed.track_id)).all()
    return [r for r in rows if r.track_id not in exclude]


def _pick_by_cells(
    rows, shown: dict[Cell, int], theta: dict[str, float], bands: Iterable[str],
    need: int, tau: float, kappa: float, seed: int, uniform: bool,
) -> list:
    """Hücreleri Gumbel-top-k sırasıyla gezip her turda hücreden bir parça alır."""
    by_cell: dict[Cell, list] = {}
    for r in rows:
        if r.band in bands:
            by_cell.setdefault((r.main_genre, r.sub_genre, r.band), []).append(r)
    if not by_cell or need <= 0:
        return []
    for cell, lst in by_cell.items():
        lst.sort(key=lambda r: seeded_unit(seed, f"{cell}:{r.track_id}"))
    counts = {c: shown.get(c, 0) for c in by_cell}
    scores = (
        dict.fromkeys(by_cell, 0.0) if uniform else cell_scores(counts, theta, kappa)
    )
    order = gumbel_order(scores, tau, seed)
    out: list = []
    depth = 0
    while len(out) < need and any(len(by_cell[c]) > depth for c in order):
        for cell in order:
            if len(by_cell[cell]) > depth and len(out) < need:
                out.append((cell, by_cell[cell][depth]))
        depth += 1
    return out


def _coverage_item(cell: Cell, shown: int, r, source: str) -> dict:
    """Kart öğesi; gerekçe kapsama hesabından gelir (D4): hangi hücre ne kadar örneklendi."""
    return {
        "track": r.track_id, "title": r.title, "artists": r.artist_names, "image": r.image_url,
        "source": source, "artist": r.artist_id, "genre": cell[0], "sub": cell[1],
        "reasons": [{
            "kind": "coverage", "main_genre": cell[0], "sub_genre": cell[1], "band": cell[2],
            "shown": shown,
        }],
    }


def probe_and_joker(
    db: Session, user_id, now: datetime, exclude: set[int], need_probe: int, need_joker: int,
    cfg: ProfileSettings, theta: dict[str, float], seed: int, *,
    vote_tracks: Sequence[int] | None = None, genres: GenrePairs | None = None,
) -> tuple[list[dict], list[dict]]:
    """Hazır (kartı çözülmüş) omurga parçalarından sonda ve joker kartları. Aynı parça iki
    kaynakta çıkmaz. Sonda: tanınır bantlar, skor = κ/√(1+o)+θ; joker: tüm bantlar, tekdüze."""
    rows = _seed_rows(db, user_id, now, exclude, ready=True)
    if not rows:
        return [], []
    shown = exposure_counts(db, user_id, cfg, vote_tracks=vote_tracks, genres=genres)
    probe = _pick_by_cells(
        rows, shown, theta, PROBE_BANDS, need_probe, cfg.queue_gumbel_tau,
        cfg.queue_coverage_kappa, seed, uniform=False,
    )
    taken = {r.track_id for _, r in probe}
    rest = [r for r in rows if r.track_id not in taken]
    joker = _pick_by_cells(
        rest, shown, theta, ("top", "mid", "tail"), need_joker, 1.0,
        cfg.queue_coverage_kappa, seed + 104729, uniform=True,
    )
    return (
        [_coverage_item(c, shown.get(c, 0), r, "probe") for c, r in probe],
        [_coverage_item(c, shown.get(c, 0), r, "joker") for c, r in joker],
    )


def resolve_seed_cards(
    db: Session, user_id, service: Callable, now: datetime, cfg: ProfileSettings,
    rcfg: RecommendSettings, budget: int, seed: int,
) -> bool:
    """Doldurucu adımı: kartı olmayan omurga parçalarından en çok `budget` tanesinin kartını
    ISRC'den çözüp `UserTrackMeta`'ya yazar. Hazır omurga kartı `buffer_target`'a ulaştıysa
    bir şey yapmaz. Hata (429/ağ) olursa False döner; kalanlar sonraki turda denenir."""
    voted = set(db.scalars(select(VoteEvent.track_id).where(VoteEvent.user_id == user_id)))
    later = set(db.scalars(select(ListenLater.track_id).where(ListenLater.user_id == user_id)))
    exclude = voted | later
    if len(_seed_rows(db, user_id, now, exclude, ready=True)) >= cfg.buffer_target:
        return True
    rows = _seed_rows(db, user_id, now, exclude, ready=False)
    shown = exposure_counts(db, user_id, cfg)
    theta = genre_theta(db, user_id, seed, rcfg)
    picks = _pick_by_cells(
        rows, shown, theta, ("top", "mid", "tail"), budget, cfg.queue_gumbel_tau,
        cfg.queue_coverage_kappa, seed, uniform=False,
    )
    if not picks:
        return True
    svc = service()
    if svc is None:
        return True
    ttl = timedelta(seconds=get_settings().spotify_cache_ttl_seconds)
    for _, r in picks:
        try:
            card = svc.find_card(r.isrc, "", isrc_only=True)
        except (httpx.HTTPError, PermissionError):
            return False
        if card is None:
            continue
        db.merge(UserTrackMeta(
            user_id=user_id, track_id=r.track_id, title=card.title,
            artist_names=list(card.artist_names), image_url=card.image_url,
            fetched_at=now, expires_at=now + ttl,
        ))
    return True
