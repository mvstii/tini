"""Sunucu içi grafik genişletme zamanlayıcısı (Render ücretsiz katmanda ayrı cron yok).

Sunucu uykudayken tur atlanır; uyanınca gecikmeden sonra çalışır. FetchLog TTL'i yinelenen
çağrıyı önlediği için sık turlar ucuzdur.
"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from app.config import get_graph_settings
from app.graph.auto import run_round

log = logging.getLogger("tini.graph.auto")


async def _loop(delay: float, interval: float) -> None:
    await asyncio.sleep(delay)
    while True:
        try:
            await asyncio.to_thread(run_round)
        except Exception:  # tur başarısız olsa da döngü ölmemeli
            log.exception("grafik genişletme turu başarısız")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_app):
    cfg = get_graph_settings()
    task = None
    if cfg.auto_expand:
        task = asyncio.create_task(
            _loop(cfg.auto_expand_delay_seconds, cfg.auto_expand_hours * 3600)
        )
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
