import threading

from app.jobs.worker import Worker


def test_runs_jobs_in_order_on_single_thread():
    w, out, names = Worker(10), [], set()

    def job(n):
        out.append(n)
        names.add(threading.current_thread().name)

    for n in range(3):
        w.submit(n, job, n)
    assert w.wait_idle()
    assert out == [0, 1, 2] and names == {"tini-worker"}


def test_same_key_is_coalesced():
    w, gate, out = Worker(10), threading.Event(), []
    started = threading.Event()
    w.submit("blocker", lambda: (started.set(), gate.wait()))
    assert started.wait(2)
    for _ in range(5):
        w.submit("a", out.append, 1)
    gate.set()
    assert w.wait_idle()
    assert out == [1] and w.coalesced >= 4


def test_queue_limit_drops_and_error_does_not_kill():
    w, gate, out = Worker(2), threading.Event(), []
    started = threading.Event()
    w.submit("blocker", lambda: (started.set(), gate.wait()))
    assert started.wait(2)
    w.submit("bad", lambda: 1 / 0)
    w.submit("x", out.append, 1)
    w.submit("y", out.append, 2)
    w.submit("z", out.append, 3)
    assert w.dropped >= 1
    gate.set()
    assert w.wait_idle()
    assert 1 in out


def test_matrix_swr_serves_stale_and_refreshes(monkeypatch):
    from app.config import GraphSettings
    from app.graph import service

    old = object()
    monkeypatch.setattr(service, "_cached", (1, old))
    calls = []
    monkeypatch.setattr(service, "_refresh", lambda v, c: calls.append(v))

    class FakeDB:
        def scalar(self, *_):
            return 2

    cfg = GraphSettings(swr_enabled=True)
    assert service.get_matrix(FakeDB(), cfg) == (1, old)
    from app.jobs.worker import get_worker

    assert get_worker().wait_idle()
    assert calls == [2]


def test_scheduler_waits_for_idle():
    import asyncio

    from app.graph import scheduler
    from app.jobs import worker

    worker.touch()
    t0 = worker.idle_seconds()
    assert t0 < 1
    asyncio.run(scheduler._wait_idle(0.0, 5))  # idle=0: beklemeden döner
    asyncio.run(scheduler._wait_idle(100, 0))  # max_wait=0: sessizlik gelmese de döner
