"""Kademe B/C: MusicBrainz'de bulunamayan parça için Last.fm ile ad tabanlı eşleme.

Kullanıcıya özel önbellekteki sanatçı adı Last.fm'e yalnızca geçici sorgu anahtarı olarak gider.
Paylaşılan tablolara yalnızca Last.fm'in kanonik adı ve kimliği yazılır; "bu şarkı bu
sanatçıdır" bağı kullanıcıya özel user_track_artist'te kalır (track.artist_id'ye dokunulmaz).
Güven eşiğin altındaysa veya bulunamazsa kademe C: bağ yok, negatif kayıt TTL ile tutulur.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import String, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from app.catalog.confidence import name_match_confidence
from app.catalog.names import normalize_name
from app.catalog.resolve import SOURCE as MB_SOURCE
from app.catalog.resolve import upsert_artist
from app.config import GraphSettings
from app.models import (
    Artist,
    ArtistRef,
    FetchLog,
    Track,
    UserTrackArtist,
    UserTrackMeta,
)
from app.sources.http import SourceError
from app.sources.lastfm import LastfmClient

SOURCE = "lastfm"
METHOD_B = "name_lastfm"


def _log(db: Session, track_id: int, status: str, ttl: int, now: datetime) -> None:
    stmt = insert(FetchLog).values(
        source=SOURCE, key=f"track:{track_id}", status=status, fetched_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["source", "key"],
            set_={c: getattr(stmt.excluded, c) for c in ("status", "fetched_at", "expires_at")},
        )
    )


def _lastfm_artist_id(
    db: Session, mbid: uuid.UUID | None, name: str, name_norm: str
) -> tuple[int, str]:
    """Last.fm'in döndürdüğü sanatçı için paylaşılan satırı bulur/açar; (artist_id, provider_id)."""
    if mbid is not None:
        return upsert_artist(db, mbid, name), str(mbid)
    pid = f"name:{name_norm}"
    ref = db.scalar(
        select(ArtistRef.artist_id).where(
            ArtistRef.provider == SOURCE, ArtistRef.provider_id == pid
        )
    )
    if ref is not None:
        return ref, pid
    aid = db.execute(
        insert(Artist).values(mbid=None, name=name, name_norm=name_norm).returning(Artist.id)
    ).scalar_one()
    return aid, pid


def resolve_track_b(
    db: Session, user_id: uuid.UUID, track_id: int, query_name: str, lfm: LastfmClient,
    cfg: GraphSettings, now: datetime | None = None,
) -> str:
    """Sonuç: 'linked' | 'empty' (kademe C) | 'error'. Çağıran commit eder."""
    now = now or datetime.now(UTC)
    try:
        info = lfm.get_info(name=query_name)
    except SourceError:
        _log(db, track_id, "error", cfg.fetch_error_ttl_seconds, now)
        return "error"
    if info is None:
        _log(db, track_id, "empty", cfg.fetch_empty_ttl_seconds, now)
        return "empty"
    canon_norm = normalize_name(info.name)
    conf = name_match_confidence(
        normalize_name(query_name), canon_norm, info.mbid is not None, cfg
    )
    if conf < cfg.tier_b_min_confidence:
        _log(db, track_id, "empty", cfg.fetch_empty_ttl_seconds, now)
        return "empty"
    artist_id, pid = _lastfm_artist_id(db, info.mbid, info.name, canon_norm)
    db.execute(
        insert(ArtistRef)
        .values(
            artist_id=artist_id, provider=SOURCE, provider_id=pid,
            match_method=METHOD_B, confidence=conf,
        )
        .on_conflict_do_nothing(index_elements=["provider", "provider_id"])
    )
    stmt = insert(UserTrackArtist).values(
        user_id=user_id, track_id=track_id, artist_id=artist_id, confidence=conf, method=METHOD_B
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "track_id"],
            set_={c: getattr(stmt.excluded, c) for c in ("artist_id", "confidence", "method")},
        )
    )
    return "linked"


def resolve_pending_b(
    db: Session, lfm: LastfmClient, cfg: GraphSettings, limit: int = 100,
    now: datetime | None = None,
) -> dict[str, int]:
    """Kademe A'da 'empty' dönen, sanatçısı olmayan ve geçerli önbellek adı bulunan parçalar."""
    now = now or datetime.now(UTC)
    mb = aliased(FetchLog)
    lf = aliased(FetchLog)
    rows = db.execute(
        select(UserTrackMeta.user_id, UserTrackMeta.track_id, UserTrackMeta.artist_names)
        .join(Track, Track.id == UserTrackMeta.track_id)
        .join(
            mb,
            (mb.source == MB_SOURCE) & (mb.key == ("isrc:" + Track.isrc)) & (mb.status == "empty"),
        )
        .outerjoin(
            lf,
            (lf.source == SOURCE)
            & (lf.key == ("track:" + Track.id.cast(String)))
            & (lf.expires_at > now),
        )
        .outerjoin(
            UserTrackArtist,
            (UserTrackArtist.user_id == UserTrackMeta.user_id)
            & (UserTrackArtist.track_id == UserTrackMeta.track_id),
        )
        .where(
            Track.artist_id.is_(None), UserTrackMeta.expires_at > now,
            lf.key.is_(None), UserTrackArtist.track_id.is_(None),
        )
        .order_by(UserTrackMeta.track_id, UserTrackMeta.user_id)
        .limit(limit)
    ).all()
    counts = {"linked": 0, "empty": 0, "error": 0}
    for user_id, track_id, names in rows:
        if not names or not names[0].strip():
            continue
        counts[resolve_track_b(db, user_id, track_id, names[0], lfm, cfg, now)] += 1
        db.commit()
    return counts
