"""Sunucu içi oturum temizlik zamanlayıcısı (Render ücretsiz katmanda ayrı cron yok).

Sunucu uykudayken tur atlanır; uyanınca gecikme süresinden sonra çalışır. Silme idempotenttir,
sık turlar ucuzdur.
"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from app.config import get_session_purge_settings
from app.session_purge import run

log = logging.getLogger("tini.session_purge")


async def _loop(delay: float, interval: float) -> None:
    await asyncio.sleep(delay)
    while True:
        try:
            await asyncio.to_thread(run)
        except Exception:  # tur başarısız olsa da döngü ölmemeli
            log.exception("session_purge turu başarısız")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_app):
    cfg = get_session_purge_settings()
    task = None
    if cfg.enabled:
        task = asyncio.create_task(_loop(cfg.delay_seconds, cfg.interval_hours * 3600))
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
