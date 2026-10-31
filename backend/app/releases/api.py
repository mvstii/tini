"""Takip listesi: GET /releases/following, PUT/DELETE /releases/following/{artist_id}."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import RecommendSettings, get_recommend_settings
from app.deps import current_user, get_db
from app.models import Artist, FollowedArtist, Release, ReleaseArtist, User
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


@router.get("/new")
def new_releases(
    days: int | None = None,
    limit: int = 50,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
) -> dict:
    """"Yeni" akışı: takip edilen sanatçıların pencere içindeki yayınları, yeniden eskiye."""
    follows = user_follows(db, user.id)
    since = datetime.now(UTC).date() - timedelta(days=min(days or cfg.fresh_window_days, 365))
    rows = db.execute(
        select(Release, Artist.id, Artist.name)
        .join(ReleaseArtist, ReleaseArtist.release_id == Release.id)
        .join(Artist, Artist.id == ReleaseArtist.artist_id)
        .where(ReleaseArtist.artist_id.in_(list(follows)), Release.first_release_date >= since)
        .order_by(Release.first_release_date.desc(), Release.id, Artist.id)
    ).all()
    items, seen = [], set()
    for r, aid, name in rows:
        if r.id in seen:
            continue
        seen.add(r.id)
        items.append({
            "release_id": r.id, "title": r.title, "type": r.primary_type,
            "released": r.first_release_date.isoformat(), "artist_id": aid, "artist": name,
            "follow": follows[aid],
        })
    return {"items": items[: max(min(limit, 200), 1)], "total": len(items)}
