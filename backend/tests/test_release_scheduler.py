import asyncio

from app.releases import scheduler


def test_loop_runs_and_survives_errors(monkeypatch):
    calls = []

    def fake_run():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(scheduler, "run", fake_run)

    async def go():
        task = asyncio.create_task(scheduler._loop(0, 0.01))
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(go())
    assert len(calls) >= 2  # ilk tur hata verse de döngü sürdü


def test_lifespan_disabled(monkeypatch):
    class Cfg:
        auto_detect = False

    monkeypatch.setattr(scheduler, "get_releases_settings", lambda: Cfg())
    started = []
    monkeypatch.setattr(scheduler, "run", lambda: started.append(1))

    async def go():
        async with scheduler.lifespan(None):
            await asyncio.sleep(0.05)

    asyncio.run(go())
    assert started == []
