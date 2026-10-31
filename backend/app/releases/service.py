"""Yayın tespiti için veritabanı katmanı: takip kümesi ve MusicBrainz'den yayın çekme."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ReleasesSettings
from app.models import (
    Artist,
    FetchLog,
    FollowedArtist,
    Release,
    ReleaseArtist,
    TasteProfile,
)
from app.releases.follow import auto_follows, effective_follows
from app.sources.http import SourceError
from app.sources.musicbrainz import MusicBrainzClient

SOURCE = "mb_release"


def user_follows(db: Session, user_id) -> dict[int, str]:
    row = db.scalar(
        select(TasteProfile)
        .where(TasteProfile.user_id == user_id)
        .order_by(TasteProfile.version.desc())
        .limit(1)
    )
    rows = db.execute(
        select(FollowedArtist.artist_id, FollowedArtist.source).where(
            FollowedArtist.user_id == user_id
        )
    ).all()
    manual = {a for a, s in rows if s == "manual"}
    muted = {a for a, s in rows if s == "muted"}
    return effective_follows(auto_follows(row.body) if row else set(), manual, muted)


def all_followed_artists(db: Session) -> set[int]:
    """Tüm kullanıcıların etkin takip sanatçıları (paylaşılan katalog için birleşim)."""
    out: set[int] = set()
    for (uid,) in db.execute(select(TasteProfile.user_id).distinct()).all():
        out |= set(user_follows(db, uid))
    out |= set(
        db.scalars(select(FollowedArtist.artist_id).where(FollowedArtist.source == "manual"))
    )
    return out


@dataclass
class DetectResult:
    queried: int = 0
    skipped_cached: int = 0
    no_mbid: int = 0
    errors: int = 0
    new_releases: int = 0


def detect_releases(
    db: Session, mb: MusicBrainzClient, cfg: ReleasesSettings, now: datetime,
    artist_ids: set[int] | None = None,
) -> DetectResult:
    res = DetectResult()
    ids = sorted(all_followed_artists(db) if artist_ids is None else artist_ids)
    since, until = (now - timedelta(days=cfg.window_days)).date(), now.date()
    for artist_id in ids:
        artist = db.get(Artist, artist_id)
        if artist is None or artist.mbid is None:
            res.no_mbid += 1
            continue
        key = f"artist:{artist_id}"
        log = db.get(FetchLog, (SOURCE, key))
        if log is not None and log.expires_at > now:
            res.skipped_cached += 1
            continue
        try:
            groups = mb.release_groups(artist.mbid, since, until, cfg.types, cfg.search_limit)
        except SourceError:
            res.errors += 1
            continue
        res.queried += 1
        res.new_releases += _store(db, artist_id, groups)
        expires = now + timedelta(days=cfg.refetch_days)
        status = "ok" if groups else "empty"
        if log is None:
            db.add(FetchLog(source=SOURCE, key=key, status=status, expires_at=expires))
        else:
            log.status, log.expires_at = status, expires
            log.fetched_at = now
        db.commit()
    return res


def _store(db: Session, artist_id: int, groups) -> int:
    added = 0
    for g in groups:
        rel = db.scalar(select(Release).where(Release.mb_rgid == g.mbid))
        if rel is None:
            rel = Release(
                mb_rgid=g.mbid, title=g.title, primary_type=g.primary_type,
                first_release_date=g.first_release_date,
            )
            db.add(rel)
            db.flush()
            added += 1
        credited = set(db.scalars(select(Artist.id).where(Artist.mbid.in_(g.artist_mbids))))
        have = set(
            db.scalars(select(ReleaseArtist.artist_id).where(ReleaseArtist.release_id == rel.id))
        )
        for a in (credited | {artist_id}) - have:
            db.add(ReleaseArtist(release_id=rel.id, artist_id=a))
    db.flush()
    return added
