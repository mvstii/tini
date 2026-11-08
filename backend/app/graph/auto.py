"""Otomatik genişleme: periyodik tur, oy sonrası genişletme ve komşu sanatçılara parça kapsaması.

Parça kapsaması MusicBrainz'den gelir (çekirdek kaynak): sanatçının ISRC'li kayıtları paylaşılan
kataloğa `Track` olarak yazılır; başlık/süre saklanmaz (yalnızca ISRC + MBID).
"""
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import GraphSettings, get_graph_settings
from app.db import get_session_factory
from app.graph.expand import expand, fetch_one
from app.models import Artist, ArtistEdge, FetchLog, ListItem, Track
from app.sources.http import SourceError
from app.sources.musicbrainz import MusicBrainzClient

log = logging.getLogger("tini.graph.auto")

TRACKS_SOURCE = "mb_artist_tracks"


def _key(artist_id: int) -> str:
    return f"artist:{artist_id}"


def _fresh(db: Session, source: str, artist_id: int, now: datetime) -> bool:
    row = db.get(FetchLog, (source, _key(artist_id)))
    return row is not None and row.expires_at > now


def _log(db: Session, source: str, artist_id: int, status: str, ttl: int, now: datetime) -> None:
    stmt = insert(FetchLog).values(
        source=source, key=_key(artist_id), status=status, fetched_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["source", "key"],
            set_={c: getattr(stmt.excluded, c) for c in ("status", "fetched_at", "expires_at")},
        )
    )


def fill_tracks(
    db: Session, mb: MusicBrainzClient, artist_ids: list[int], cfg: GraphSettings,
    now: datetime,
) -> dict[str, int]:
    """Parçası olmayan, MBID'li sanatçılar için ISRC'li kayıtları kataloğa ekler."""
    counts = {"ok": 0, "empty": 0, "error": 0, "tracks": 0}
    for artist_id in artist_ids:
        artist = db.get(Artist, artist_id)
        if artist is None or artist.mbid is None or _fresh(db, TRACKS_SOURCE, artist_id, now):
            continue
        has_track = db.scalar(select(Track.id).where(Track.artist_id == artist_id).limit(1))
        if has_track is not None:
            continue
        try:
            found = mb.artist_isrcs(artist.mbid, cfg.tracks_browse_limit)
        except SourceError:
            _log(db, TRACKS_SOURCE, artist_id, "error", cfg.fetch_error_ttl_seconds, now)
            db.commit()
            counts["error"] += 1
            continue
        added = 0
        for isrc, rec_mbid in found[: cfg.tracks_per_artist]:
            new_id = db.scalar(
                insert(Track)
                .values(isrc=isrc, mbid=rec_mbid, artist_id=artist_id)
                .on_conflict_do_nothing(index_elements=["isrc"])
                .returning(Track.id)
            )
            added += new_id is not None
        status = "ok" if added else "empty"
        ttl = cfg.fetch_ok_ttl_seconds if added else cfg.fetch_empty_ttl_seconds
        _log(db, TRACKS_SOURCE, artist_id, status, ttl, now)
        db.commit()
        counts[status] += 1
        counts["tracks"] += added
    return counts


def artists_needing_tracks(
    db: Session, cfg: GraphSettings, now: datetime, limit: int
) -> list[int]:
    """Öneri listesinde parçasız kalan sanatçılar önce, ardından en güçlü komşular."""
    listed = list(dict.fromkeys(db.scalars(
        select(ListItem.artist_id)
        .where(ListItem.track_id.is_(None))
        .order_by(ListItem.list_id.desc(), ListItem.position)
        .limit(limit * 4)
    )))
    neighbors = list(dict.fromkeys(db.scalars(
        select(ArtistEdge.dst)
        .where(ArtistEdge.source == cfg.edge_source, ArtistEdge.expires_at > now)
        .order_by(ArtistEdge.weight.desc())
        .limit(limit * 8)
    )))
    out: list[int] = []
    for aid in dict.fromkeys(listed + neighbors):
        if len(out) >= limit:
            break
        artist = db.get(Artist, aid)
        if artist is None or artist.mbid is None or _fresh(db, TRACKS_SOURCE, aid, now):
            continue
        if db.scalar(select(Track.id).where(Track.artist_id == aid).limit(1)) is None:
            out.append(aid)
    return out


def run_round(cfg: GraphSettings | None = None) -> dict:
    """Bir tur: Last.fm genişlemesi (anahtar varsa), sonra MusicBrainz parça kapsaması."""
    from app.jobs.enrich import _quiet_http_logs, make_lastfm, make_musicbrainz

    _quiet_http_logs()
    cfg = cfg or get_graph_settings()
    now = datetime.now(UTC)
    result: dict = {}
    with httpx.Client(timeout=20) as client, get_session_factory()() as db:
        lfm = make_lastfm(client)
        if lfm is not None:
            result["expand"] = expand(db, lfm, cfg, limit=cfg.auto_expand_limit)
        ids = artists_needing_tracks(db, cfg, now, cfg.auto_tracks_limit)
        if ids:
            result["tracks"] = fill_tracks(db, make_musicbrainz(client), ids, cfg, now)
    log.info("graph auto: %s", result)
    return result


def after_vote(track_id: int) -> None:
    """Oy sonrası (arka plan): oylanan sanatçının komşularını çek, güçlü komşulara parça bul.

    Hata isteği etkilemez; yalnızca loglanır."""
    from app.jobs.enrich import _quiet_http_logs, make_lastfm, make_musicbrainz

    try:
        _quiet_http_logs()
        cfg = get_graph_settings()
        now = datetime.now(UTC)
        with httpx.Client(timeout=20) as client, get_session_factory()() as db:
            artist_id = db.scalar(select(Track.artist_id).where(Track.id == track_id))
            if artist_id is None:
                return
            lfm = make_lastfm(client)
            if lfm is not None and not _fresh(db, "lastfm_similar", artist_id, now):
                artist = db.get(Artist, artist_id)
                fetch_one(
                    db, artist, lfm, cfg, now, cfg.fetch_ok_ttl_seconds,
                    cfg.fetch_empty_ttl_seconds, cfg.fetch_error_ttl_seconds,
                )
                db.commit()
            near = list(db.scalars(
                select(ArtistEdge.dst)
                .where(ArtistEdge.src == artist_id, ArtistEdge.source == cfg.edge_source)
                .order_by(ArtistEdge.weight.desc())
                .limit(cfg.vote_neighbor_tracks * 3)
            ))
            todo = [
                a for a in near
                if db.scalar(select(Track.id).where(Track.artist_id == a).limit(1)) is None
            ][: cfg.vote_neighbor_tracks]
            if todo:
                fill_tracks(db, make_musicbrainz(client), todo, cfg, now)
    except Exception:  # noqa: BLE001
        log.exception("oy sonrası genişletme başarısız")
