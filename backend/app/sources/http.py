"""Kaynak istemcileri için ortak HTTP katmanı: hız sınırı, 429/5xx geri çekilme, User-Agent."""
import threading
import time
from collections.abc import Callable

import httpx

from app.config import GraphSettings


class SourceError(Exception):
    """Kaynak yanıt vermedi veya deneme sınırı aşıldı."""


class RateLimiter:
    """Slot ayıran hız sınırlayıcı: kilit altında sıradaki izinli zaman ilerletilir, bekleme
    kilit dışında yapılır; böylece eşzamanlı çağıranlar aynı aralığı paylaşır."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next: float | None = None

    def acquire(
        self, interval: float, clock: Callable[[], float], sleep: Callable[[float], None]
    ) -> None:
        with self._lock:
            now = clock()
            start = now if self._next is None else max(now, self._next)
            self._next = start + interval
        wait = start - now
        if wait > 0:
            sleep(wait)


_limiters: dict[str, RateLimiter] = {}
_limiters_lock = threading.Lock()


def get_limiter(source: str) -> RateLimiter:
    """Kaynak adına göre süreç geneli paylaşılan sınırlayıcı."""
    with _limiters_lock:
        return _limiters.setdefault(source, RateLimiter())


def reset_limiters() -> None:
    """Test izolasyonu: paylaşılan sınırlayıcıları sıfırlar."""
    with _limiters_lock:
        _limiters.clear()


class SourceClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        user_agent: str,
        min_interval: float,
        max_retries: int,
        backoff_base: float,
        backoff_max: float,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        source: str | None = None,
    ) -> None:
        if not user_agent:
            raise ValueError("User-Agent zorunlu")
        self._client = client
        self._ua = user_agent
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._sleep = sleep
        self._clock = clock
        # Kaynak adı verilirse süreç geneli paylaşılır; yoksa örneğe özel sınırlayıcı.
        self._limiter = get_limiter(source) if source else RateLimiter()

    @classmethod
    def from_settings(
        cls, client: httpx.Client, cfg: GraphSettings, *, user_agent: str, min_interval: float,
        source: str | None = None,
    ) -> "SourceClient":
        return cls(
            client, user_agent=user_agent, min_interval=min_interval, source=source,
            max_retries=cfg.http_max_retries, backoff_base=cfg.http_backoff_base_seconds,
            backoff_max=cfg.http_backoff_max_seconds,
        )

    def _throttle(self) -> None:
        self._limiter.acquire(self._min_interval, self._clock, self._sleep)

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        ra = resp.headers.get("Retry-After")
        if ra is not None:
            try:
                return min(max(float(ra), 0.0), self._backoff_max)
            except ValueError:
                pass
        return min(self._backoff_base * (2**attempt), self._backoff_max)

    def get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict | None:
        """GET → JSON. 404 → None. 429/5xx ve ağ hatalarında geri çekilir, sınırda SourceError."""
        return self._request_json("GET", url, params=params, extra_headers=headers)

    def post_json(
        self, url: str, body: dict, *, headers: dict[str, str] | None = None
    ) -> dict | None:
        """POST (JSON gövde) → JSON. Hata/geri çekilme davranışı get_json ile aynıdır.
        `headers` (ör. Authorization) günlüğe yazılmaz."""
        return self._request_json("POST", url, json_body=body, extra_headers=headers)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict | None:
        headers = {"User-Agent": self._ua, "Accept": "application/json", **(extra_headers or {})}
        last_err = "bilinmiyor"
        for attempt in range(self._max_retries + 1):
            self._throttle()
            try:
                if method == "POST":
                    resp = self._client.post(url, json=json_body, headers=headers)
                else:
                    resp = self._client.get(url, params=params, headers=headers)
            except httpx.TransportError as e:
                last_err = type(e).__name__
                if attempt < self._max_retries:
                    self._sleep(min(self._backoff_base * (2**attempt), self._backoff_max))
                continue
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = f"HTTP {resp.status_code}"
                if attempt < self._max_retries:
                    self._sleep(self._retry_delay(resp, attempt))
                continue
            if resp.status_code >= 400:
                raise SourceError(f"HTTP {resp.status_code}")
            try:
                return resp.json()
            except ValueError as e:  # JSON olmayan / boş gövde (ör. HTML hata sayfası)
                raise SourceError("JSON olmayan yanıt") from e
        raise SourceError(f"deneme sınırı aşıldı ({last_err})")
