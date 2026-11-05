"""Parça arama, "Sonra dinle" listesi ve parça yorumları.

Servis verisi (başlık/sanatçı/kapak) yalnızca kullanıcıya özel TTL'li `UserTrackMeta` önbelleğine
yazılır; paylaşılan katalogda yalnızca ISRC durur. Yorum metni kullanıcının kendi verisidir."""
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.connect import get_http
from app.deps import current_user, get_db
from app.models import ListenLater, Track, TrackComment, User, UserTrackMeta
from app.profile.suggest import connected_adapter
from app.recommend.api import _service_adapter

search_router = APIRouter(tags=["search"])
later_router = APIRouter(prefix="/later", tags=["later"])
comments_router = APIRouter(tags=["comments"])

_REFRESH_MAX = 10  # istek başına en çok bu kadar servis çağrısı (429 koruması)


def _ttl() -> timedelta:
    return timedelta(seconds=get_settings().spotify_cache_ttl_seconds)


def _put_meta(db: Session, user_id, track_id: int, title, artists, image, now) -> UserTrackMeta:
    return db.merge(UserTrackMeta(
        user_id=user_id, track_id=track_id, title=title, artist_names=list(artists),
        image_url=image, fetched_at=now, expires_at=now + _ttl(),
    ))


def track_cards(
    db: Session, user: User, track_ids: list[int], http: httpx.Client, now: datetime | None = None
) -> dict[int, dict]:
    """Parça başına {track, title, artists, image}. Süresi dolmuş/eksik önbellek bağlı servisten
    yenilenir; servis yoksa ya da yanıt vermezse başlık null döner."""
    now = now or datetime.now(UTC)
    if not track_ids:
        return {}
    metas = {
        m.track_id: m
        for m in db.scalars(
            select(UserTrackMeta).where(
                UserTrackMeta.user_id == user.id, UserTrackMeta.track_id.in_(track_ids),
                UserTrackMeta.expires_at > now,
            )
        )
    }
    isrcs = dict(db.execute(select(Track.id, Track.isrc).where(Track.id.in_(track_ids))).all())
    svc, calls = None, 0
    for tid in track_ids:
        if tid in metas or calls >= _REFRESH_MAX:
            continue
        svc = svc or connected_adapter(db, user, http)
        if svc is None:
            break
        calls += 1
        try:
            card = svc.find_card(isrcs.get(tid), "")
        except (httpx.HTTPError, PermissionError):
            break
        if card is not None:
            metas[tid] = _put_meta(
                db, user.id, tid, card.title, card.artist_names, card.image_url, now
            )
    db.commit()
    return {
        tid: {
            "track": tid,
            "title": metas[tid].title if tid in metas else None,
            "artists": list(metas[tid].artist_names) if tid in metas else [],
            "image": metas[tid].image_url if tid in metas else None,
        }
        for tid in track_ids
    }


def _service_error(e: httpx.HTTPError, what: str) -> HTTPException:
    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403):
        return HTTPException(409, f"{what}: servis yetkisi reddedildi")
    return HTTPException(502, f"{what}: servise ulaşılamadı")


# ---- Arama -------------------------------------------------------------------------------------


