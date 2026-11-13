"""Takip listesi: GET /releases/following, PUT/DELETE /releases/following/{artist_id}."""
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import (
    RecommendSettings,
    ReleasesSettings,
    get_recommend_settings,
    get_releases_settings,
)
from app.deps import current_user, get_db
from app.models import Artist, FollowedArtist, Release, ReleaseArtist, User
from app.preview import get_deezer
from app.releases.service import user_follows
from app.sources.deezer import DeezerClient
from app.sources.http import SourceError

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


def cover_url(base: str, rel: Release) -> str:
    """Cover Art Archive kapağı (release-group düzeyi); yoksa istemci yer tutucu gösterir."""
    return f"{base.rstrip('/')}/release-group/{rel.mb_rgid}/front-250"


@router.get("/new")
def new_releases(
    days: int | None = None,
    limit: int = 50,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    rcfg: ReleasesSettings = Depends(get_releases_settings),
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
            "follow": follows[aid], "cover": cover_url(rcfg.cover_base_url, r),
        })
    return {"items": items[: max(min(limit, 200), 1)], "total": len(items)}


# Yayın başına parça listesi (Deezer): yalnızca bellekte, süreli; kalıcı saklanmaz.
_TRACKS: dict[int, tuple[float, list[dict]]] = {}


def _tracks_of(deezer: DeezerClient, rel: Release, artist: str, ttl: float) -> list[dict]:
    hit = _TRACKS.get(rel.id)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    try:
        tracks = deezer.album_tracks(artist, rel.title)
    except SourceError:
        return []  # geçici hata önbelleğe yazılmaz
    _TRACKS[rel.id] = (time.monotonic() + ttl, tracks)
    return tracks


@router.get("/new-tracks")
def new_tracks(
    days: int | None = None,
    limit: int = 40,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: ReleasesSettings = Depends(get_releases_settings),
    deezer: DeezerClient = Depends(get_deezer),
) -> dict:
    """"Bu hafta çıkanlar": takip edilen sanatçıların son günlerdeki yayınları, parça parça.
    Her parçanın `deezer_id`'si /preview?deezer_id= ile çalınır."""
    follows = user_follows(db, user.id)
    since = datetime.now(UTC).date() - timedelta(days=min(days or cfg.new_tracks_days, 60))
    rows = db.execute(
        select(Release, Artist.name, Artist.id)
        .join(ReleaseArtist, ReleaseArtist.release_id == Release.id)
        .join(Artist, Artist.id == ReleaseArtist.artist_id)
        .where(ReleaseArtist.artist_id.in_(list(follows)), Release.first_release_date >= since)
        .order_by(Release.first_release_date.desc(), Release.id, Artist.id)
    ).all()
    releases, seen = [], set()
    for r, name, aid in rows:
        if r.id not in seen and name:
            seen.add(r.id)
            releases.append((r, name, aid))
    ttl = cfg.tracks_cache_hours * 3600
    items: list[dict] = []
    for r, artist, aid in releases[: cfg.new_tracks_max_releases]:
        for t in _tracks_of(deezer, r, artist, ttl):
            items.append({
                "deezer_id": t["id"], "title": t["title"], "artist": artist, "artist_id": aid,
                "release": r.title, "type": r.primary_type,
                "released": r.first_release_date.isoformat(),
                "cover": cover_url(cfg.cover_base_url, r),
            })
    return {"items": items[: max(min(limit, 200), 1)], "releases": len(releases)}
