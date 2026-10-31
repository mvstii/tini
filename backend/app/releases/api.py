"""Takip listesi: GET /releases/following, PUT/DELETE /releases/following/{artist_id}."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Artist, FollowedArtist, User
from app.releases.service import user_follows

router = APIRouter(prefix="/releases")


@router.get("/following")
def following(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    follows = user_follows(db, user.id)
    rows = db.execute(
        select(Artist.id, Artist.name, Artist.mbid).where(Artist.id.in_(follows))
    ).all()
    items = [
        {"artist_id": a, "name": n, "source": follows[a], "trackable": m is not None}
        for a, n, m in rows
    ]
    items.sort(key=lambda i: (i["name"] or "", i["artist_id"]))
    return {"items": items}


def _set(db: Session, user: User, artist_id: int, source: str) -> None:
    if db.get(Artist, artist_id) is None:
        raise HTTPException(404, "Sanatçı yok")
    stmt = insert(FollowedArtist).values(user_id=user.id, artist_id=artist_id, source=source)
    db.execute(stmt.on_conflict_do_update(
        index_elements=["user_id", "artist_id"], set_={"source": source}
    ))
    db.commit()


@router.put("/following/{artist_id}")
def follow(
    artist_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    _set(db, user, artist_id, "manual")
    return {"artist_id": artist_id, "source": "manual"}


@router.delete("/following/{artist_id}", status_code=204)
def unfollow(
    artist_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    _set(db, user, artist_id, "muted")
    return Response(status_code=204)
