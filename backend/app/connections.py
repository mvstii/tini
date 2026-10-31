"""Servis bağlantısı için geçerli erişim değerini sağlar; süresi dolmak üzereyse yeniler."""
from datetime import UTC, datetime, timedelta

import httpx
from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Session

from app.adapters.spotify import oauth
from app.config import get_settings
from app.models import ServiceConnection
from app.security import decrypt_value, encrypt_value

SKEW = timedelta(seconds=60)


def _decrypt(key: str, blob: bytes) -> str:
    try:
        return decrypt_value(key, blob)
    except InvalidToken as e:  # anahtar değişti/bozuldu; çağıranlar PermissionError'u 409'a çevirir
        raise PermissionError("Bağlantı çözülemiyor; servisi yeniden bağla") from e


def valid_access_value(db: Session, conn: ServiceConnection, http: httpx.Client) -> str:
    cfg = get_settings()
    if conn.expires_at is None or conn.expires_at - SKEW > datetime.now(UTC):
        return _decrypt(cfg.credential_key, conn.access_token_enc)
    if conn.refresh_token_enc is None:
        raise PermissionError("Bağlantı yenilenemiyor; servisi yeniden bağla")
    refresh = _decrypt(cfg.credential_key, conn.refresh_token_enc)
    fresh = oauth.refresh_tokens(http, cfg.spotify_client_id, refresh)
    conn.access_token_enc = encrypt_value(cfg.credential_key, fresh.access)
    if fresh.refresh:
        conn.refresh_token_enc = encrypt_value(cfg.credential_key, fresh.refresh)
    conn.expires_at = fresh.expires_at
    db.commit()
    return fresh.access
