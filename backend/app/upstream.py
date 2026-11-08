"""Dış servis (Spotify vb.) hatalarını istemciye anlaşılır yanıta çevirir."""
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
from fastapi import HTTPException

from app.config import get_settings


def parse_retry_after(value: str | None, default: float, now: datetime | None = None) -> float:
    """`Retry-After` saniye ya da HTTP-date olabilir; ayrıştırılamazsa `default` döner."""
    if value is None:
        return default
    value = value.strip()
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return default
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max((when - (now or datetime.now(UTC))).total_seconds(), 0.0)


def upstream_unavailable(exc: httpx.HTTPError, what: str) -> HTTPException:
    """401/403 → 409 (yetki reddi); 429/5xx ve ağ hataları → 503 + Retry-After; diğerleri → 502."""
    resp = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
    if resp is not None and resp.status_code in (401, 403):
        return HTTPException(409, f"{what}: servis yetkisi reddedildi")
    default = get_settings().upstream_retry_after_seconds
    if resp is None or resp.status_code == 429 or resp.status_code >= 500:
        wait = parse_retry_after(resp.headers.get("Retry-After") if resp else None, default)
        return HTTPException(
            503,
            f"{what}: servis şu an yanıt vermiyor, biraz sonra tekrar dene",
            headers={"Retry-After": str(max(1, round(wait)))},
        )
    return HTTPException(502, f"{what}: servise ulaşılamadı")
