"""Süresi dolan oturumları siler (`user_session`).

Okuma tarafı (`current_user`) dolmuş oturumu zaten reddeder; bu iş satırları gerçekten kaldırır,
tablo sınırsız büyümesin. Saf çekirdek: `now` parametredir.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import SessionPurgeSettings, get_session_purge_settings
from app.db import get_session_factory
from app.models import UserSession

log = logging.getLogger("tini.session_purge")


def purge_expired_sessions(
    db: Session, now: datetime, grace_seconds: int = 3600, batch_size: int = 5000
) -> int:
    """`expires_at < now - grace` olan oturumları gruplar halinde siler; silinen sayıyı döner."""
    cutoff = now - timedelta(seconds=grace_seconds)
    total = 0
    while True:
        victims = (
            select(UserSession.token_hash).where(UserSession.expires_at < cutoff).limit(batch_size)
        )
        res = db.execute(delete(UserSession).where(UserSession.token_hash.in_(victims)))
        db.commit()
        n = res.rowcount or 0
        total += n
        if n < batch_size:
            return total


def run(cfg: SessionPurgeSettings | None = None) -> int:
    cfg = cfg or get_session_purge_settings()
    with get_session_factory()() as db:
        n = purge_expired_sessions(db, datetime.now(UTC), cfg.grace_seconds, cfg.batch_size)
    log.info("session_purge: %d süresi dolmuş oturum silindi", n)
    return n