@search_router.get("/search")
def search(
    q: str = Query(min_length=2, max_length=100),
    service: str = "spotify",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> dict:
    """Bağlı servisin aramasından parçalar. Katalogda yalnızca ISRC yazılır; başlık/sanatçı/kapak
    kullanıcıya özel TTL önbelleğine girer."""
    adapter = _service_adapter(db, user, service, http)
    try:
        found = adapter.search_tracks(q.strip())
    except httpx.HTTPError as e:
        raise _service_error(e, "Arama başarısız") from e
    if not found:
        return {"items": []}
    db.execute(insert(Track).values([{"isrc": f.isrc} for f in found]).on_conflict_do_nothing())
    ids = dict(
        db.execute(select(Track.isrc, Track.id).where(Track.isrc.in_([f.isrc for f in found])))
        .all()
    )
    now = datetime.now(UTC)
    items = []
    for f in found:
        tid = ids[f.isrc]
        _put_meta(db, user.id, tid, f.title, f.artist_names, f.image_url, now)
        items.append(
            {"track": tid, "title": f.title, "artists": list(f.artist_names), "image": f.image_url}
        )
    db.commit()
    return {"items": items}


# ---- Sonra dinle -------------------------------------------------------------------------------


class LaterIn(BaseModel):
    track: int


def _track_or_404(db: Session, track_id: int) -> None:
    if db.get(Track, track_id) is None:
        raise HTTPException(404, "Parça yok")


@later_router.post("", status_code=201)
def add_later(
    body: LaterIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    _track_or_404(db, body.track)
    db.execute(
        insert(ListenLater).values(user_id=user.id, track_id=body.track).on_conflict_do_nothing()
    )
    db.commit()
    return {"track": body.track}


@later_router.delete("/{track_id}", status_code=204)
def remove_later(
    track_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    row = db.get(ListenLater, (user.id, track_id))
    if row is not None:
        db.delete(row)
        db.commit()


@later_router.get("")
def list_later(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> dict:
    ids = list(
        db.scalars(
            select(ListenLater.track_id)
            .where(ListenLater.user_id == user.id)
            .order_by(ListenLater.created_at.desc(), ListenLater.track_id)
        )
    )
    cards = track_cards(db, user, ids, http)
    return {"items": [cards[t] for t in ids]}


@later_router.post("/export/{service}", status_code=201)
def export_later(
    service: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> dict:
    """Listeyi kullanıcının servisinde özel çalma listesi olarak yazar; çözülemeyenler atlanır."""
    adapter = _service_adapter(db, user, service, http)
    rows = db.execute(
        select(ListenLater.track_id, Track.isrc)
        .join(Track, Track.id == ListenLater.track_id)
        .where(ListenLater.user_id == user.id)
        .order_by(ListenLater.created_at)
    ).all()
    ids: list[str] = []
    skipped: list[int] = []
    try:
        for track_id, isrc in rows:
            tid = adapter.find_track(isrc)
            if tid and tid not in ids:
                ids.append(tid)
            else:
                skipped.append(track_id)
        if not ids:
            return {"playlist_id": None, "added": 0, "skipped": skipped}
        name = f"Tını sonra dinle {datetime.now(UTC):%Y-%m-%d}"
        playlist_id = adapter.create_playlist(name, ids)
    except httpx.HTTPError as e:
        raise _service_error(e, "Çalma listesi yazılamadı") from e
    return {"playlist_id": playlist_id, "added": len(ids), "skipped": skipped}


# ---- Yorumlar ----------------------------------------------------------------------------------


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


def _author(user_id) -> str:
    """Yazar etiketi: e-posta asla gösterilmez; kimlikten türetilen kısa ad."""
    return f"Tını #{user_id.hex[:4]}"


def _comment_out(c: TrackComment, me) -> dict:
    return {
        "id": c.id, "track": c.track_id, "author": _author(c.user_id), "body": c.body,
        "created_at": c.created_at.isoformat(),
        "edited_at": c.edited_at.isoformat() if c.edited_at else None,
        "mine": c.user_id == me,
    }


def _clean(body: CommentIn) -> str:
    text = body.body.strip()
    if not text:
        raise HTTPException(422, "Yorum boş olamaz")
    return text


@comments_router.get("/tracks/{track_id}/comments")
def list_comments(
    track_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> dict:
    _track_or_404(db, track_id)
    rows = db.scalars(
        select(TrackComment)
        .where(TrackComment.track_id == track_id)
        .order_by(TrackComment.created_at.desc(), TrackComment.id.desc())
        .limit(200)
    ).all()
    card = track_cards(db, user, [track_id], http)[track_id]
    return {"track": card, "items": [_comment_out(c, user.id) for c in rows]}


@comments_router.post("/tracks/{track_id}/comments", status_code=201)
def add_comment(
    track_id: int,
    body: CommentIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    _track_or_404(db, track_id)
    c = TrackComment(user_id=user.id, track_id=track_id, body=_clean(body))
    db.add(c)
    db.commit()
    db.refresh(c)
    return _comment_out(c, user.id)


def _own_comment(db: Session, user: User, comment_id: int) -> TrackComment:
    c = db.get(TrackComment, comment_id)
    if c is None:
        raise HTTPException(404, "Yorum yok")
    if c.user_id != user.id:
        raise HTTPException(403, "Yalnızca kendi yorumunu değiştirebilirsin")
    return c


@comments_router.patch("/comments/{comment_id}")
def edit_comment(
    comment_id: int,
    body: CommentIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    c = _own_comment(db, user, comment_id)
    c.body = _clean(body)
    c.edited_at = datetime.now(UTC)
    db.commit()
    db.refresh(c)
    return _comment_out(c, user.id)


@comments_router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    db.delete(_own_comment(db, user, comment_id))
    db.commit()
