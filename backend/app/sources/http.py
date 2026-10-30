"""Kaynak istemcileri için ortak HTTP katmanı: hız sınırı, 429/5xx geri çekilme, User-Agent."""
import time
from collections.abc import Callable

import httpx

from app.config import GraphSettings


class SourceError(Exception):
    """Kaynak yanıt vermedi veya deneme sınırı aşıldı."""


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
        self._last: float | None = None

    @classmethod
    def from_settings(
        cls, client: httpx.Client, cfg: GraphSettings, *, user_agent: str, min_interval: float
    ) -> "SourceClient":
        return cls(
            client, user_agent=user_agent, min_interval=min_interval,
            max_retries=cfg.http_max_retries, backoff_base=cfg.http_backoff_base_seconds,
            backoff_max=cfg.http_backoff_max_seconds,
        )

    def _throttle(self) -> None:
        if self._last is not None:
            wait = self._min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        ra = resp.headers.get("Retry-After")
        if ra is not None:
            try:
                return min(max(float(ra), 0.0), self._backoff_max)
            except ValueError:
                pass
        return min(self._backoff_base * (2**attempt), self._backoff_max)

    def get_json(self, url: str, params: dict[str, str] | None = None) -> dict | None:
        """GET → JSON. 404 → None. 429/5xx ve ağ hatalarında geri çekilir, sınırda SourceError."""
        headers = {"User-Agent": self._ua, "Accept": "application/json"}
        last_err = "bilinmiyor"
        for attempt in range(self._max_retries + 1):
            self._throttle()
            try:
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
            return resp.json()
        raise SourceError(f"deneme sınırı aşıldı ({last_err})")
