"""Servis bağlantısı için geçerli erişim değerini sağlar; süresi dolmak üzereyse yeniler."""
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.adapters.spotify import oauth
from app.config import get_settings
from app.models import ServiceConnection
from app.security import decrypt_value, encrypt_value

SKEW = timedelta(seconds=60)


def valid_access_value(db: Session, conn: ServiceConnection, http: httpx.Client) -> str:
    cfg = get_settings()
    if conn.expires_at is None or conn.expires_at - SKEW > datetime.now(UTC):
        return decrypt_value(cfg.credential_key, conn.access_token_enc)
    if conn.refresh_token_enc is None:
        raise PermissionError("Bağlantı yenilenemiyor; servisi yeniden bağla")
    refresh = decrypt_value(cfg.credential_key, conn.refresh_token_enc)
    fresh = oauth.refresh_tokens(http, cfg.spotify_client_id, refresh)
    conn.access_token_enc = encrypt_value(cfg.credential_key, fresh.access)
    if fresh.refresh:
        conn.refresh_token_enc = encrypt_value(cfg.credential_key, fresh.refresh)
    conn.expires_at = fresh.expires_at
    db.commit()
    return fresh.access
