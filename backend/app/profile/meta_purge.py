"""Süresi dolan servis metadata'sını siler (`user_track_meta`).

Spotify verisi kalıcı saklanmaz (CLAUDE.md, Developer Terms v10): başlık, sanatçı, süre ve kapak
URL'si yalnızca kullanıcıya özel, TTL'li önbellekte durur. Okuma tarafı `expires_at > now` ile
süzer; bu iş dolmuş satırları gerçekten kaldırır. Saf çekirdek: `now` parametredir.

CLI: python -m app.jobs.purge_meta  (ya da sunucu içi zamanlayıcı, bkz. meta_purge_scheduler)
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.config import MetaPurgeSettings, get_meta_purge_settings
from app.db import get_session_factory
from app.models import UserTrackMeta

log = logging.getLogger("tini.meta_purge")


def purge_expired_meta(
    db: Session, now: datetime, grace_seconds: int = 3600, batch_size: int = 5000
) -> int:
    """`expires_at < now - grace` olan satırları gruplar halinde siler; silinen sayıyı döner.

    Her grup ayrı işlemde commit edilir: uzun kilit ve büyük işlem oluşmaz."""
    cutoff = now - timedelta(seconds=grace_seconds)
    total = 0
    while True:
        victims = (
            select(UserTrackMeta.user_id, UserTrackMeta.track_id)
            .where(UserTrackMeta.expires_at < cutoff)
            .limit(batch_size)
        )
        res = db.execute(
            delete(UserTrackMeta).where(
                tuple_(UserTrackMeta.user_id, UserTrackMeta.track_id).in_(victims)
            )
        )
        db.commit()
        n = res.rowcount or 0
        total += n
        if n < batch_size:
            return total


def run(cfg: MetaPurgeSettings | None = None) -> int:
    cfg = cfg or get_meta_purge_settings()
    with get_session_factory()() as db:
        n = purge_expired_meta(db, datetime.now(UTC), cfg.grace_seconds, cfg.batch_size)
    log.info("meta_purge: %d süresi dolmuş satır silindi", n)
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
