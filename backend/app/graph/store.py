"""Kenar deposu: komşu başına üst sınırlı yazım ve boyut izleme.

Yalnızca kaynağın kanonik adı/kimliği ve ham ağırlık yazılır; ham yanıt saklanmaz.
"""
import logging
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.catalog.names import normalize_name
from app.catalog.resolve import upsert_artist
from app.config import GraphSettings
from app.models import Artist, ArtistEdge, ArtistRef, GraphSnapshot
from app.sources.lastfm import LfmSimilar

log = logging.getLogger("tini.graph")

SOURCE_REF = "lastfm"
METHOD_SIMILAR = "lastfm_similar"


def neighbor_artist_id(db: Session, mbid: uuid.UUID | None, name: str) -> int:
    """Komşu için paylaşılan satırı bulur/açar; kimlik Last.fm'in kendi kimliğidir (güven 1)."""
    if mbid is not None:
        aid, pid = upsert_artist(db, mbid, name), str(mbid)
    else:
        norm = normalize_name(name)
        pid = f"name:{norm}"
        aid = db.scalar(
            select(ArtistRef.artist_id).where(
                ArtistRef.provider == SOURCE_REF, ArtistRef.provider_id == pid
            )
        )
        if aid is None:
            aid = db.execute(
                insert(Artist).values(mbid=None, name=name, name_norm=norm).returning(Artist.id)
            ).scalar_one()
    db.execute(
        insert(ArtistRef)
        .values(
            artist_id=aid, provider=SOURCE_REF, provider_id=pid,
            match_method=METHOD_SIMILAR, confidence=1.0,
        )
        .on_conflict_do_nothing(index_elements=["provider", "provider_id"])
    )
    return aid


def store_edges(
    db: Session, src: int, similar: Sequence[LfmSimilar], cfg: GraphSettings,
    now: datetime, ttl_seconds: int,
) -> int:
    """src'nin kenarlarını değiştirir: ağırlığa göre en çok `edge_max_neighbors` komşu.

    Kendine kenar atılır; aynı komşu tekrarlanırsa en büyük ağırlık kalır. Yazılan kenar
    sayısını döndürür. Çağıran commit eder.
    """
    best: dict[int, float] = {}
    for s in sorted(similar, key=lambda x: x.match, reverse=True):
        if len(best) >= cfg.edge_max_neighbors:
            break
        dst = neighbor_artist_id(db, s.mbid, s.name)
        if dst == src:
            continue
        best.setdefault(dst, min(max(s.match, 0.0), 1.0))
    db.execute(
        delete(ArtistEdge).where(ArtistEdge.src == src, ArtistEdge.source == cfg.edge_source)
    )
    if best:
        db.execute(
            insert(ArtistEdge),
            [
                {
                    "src": src, "dst": dst, "source": cfg.edge_source, "weight": w,
                    "fetched_at": now, "expires_at": now + timedelta(seconds=ttl_seconds),
                }
                for dst, w in best.items()
            ],
        )
    return len(best)


def table_size_bytes(db: Session) -> int:
    return db.scalar(text("select pg_total_relation_size('artist_edge')")) or 0


def enforce_size_cap(db: Session, cfg: GraphSettings) -> dict[str, int]:
    """Boyut uyarı eşiğini aşarsa uyarır; üst sınırı aşarsa en eski kenarları atar.

    Silme boyutu hemen küçültmez (VACUUM gerekir); bu yüzden atılacak satır sayısı mevcut
    boyuna göre orantılanır: hedef = uyarı eşiği. Dönen sözlük: önce/sonra bayt ve atılan satır.
    """
    size = table_size_bytes(db)
    dropped = 0
    if size > cfg.edge_warn_bytes:
        log.warning("artist_edge %d bayt (uyarı eşiği %d)", size, cfg.edge_warn_bytes)
    if size > cfg.edge_max_bytes:
        rows = db.scalar(select(func.count()).select_from(ArtistEdge)) or 0
        keep = int(rows * cfg.edge_warn_bytes / size)
        oldest = (
            select(ArtistEdge.src, ArtistEdge.dst, ArtistEdge.source)
            .order_by(ArtistEdge.fetched_at, ArtistEdge.src, ArtistEdge.dst)
            .limit(max(rows - keep, 0))
        )
        dropped = db.execute(
            delete(ArtistEdge).where(
                tuple_(ArtistEdge.src, ArtistEdge.dst, ArtistEdge.source).in_(oldest)
            )
        ).rowcount
        log.warning("artist_edge üst sınırı aşıldı; %d eski kenar atıldı", dropped)
    return {"size_bytes": size, "dropped": dropped}


def create_snapshot(db: Session, params: dict) -> GraphSnapshot:
    count = db.scalar(select(func.count()).select_from(ArtistEdge)) or 0
    snap = GraphSnapshot(edge_count=count, params=params)
    db.add(snap)
    db.flush()
    return snap
