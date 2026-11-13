"""Profil fotoğrafı: kullanıcı başına tek küçük JPEG, Postgres'te (kişisel veri, hesapla silinir).

Sunucu görseli çözmez; boyut sınırı, JPEG sihirli baytı ve hız sınırıyla yetinir.
Fotoğraf başka yanıtlara gömülmez; istemci `GET /me/photo`'yu ETag ile sorgular.
"""
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import PhotoSettings
from app.deps import current_user, get_db
from app.models import User, UserPhoto
from app.ratelimit import SlidingWindowLimiter, get_photo_limiter, too_many

router = APIRouter(prefix="/me/photo", tags=["photo"])

JPEG_MIME = "image/jpeg"
_JPEG_MAGIC = b"\xff\xd8\xff"


def get_photo_settings() -> PhotoSettings:
    return PhotoSettings()


async def _read_body(request: Request, s: PhotoSettings = Depends(get_photo_settings)) -> bytes:
    """Gövdeyi en çok `max_bytes` kadar okur; fazlası belleğe alınmadan reddedilir."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > s.max_bytes:
        raise HTTPException(413, "Fotoğraf çok büyük")
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > s.max_bytes:
            raise HTTPException(413, "Fotoğraf çok büyük")
    return bytes(buf)


def _matches(if_none_match: str, etag: str) -> bool:
    for part in if_none_match.split(","):
        if part.strip().removeprefix("W/").strip('"') == etag:
            return True
    return False


@router.put("")
def put_photo(
    user: User = Depends(current_user),
    body: bytes = Depends(_read_body),
    db: Session = Depends(get_db),
    limiter: SlidingWindowLimiter = Depends(get_photo_limiter),
) -> dict[str, str]:
    key = str(user.id)
    wait = limiter.retry_after(key)
    if wait is not None:
        raise too_many(wait)
    if not body:
        raise HTTPException(400, "Fotoğraf boş")
    if not body.startswith(_JPEG_MAGIC):
        raise HTTPException(415, "Yalnızca JPEG kabul edilir")
    limiter.hit(key)
    etag = hashlib.sha1(body).hexdigest()
    row = db.get(UserPhoto, user.id)
    if row is None:
        db.add(UserPhoto(user_id=user.id, content=body, mime=JPEG_MIME, etag=etag))
    else:
        row.content = body
        row.mime = JPEG_MIME
        row.etag = etag
    db.commit()
    return {"etag": etag}


@router.get("")
def get_photo(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    row = db.get(UserPhoto, user.id)
    if row is None:
        raise HTTPException(404, "Fotoğraf yok")
    headers = {"ETag": f'"{row.etag}"', "Cache-Control": "private, max-age=0, must-revalidate"}
    if _matches(request.headers.get("if-none-match", ""), row.etag):
        return Response(status_code=304, headers=headers)
    return Response(content=row.content, media_type=row.mime, headers=headers)


@router.delete("", status_code=204)
def delete_photo(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    row = db.get(UserPhoto, user.id)
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)
