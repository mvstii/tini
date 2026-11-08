"""Kütüphane içe aktarma: adaptörün okuduğu parçaları veritabanına yazar.

Paylaşılan katalogya yalnızca ISRC girer; başlık/sanatçı/süre kullanıcıya özel
TTL'li önbelleğe (user_track_meta) yazılır (bkz. CLAUDE.md).
"""
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.adapters.base import Library
from app.adapters.spotify.client import SpotifyAdapter
from app.config import get_settings
from app.connect import get_http
from app.connections import valid_access_value
from app.deps import current_user, get_db
from app.jobs.enrich import run_background
from app.models import ServiceConnection, Track, User, UserTrackLink, UserTrackMeta
from app.upstream import upstream_unavailable

router = APIRouter()

ADAPTERS = {"spotify": SpotifyAdapter}


def store_library(
    db: Session, user_id: uuid.UUID, service: str, lib: Library, ttl: timedelta
) -> int:
    """Parçaları yazar (tekrar çalıştırılabilir); yazılan parça sayısını döndürür."""
    if not lib.tracks:
        return 0
    now = datetime.now(UTC)
    isrcs = [t.isrc for t in lib.tracks]
    db.execute(
        insert(Track).values([{"isrc": i} for i in set(isrcs)]).on_conflict_do_nothing()
    )
    ids = dict(db.execute(select(Track.isrc, Track.id).where(Track.isrc.in_(isrcs))).all())

    # Aynı ISRC'ye bağlı birden çok servis kimliği olabilir; meta parça başına tek satırdır.
    links = {
        (t.external_id): {
            "user_id": user_id, "service": service,
            "external_id": t.external_id, "track_id": ids[t.isrc],
        }
        for t in lib.tracks
    }
    stmt = insert(UserTrackLink).values(list(links.values()))
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "service", "external_id"],
            set_={"track_id": stmt.excluded.track_id},
        )
    )
    metas = {
        ids[t.isrc]: {
            "user_id": user_id, "track_id": ids[t.isrc], "title": t.title,
            "artist_names": list(t.artist_names), "duration_ms": t.duration_ms,
            "image_url": t.image_url, "fetched_at": now, "expires_at": now + ttl,
        }
        for t in lib.tracks
    }
    stmt = insert(UserTrackMeta).values(list(metas.values()))
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "track_id"],
            set_={
                c: getattr(stmt.excluded, c)
                for c in (
                    "title", "artist_names", "duration_ms", "image_url", "fetched_at", "expires_at"
                )
            },
        )
    )
    db.commit()
    return len(metas)


@router.post("/library/import")
def import_library(
    background: BackgroundTasks,
    service: str = "spotify",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> dict[str, int]:
    adapter_cls = ADAPTERS.get(service)
    if adapter_cls is None:
        raise HTTPException(400, "Bilinmeyen servis")
    conn = db.scalars(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id, ServiceConnection.service == service
        )
    ).first()
    if conn is None:
        raise HTTPException(409, "Servis bağlı değil")
    try:
        value = valid_access_value(db, conn, http)
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    try:
        lib = adapter_cls(http, value).read_library()
    except httpx.HTTPError as e:
        raise upstream_unavailable(e, "Kütüphane içe aktarılamadı") from e
    ttl = timedelta(seconds=get_settings().spotify_cache_ttl_seconds)
    stored = store_library(db, user.id, service, lib, ttl)
    if get_settings().musicbrainz_contact:
        background.add_task(run_background)
    return {"imported": stored, "skipped": lib.skipped}
