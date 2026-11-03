"""POST /votes, GET /votes/current. Oy silinmez; değişiklik yeni olaydır."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.config import (
    GraphSettings,
    ProfileSettings,
    RecommendSettings,
    get_graph_settings,
    get_profile_settings,
    get_recommend_settings,
)
from app.deps import current_user, get_db
from app.models import (
    GeneratedList,
    ListItem,
    TasteProfile,
    Track,
    UnheardEvent,
    User,
    UserTrackLink,
    UserTrackMeta,
    VoteEvent,
)
from app.profile.active import order_active, order_unresolved
from app.profile.active_service import artist_uncertainties, mark_awaiting
from app.profile.queue import pick_versions
from app.profile.scoring import VoteEvt, score_votes
from app.profile.service import rebuild_profile, unheard_statuses
from app.profile.unheard import next_state

router = APIRouter(prefix="/votes")
profile_router = APIRouter(prefix="/profile")


class VoteIn(BaseModel):
    track: int
    vote: int = Field(ge=1, le=6)


class UnheardIn(BaseModel):
    track: int


def _events(db: Session, user_id) -> list[VoteEvt]:
    rows = db.execute(
        select(VoteEvent.id, VoteEvent.track_id, VoteEvent.vote, VoteEvent.created_at).where(
            VoteEvent.user_id == user_id
        )
    ).all()
    return [VoteEvt(*r) for r in rows]


@router.post("", status_code=201)
def cast_vote(
    body: VoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    owned = db.scalar(
        select(UserTrackLink.id)
        .where(UserTrackLink.user_id == user.id, UserTrackLink.track_id == body.track)
        .limit(1)
    )
    if owned is None:
        # Kütüphane dışı ama kullanıcıya üretilmiş bir listedeki öneri de oylanabilir.
        owned = db.scalar(
            select(ListItem.list_id)
            .join(GeneratedList, GeneratedList.id == ListItem.list_id)
            .where(GeneratedList.user_id == user.id, ListItem.track_id == body.track)
            .limit(1)
        )
    if owned is None:
        raise HTTPException(404, "Parça kütüphanede ya da listelerinde yok")
    ev = VoteEvent(user_id=user.id, track_id=body.track, vote=body.vote)
    db.add(ev)
    db.commit()
    return {"id": ev.id, "track": ev.track_id, "vote": ev.vote}


@router.post("/unheard", status_code=201)
def mark_unheard(
    body: UnheardIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: ProfileSettings = Depends(get_profile_settings),
) -> dict:
    """Sola kaydırma: "bu parçayı dinlemedim". Yeni bir Unheard olayı yazılır (silinmez)."""
    owned = db.scalar(
        select(UserTrackLink.id)
        .where(UserTrackLink.user_id == user.id, UserTrackLink.track_id == body.track)
        .limit(1)
    )
    if owned is None:
        raise HTTPException(404, "Parça kütüphanede yok")
    prior = db.scalar(
        select(func.count())
        .select_from(UnheardEvent)
        .where(UnheardEvent.user_id == user.id, UnheardEvent.track_id == body.track)
    )
    ev = UnheardEvent(user_id=user.id, track_id=body.track, state=next_state(prior))
    db.add(ev)
    db.commit()
    status = next(
        (s for s in unheard_statuses(db, user.id, cfg) if s.track_id == body.track), None
    )
    return {
        "id": ev.id,
        "track": ev.track_id,
        "state": status.state if status else ev.state,
        "presentations": status.presentations if status else 0,
    }


@router.get("/queue")
def queue(
    seed: int = 0,
    limit: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: ProfileSettings = Depends(get_profile_settings),
    rcfg: RecommendSettings = Depends(get_recommend_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    """Oylanacak parçalar. Başlık/sanatçı kullanıcıya özel önbellekten gelir; süresi dolmuş
    önbellekli parçalar atlanır ve `stale` ile sayılır (istemci kütüphaneyi yeniden aktarır)."""
    size = min(limit or cfg.queue_size, cfg.queue_max_size)
    voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user.id)
    rows = db.execute(
        select(
            Track.id, Track.artist_id, UserTrackMeta.title, UserTrackMeta.artist_names,
            UserTrackMeta.expires_at, UserTrackMeta.image_url,
        )
        .join(UserTrackLink, UserTrackLink.track_id == Track.id)
        .outerjoin(
            UserTrackMeta,
            (UserTrackMeta.track_id == Track.id) & (UserTrackMeta.user_id == user.id),
        )
        .where(
            UserTrackLink.user_id == user.id,
            Track.id.not_in(voted),
        )
        .ext(distinct_on(Track.id))
        .order_by(Track.id)
    ).all()
    now = datetime.now(UTC)
    fresh = {r[0]: r for r in rows if r[4] is not None and r[4] > now}
    voted_artists = set(
        db.scalars(
            select(Track.artist_id)
            .join(VoteEvent, VoteEvent.track_id == Track.id)
            .where(VoteEvent.user_id == user.id, Track.artist_id.is_not(None))
        )
    )
    statuses = unheard_statuses(db, user.id, cfg)
    expired = {s.track_id for s in statuses if s.state == "expired"}
    pool = {s.track_id for s in statuses} - expired
    # Yalnızca önbelleği dolmuş parçalar "eski" sayılır (yenileme bunları düzeltir); havuzda
    # süresi dolmuş parçalar kütüphane yenilemesiyle geri gelmez, sayılmaz.
    stale = sum(1 for r in rows if r[0] not in fresh and r[0] not in expired)
    fresh = {t: r for t, r in fresh.items() if t not in expired}
    voted_meta = db.execute(
        select(UserTrackMeta.title, UserTrackMeta.artist_names).where(
            UserTrackMeta.user_id == user.id, UserTrackMeta.track_id.in_(voted)
        )
    ).all()
    keep = pick_versions(
        [(t, r[2], r[3]) for t, r in fresh.items()], voted_meta, pool, cfg.queue_version_markers
    )
    fresh = {t: r for t, r in fresh.items() if t in keep}
    cands = [(r[0], r[1]) for r in fresh.values() if r[1] is not None]
    unresolved = [t for t, r in fresh.items() if r[1] is None]
    unc = artist_uncertainties(db, user.id, {a for _, a in cands}, cfg, rcfg, gcfg)
    order = order_active(cands, unc, pool & set(fresh), voted_artists, seed, cfg)
    order = (order + order_unresolved(unresolved, pool, seed))[:size]
    mark_awaiting(db, user.id, pool & set(order), statuses)
    return {
        "algo_version": cfg.queue_algo_version,
        "remaining": len(fresh),
        "stale": stale,
        "items": [
            {"track": t, "title": fresh[t][2], "artists": fresh[t][3], "image": fresh[t][5]}
            for t in order
        ],
    }


@router.get("/history")
def history(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Parça başına güncel oy (son olay), yeniden eskiye. Başlık varsa önbellekten."""
    latest = (
        select(VoteEvent.track_id, VoteEvent.vote, VoteEvent.created_at)
        .where(VoteEvent.user_id == user.id)
        .ext(distinct_on(VoteEvent.track_id))
        .order_by(VoteEvent.track_id, VoteEvent.id.desc())
        .subquery()
    )
    total = db.scalar(select(func.count()).select_from(latest))
    rows = db.execute(
        select(latest.c.track_id, latest.c.vote, latest.c.created_at, UserTrackMeta.title,
               UserTrackMeta.artist_names)
        .outerjoin(
            UserTrackMeta,
            (UserTrackMeta.track_id == latest.c.track_id) & (UserTrackMeta.user_id == user.id),
        )
        .order_by(latest.c.created_at.desc(), latest.c.track_id)
        .limit(min(max(limit, 1), 200))
        .offset(max(offset, 0))
    ).all()
    return {
        "total": total,
        "items": [
            {"track": t, "vote": v, "voted_at": at.isoformat(), "title": title,
             "artists": names}
            for t, v, at, title, names in rows
        ],
    }


@router.get("/current")
def current(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: ProfileSettings = Depends(get_profile_settings),
) -> dict:
    scored = score_votes(_events(db, user.id), datetime.now(UTC), cfg)
    return {
        "algo_version": cfg.profile_algo_version,
        "votes": [
            {"track": s.track_id, "vote": s.vote, "score": round(s.score, 6),
             "weight": round(s.weight, 6)}
            for s in scored
        ],
    }


def _out(row: TasteProfile) -> dict:
    return {"version": row.version, "created_at": row.created_at.isoformat(), **row.body}


@profile_router.post("/rebuild", status_code=201)
def rebuild(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: ProfileSettings = Depends(get_profile_settings),
    graph_cfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    return _out(rebuild_profile(db, user.id, datetime.now(UTC), cfg, graph_cfg))


@profile_router.get("")
def latest(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(
        select(TasteProfile)
        .where(TasteProfile.user_id == user.id)
        .order_by(TasteProfile.version.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(404, "Henüz profil üretilmedi")
    return _out(row)
