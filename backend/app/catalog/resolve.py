"""Kademe A: ISRC → MusicBrainz kaydı → sanatçı MBID. Spotify metni kullanılmaz.

Paylaşılan tablolara yalnızca MusicBrainz'in kanonik adı ve kimliği yazılır.
Aynı normalize ad + çelişen MBID birleştirilmez; MBID başına ayrı satır açılır.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.catalog.names import normalize_name
from app.config import GraphSettings
from app.models import Artist, ArtistRef, FetchLog, Track
from app.sources.http import SourceError
from app.sources.musicbrainz import MusicBrainzClient

SOURCE = "musicbrainz"
METHOD_A = "isrc_mb"


def upsert_artist(db: Session, mbid: uuid.UUID, name: str) -> int:
    existing = db.scalar(select(Artist.id).where(Artist.mbid == mbid))
    if existing is not None:
        return existing
    return db.execute(
        insert(Artist)
        .values(mbid=mbid, name=name, name_norm=normalize_name(name))
        .returning(Artist.id)
    ).scalar_one()


def _log(db: Session, key: str, status: str, ttl: int, now: datetime) -> None:
    stmt = insert(FetchLog).values(
        source=SOURCE, key=key, status=status, fetched_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["source", "key"],
            set_={c: getattr(stmt.excluded, c) for c in ("status", "fetched_at", "expires_at")},
        )
    )


def resolve_track(
    db: Session, track: Track, mb: MusicBrainzClient, cfg: GraphSettings,
    now: datetime | None = None,
) -> str:
    """Tek parçayı çözer; sonuç: 'ok' | 'empty' | 'error' | 'cached'. Çağıran commit eder."""
    now = now or datetime.now(UTC)
    key = f"isrc:{track.isrc}"
    log = db.get(FetchLog, (SOURCE, key))
    if log is not None and log.expires_at > now:
        return "cached"
    try:
        rec = mb.lookup_isrc(track.isrc)
    except SourceError:
        _log(db, key, "error", cfg.fetch_error_ttl_seconds, now)
        return "error"
    if rec is None:
        _log(db, key, "empty", cfg.fetch_empty_ttl_seconds, now)
        return "empty"
    credit = rec.artists[0]  # kayıttaki ilk kredi birincil sanatçıdır
    artist_id = upsert_artist(db, credit.mbid, credit.name)
    db.execute(
        insert(ArtistRef)
        .values(
            artist_id=artist_id, provider=SOURCE, provider_id=str(credit.mbid),
            match_method=METHOD_A, confidence=cfg.tier_a_confidence,
        )
        .on_conflict_do_nothing(index_elements=["provider", "provider_id"])
    )
    track.artist_id = artist_id
    track.mbid = rec.mbid
    _log(db, key, "ok", cfg.fetch_ok_ttl_seconds, now)
    return "ok"


def resolve_pending(
    db: Session, mb: MusicBrainzClient, cfg: GraphSettings, limit: int = 100,
    now: datetime | None = None,
) -> dict[str, int]:
    """Sanatçısı çözülmemiş parçaları sırayla işler; her parçadan sonra commit eder."""
    now = now or datetime.now(UTC)
    tracks = db.scalars(
        select(Track)
        .outerjoin(
            FetchLog,
            (FetchLog.source == SOURCE)
            & (FetchLog.key == ("isrc:" + Track.isrc))
            & (FetchLog.expires_at > now),
        )
        .where(Track.artist_id.is_(None), FetchLog.key.is_(None))
        .order_by(Track.id)
        .limit(limit)
    ).all()
    counts = {"ok": 0, "empty": 0, "error": 0, "cached": 0}
    for t in tracks:
        counts[resolve_track(db, t, mb, cfg, now)] += 1
        db.commit()
    return counts
