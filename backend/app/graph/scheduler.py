"""Sunucu içi grafik genişletme zamanlayıcısı (Render ücretsiz katmanda ayrı cron yok).

Sunucu uykudayken tur atlanır; uyanınca gecikmeden sonra çalışır. FetchLog TTL'i yinelenen
çağrıyı önlediği için sık turlar ucuzdur.
"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from app.config import get_graph_settings
from app.graph.auto import run_round
from app.jobs.worker import get_worker, idle_seconds

log = logging.getLogger("tini.graph.auto")


async def _wait_idle(idle: float, max_wait: float) -> None:
    waited = 0.0
    while idle_seconds() < idle and waited < max_wait:
        await asyncio.sleep(2)
        waited += 2


async def _loop(delay: float, interval: float) -> None:
    cfg = get_graph_settings()
    await asyncio.sleep(delay)
    while True:
        try:
            await _wait_idle(cfg.auto_expand_idle_seconds, cfg.auto_expand_idle_max_wait)
            get_worker().submit("graph_round", run_round)
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
