"""Aşama zamanlayıcı (salt ölçüm): `Server-Timing` başlığı ve istek günlüğü için.

Bağımlılıksız ve saf: saat enjekte edilebilir; davranışı değiştirmez.
"""
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class Stages:
    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._mark = clock()
        self._ms: dict[str, float] = {}

    def add(self, name: str, ms: float) -> None:
        self._ms[name] = self._ms.get(name, 0.0) + ms

    def lap(self, name: str) -> None:
        """Önceki işaretten bu yana geçen süreyi `name` aşamasına yazar."""
        now = self._clock()
        self.add(name, (now - self._mark) * 1000)
        self._mark = now

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        t0 = self._clock()
        try:
            yield
        finally:
            self.add(name, (self._clock() - t0) * 1000)
            self._mark = self._clock()

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 1) for k, v in self._ms.items()}

    def header(self) -> str:
        """W3C Server-Timing değeri: `candidates;dur=12.3, rank;dur=4.0`."""
        return ", ".join(f"{k};dur={v}" for k, v in self.as_dict().items())
