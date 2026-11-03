"""Kayan pencereli hız sınırı. Durum bellekte tutulur (tek işlemli MVP); saat parametre."""
import time
from collections import defaultdict, deque
from collections.abc import Callable
from functools import lru_cache
from math import ceil

from fastapi import HTTPException, Request

from app.config import AuthSettings


class SlidingWindowLimiter:
    """`limit` vuruşa kadar izin verir; pencere (saniye) içindeki vuruşlar sayılır."""

    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        q = self._hits[key]
        cutoff = self._clock() - self.window
        while q and q[0] <= cutoff:
            q.popleft()
        if not q:
            self._hits.pop(key, None)
            return deque()
        return q

    def retry_after(self, key: str) -> int | None:
        """Sınır dolmuşsa beklenecek saniye, değilse None."""
        q = self._prune(key)
        if len(q) < self.limit:
            return None
        return max(1, ceil(q[0] + self.window - self._clock()))

    def hit(self, key: str) -> None:
        self._prune(key)
        self._hits[key].append(self._clock())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)

    def clear(self) -> None:
        self._hits.clear()


class AuthLimits:
    """Giriş (e-posta + IP) ve kayıt (IP) sınırlayıcıları."""

    def __init__(self, s: AuthSettings) -> None:
        self.login_email = SlidingWindowLimiter(s.login_email_limit, s.login_window_seconds)
        self.login_ip = SlidingWindowLimiter(s.login_ip_limit, s.login_window_seconds)
        self.register_ip = SlidingWindowLimiter(s.register_ip_limit, s.register_window_seconds)

    def clear(self) -> None:
        for lim in (self.login_email, self.login_ip, self.register_ip):
            lim.clear()


@lru_cache
def get_auth_limits() -> AuthLimits:
    return AuthLimits(AuthSettings())


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        429,
        "Çok fazla deneme, biraz sonra tekrar dene",
        headers={"Retry-After": str(retry_after)},
    )
