"""Ağır arka plan işleri için tek iş parçacıklı yürütücü.

İstek iş parçacıklarını ve Neon bağlantılarını şişirmemek için ağır işler (oy sonrası
grafik genişletme, tur) burada sırayla çalışır. Aynı anahtarla bekleyen iş birleştirilir
(debounce); kuyruk dolunca yeni iş düşürülür (iş kritik değil, sonraki oy yeniden dener).
"""
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable

log = logging.getLogger("tini.worker")


class Worker:
    def __init__(self, max_queue: int) -> None:
        self._max = max_queue
        self._pending: OrderedDict[object, tuple[Callable, tuple]] = OrderedDict()
        self._cv = threading.Condition()
        self._thread: threading.Thread | None = None
        self._running = False
        self.dropped = 0
        self.coalesced = 0
        self.done = 0
        self._busy = False

    def submit(self, key: object, fn: Callable, *args) -> bool:
        """İşi kuyruğa alır. Aynı anahtar bekliyorsa birleştirir; kuyruk doluysa düşürür."""
        with self._cv:
            if key in self._pending:
                self.coalesced += 1
                return False
            if len(self._pending) >= self._max:
                self.dropped += 1
                log.warning("worker kuyruğu dolu (%d), iş düşürüldü: %r", self._max, key)
                return False
            self._pending[key] = (fn, args)
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._run, name="tini-worker", daemon=True)
                self._thread.start()
            self._cv.notify()
            return True

    def depth(self) -> int:
        with self._cv:
            return len(self._pending)

    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._pending:
                    if not self._running:
                        return
                    if not self._cv.wait(timeout=30):
                        self._running = False  # 30 sn boşta: iş parçacığı kapanır
                        return
                key, (fn, args) = self._pending.popitem(last=False)
                self._busy = True
            try:
                fn(*args)
            except Exception:  # noqa: BLE001 - bir iş yürütücüyü öldürmemeli
                log.exception("worker işi başarısız: %r", key)
            finally:
                with self._cv:
                    self._busy = False
                    self.done += 1

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """Test yardımcısı: kuyruk boşalıp çalışan iş bitene kadar bekler."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._cv:
                if not self._pending and not self._busy:
                    return True
            time.sleep(0.01)
        return False


_last_activity = time.monotonic()


def touch() -> None:
    """Kullanıcı isteği geldi (requestlog çağırır); ağır turlar bundan sonra bekler."""
    global _last_activity
    _last_activity = time.monotonic()


def idle_seconds() -> float:
    return time.monotonic() - _last_activity


_worker: Worker | None = None
_lock = threading.Lock()


def get_worker() -> Worker:
    global _worker
    with _lock:
        if _worker is None:
            from app.config import get_graph_settings

            _worker = Worker(get_graph_settings().worker_queue_max)
        return _worker
