"""POST /votes, GET /votes/current. Oy silinmez; değişiklik yeni olaydır."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ProfileSettings, get_profile_settings
from app.deps import current_user, get_db
from app.models import User, UserTrackLink, VoteEvent
from app.profile.scoring import VoteEvt, score_votes

router = APIRouter(prefix="/votes")


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
