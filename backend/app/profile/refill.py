"""Hızlı yol doldurucusu (PR-2): tampon eşiği kontrolü, tek uçuş ve arka plan işi.

`queue()` ve `cast_vote` yalnızca `maybe_refill` çağırır (ucuz sorgular); ağır iş
(`refill_buffer`: meta tazeleme, profil/liste yenileme, servis çağrıları) PR-1 yürütücüsünde
çalışır. Tek uçuş: kullanıcı başına Postgres advisory kilidi. Kilit ayrı (autocommit) bir
bağlantıda tutulur; çünkü doldurucu işin ortasında commit eder ve işlem kapsamlı kilit
(`pg_try_advisory_xact_lock`) bu commit'te düşerdi. Neon doğrudan bağlantı olduğundan oturum
kilidi güvenlidir.
"""
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import exists, func, select, text
from sqlalchemy.orm import Session

from app.config import (
    ProfileSettings,
    get_graph_settings,
    get_profile_settings,
    get_recommend_settings,
    get_settings,
)
from app.db import get_engine, get_session_factory
from app.jobs.worker import get_worker
from app.models import User, UserTrackMeta, VoteEvent
from app.profile.suggest import (
    _latest_profile,
    connected_adapter,
    ready_count,
    refill_buffer,
)

log = logging.getLogger("tini.refill")

_backoff_until: dict[uuid.UUID, float] = {}  # servis hatasından sonra kullanıcı başına bekleme


def lock_key(user_id: uuid.UUID) -> int:
    """Kullanıcı kimliğinden türetilen 63 bitlik (işaretli bigint'e sığan) kilit anahtarı."""
    return user_id.int % (1 << 63)


def try_lock(conn, key: int) -> bool:
    return bool(conn.execute(text("select pg_try_advisory_lock(:k)"), {"k": key}).scalar())


def unlock(conn, key: int) -> None:
    conn.execute(text("select pg_advisory_unlock(:k)"), {"k": key})


def refill_needed(
    db: Session, user: User, now: datetime, cfg: ProfileSettings, ready_total: int | None = None
) -> bool:
    """Doldurucu gerekir mi: hazır sayısı alt eşikte, süresi dolmak üzere meta var ya da
    profil yenileme eşiğini geçecek kadar yeni oy var."""
    if _latest_profile(db, user.id) is not None:
        if ready_total is None:
            ready_total = ready_count(db, user.id, now)
        if ready_total < cfg.buffer_low_watermark:
            return True
        profile = _latest_profile(db, user.id)
        new_votes = db.scalar(
            select(func.count()).select_from(VoteEvent).where(
                VoteEvent.user_id == user.id, VoteEvent.created_at > profile.created_at
            )
        )
        if new_votes >= cfg.queue_rebuild_after_votes:
            return True
    ttl = timedelta(seconds=get_settings().spotify_cache_ttl_seconds)
    voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user.id)
    return bool(db.scalar(select(exists().where(
        UserTrackMeta.user_id == user.id,
        UserTrackMeta.expires_at > now,
        UserTrackMeta.expires_at <= now + ttl * (1 - cfg.meta_refresh_at),
        UserTrackMeta.track_id.not_in(voted),
    ))))


def maybe_refill(
    db: Session, user: User, now: datetime, cfg: ProfileSettings, ready_total: int | None = None
) -> bool:
    """Gerekirse doldurucuyu yürütücüye verir (kullanıcı başına tek bekleyen iş)."""
    if not cfg.fast_queue_enabled or not refill_needed(db, user, now, cfg, ready_total):
        return False
    return get_worker().submit(("refill", user.id), run_refill, user.id)


def run_refill(user_id: uuid.UUID) -> None:
    """Yürütücü işi: kilidi alamazsa (başka bir doldurucu çalışıyor) sessizce çıkar."""
    if time.monotonic() < _backoff_until.get(user_id, 0.0):
        return
    cfg = get_profile_settings()
    key = lock_key(user_id)
    with get_engine().connect().execution_options(isolation_level="AUTOCOMMIT") as lock_conn:
        if not try_lock(lock_conn, key):
            log.info("refill zaten çalışıyor: %s", user_id)
            return
        try:
            with httpx.Client(timeout=15) as http, get_session_factory()() as db:
                user = db.get(User, user_id)
                if user is None:
                    return
                ok = refill_buffer(
                    db, user, lambda: connected_adapter(db, user, http), datetime.now(UTC), cfg,
                    get_recommend_settings(), get_graph_settings(),
                )
                if not ok:
                    _backoff_until[user_id] = time.monotonic() + cfg.refill_error_backoff_seconds
                    log.warning("refill servis hatasıyla kesildi: %s", user_id)
        finally:
            unlock(lock_conn, key)
