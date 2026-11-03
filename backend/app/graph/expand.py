"""Tembel genişleme: çapa sanatçılardan komşuları Last.fm'den çeker, kenar deposuna yazar.

Planlama saftır (graph.expansion); burası veritabanı ve Last.fm ile konuşan kısımdır.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import GraphSettings
from app.graph.expansion import plan_expansion
from app.graph.store import create_snapshot, enforce_size_cap, store_edges
from app.models import (
    Artist,
    ArtistEdge,
    FetchLog,
    ListItem,
    Track,
    UserTrackArtist,
    VoteEvent,
)
from app.sources.http import SourceError
from app.sources.lastfm import LastfmClient

log = logging.getLogger("tini.expand")

SOURCE = "lastfm_similar"  # fetch_log kaynağı; kademe B'nin "lastfm" anahtarlarından ayrı


def _key(artist_id: int) -> str:
    return f"artist:{artist_id}"


def _log(db: Session, artist_id: int, status: str, ttl: int, now: datetime) -> None:
    stmt = insert(FetchLog).values(
        source=SOURCE, key=_key(artist_id), status=status, fetched_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["source", "key"],
            set_={c: getattr(stmt.excluded, c) for c in ("status", "fetched_at", "expires_at")},
        )
    )


def load_anchors(db: Session) -> list[int]:
    """Kütüphane (kademe A + B), oylanan ve öneri listesindeki sanatçılar, tekrarsız."""
    a = select(Track.artist_id).where(Track.artist_id.is_not(None))
    b = select(UserTrackArtist.artist_id)
    c = (
        select(Track.artist_id)
        .join(VoteEvent, VoteEvent.track_id == Track.id)
        .where(Track.artist_id.is_not(None))
    )
    d = select(ListItem.artist_id)
    found: set[int] = set()
    for q in (a, b, c, d):
        found |= set(db.scalars(q).all())
    return sorted(found)


def load_cache_state(
    db: Session, cfg: GraphSettings, now: datetime
) -> tuple[set[int], dict[int, list[int]]]:
    prefix = "artist:"
    keys = db.scalars(
        select(FetchLog.key).where(FetchLog.source == SOURCE, FetchLog.expires_at > now)
    ).all()
    fresh = {int(k[len(prefix):]) for k in keys}
    edges: dict[int, list[int]] = {}
    rows = db.execute(
        select(ArtistEdge.src, ArtistEdge.dst).where(
            ArtistEdge.source == cfg.edge_source, ArtistEdge.expires_at > now
        )
    ).all()
    for src, dst in rows:
        edges.setdefault(src, []).append(dst)
    return fresh, edges


def fetch_one(
    db: Session, artist: Artist, lfm: LastfmClient, cfg: GraphSettings, now: datetime,
    ok_ttl: int, empty_ttl: int, error_ttl: int,
) -> str:
    """Sonuç: 'ok' | 'empty' | 'error'. Çağıran commit eder."""
    if artist.mbid is None and not artist.name:
        _log(db, artist.id, "empty", empty_ttl, now)
        return "empty"
    try:
        similar = lfm.get_similar(
            name=None if artist.mbid else artist.name, mbid=artist.mbid,
            limit=cfg.edge_max_neighbors,
        )
    except SourceError:
        _log(db, artist.id, "error", error_ttl, now)
        return "error"
    if not similar:
        store_edges(db, artist.id, [], cfg, now, ok_ttl)  # eski kenarları temizler
        _log(db, artist.id, "empty", empty_ttl, now)
        return "empty"
    store_edges(db, artist.id, similar, cfg, now, ok_ttl)
    _log(db, artist.id, "ok", ok_ttl, now)
    return "ok"


def expand(
    db: Session, lfm: LastfmClient, cfg: GraphSettings, limit: int = 100,
    depth: int | None = None, anchors: list[int] | None = None, now: datetime | None = None,
) -> dict:
    """Plan → çek → yeniden planla; `limit` kadar çekimde veya plan boşalınca durur.

    Önbellek isabeti ilk planda ölçülür: geçerli bulunan düğüm / ziyaret edilen düğüm.
    """
    now = now or datetime.now(UTC)
    depth = cfg.expand_depth if depth is None else depth
    anchors = load_anchors(db) if anchors is None else anchors
    counts = {"ok": 0, "empty": 0, "error": 0}
    hit_ratio: float | None = None
    fetched = 0
    ttls = (cfg.fetch_ok_ttl_seconds, cfg.fetch_empty_ttl_seconds, cfg.fetch_error_ttl_seconds)
    while fetched < limit:
        fresh, edges = load_cache_state(db, cfg, now)
        plan = plan_expansion(anchors, depth, fresh, edges)
        if hit_ratio is None:
            hit_ratio = plan.cached / plan.visited if plan.visited else 1.0
        if not plan.to_fetch:
            break
        for artist_id in plan.to_fetch[: limit - fetched]:
            artist = db.get(Artist, artist_id)
            counts[fetch_one(db, artist, lfm, cfg, now, *ttls)] += 1
            db.commit()
            fetched += 1
    size = enforce_size_cap(db, cfg)
    snapshot = None
    if counts["ok"]:
        snapshot = create_snapshot(
            db,
            {
                "depth": depth, "max_neighbors": cfg.edge_max_neighbors,
                "source": cfg.edge_source, "anchors": len(anchors), "fetched": fetched,
            },
        ).version
    db.commit()
    result = {
        **counts, "fetched": fetched, "anchors": len(anchors),
        "cache_hit_ratio": hit_ratio if hit_ratio is not None else 1.0,
        "size_bytes": size["size_bytes"], "dropped": size["dropped"], "snapshot": snapshot,
    }
    log.info("expand: %s", result)
    return result
