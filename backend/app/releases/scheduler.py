"""Sunucu içi yayın tespiti zamanlayıcısı (Render ücretsiz katmanda ayrı cron yok).

Sunucu uykuya geçerse tur atlanır; uyanınca gecikme süresinden sonra yeniden çalışır.
Aynı sanatçı `refetch_days` içinde tekrar sorgulanmadığından sık turlar ucuzdur.
"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from app.config import get_releases_settings
from app.jobs.detect_releases import run

log = logging.getLogger("tini.releases")


async def _loop(delay: float, interval: float) -> None:
    await asyncio.sleep(delay)
    while True:
        try:
            await asyncio.to_thread(run)
        except Exception:  # tur başarısız olsa da döngü ölmemeli
            log.exception("detect_releases turu başarısız")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_app):
    cfg = get_releases_settings()
    task = None
    if cfg.auto_detect:
        task = asyncio.create_task(
            _loop(cfg.auto_detect_delay_seconds, cfg.auto_detect_hours * 3600)
        )
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
