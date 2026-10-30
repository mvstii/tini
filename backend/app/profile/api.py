"""POST /votes, GET /votes/current. Oy silinmez; değişiklik yeni olaydır."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GraphSettings, ProfileSettings, get_graph_settings, get_profile_settings
from app.deps import current_user, get_db
from app.models import TasteProfile, User, UserTrackLink, VoteEvent
from app.profile.scoring import VoteEvt, score_votes
from app.profile.service import rebuild_profile

router = APIRouter(prefix="/votes")
profile_router = APIRouter(prefix="/profile")


class VoteIn(BaseModel):
    track: int
    vote: int = Field(ge=1, le=6)


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
        raise HTTPException(404, "Parça kütüphanede yok")
    ev = VoteEvent(user_id=user.id, track_id=body.track, vote=body.vote)
    db.add(ev)
    db.commit()
    return {"id": ev.id, "track": ev.track_id, "vote": ev.vote}


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
