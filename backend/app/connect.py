from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters.spotify import oauth
from app.config import get_settings
from app.deps import current_user, get_db
from app.models import OAuthState, ServiceConnection, User
from app.security import encrypt_value

router = APIRouter()
STATE_TTL = timedelta(minutes=10)


def get_http() -> Iterator[httpx.Client]:
    with httpx.Client(timeout=15) as c:
        yield c


@router.post("/connect/spotify/start")
def start(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    cfg = get_settings()
    if not cfg.spotify_client_id:
        raise HTTPException(503, "Spotify yapılandırılmamış")
    verifier, challenge = oauth.make_pkce()
    state, _ = oauth.make_pkce()
    db.execute(delete(OAuthState).where(OAuthState.expires_at <= datetime.now(UTC)))
    db.add(
        OAuthState(
            state=state, user_id=user.id, verifier=verifier,
            expires_at=datetime.now(UTC) + STATE_TTL,
        )
    )
    db.commit()
    url = oauth.build_authorize_url(
        cfg.spotify_client_id, cfg.spotify_redirect_uri, cfg.spotify_scopes, state, challenge
    )
    return {"authorize_url": url}


@router.get("/connect/spotify/callback", response_class=HTMLResponse)
def callback(
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    http: httpx.Client = Depends(get_http),
) -> str:
    pending = db.get(OAuthState, state) if state else None
    if pending is None or pending.expires_at <= datetime.now(UTC):
        raise HTTPException(400, "Geçersiz veya süresi dolmuş istek")
    db.delete(pending)
    if error or not code:
        db.commit()
        raise HTTPException(400, "Spotify bağlantısı reddedildi")

    cfg = get_settings()
    try:
        tokens = oauth.exchange_code(
            http, cfg.spotify_client_id, cfg.spotify_redirect_uri, code, pending.verifier
        )
        external_id = oauth.fetch_profile_id(http, tokens.access)
    except httpx.HTTPError as exc:
        db.rollback()
        raise HTTPException(502, "Spotify yanıt vermedi") from exc

    conn = db.scalar(
        select(ServiceConnection).where(
            ServiceConnection.user_id == pending.user_id,
            ServiceConnection.service == oauth.SERVICE,
        )
    )
    if conn is None:
        conn = ServiceConnection(user_id=pending.user_id, service=oauth.SERVICE)
        db.add(conn)
    conn.external_user_id = external_id
    conn.access_token_enc = encrypt_value(cfg.credential_key, tokens.access)
    conn.refresh_token_enc = (
        encrypt_value(cfg.credential_key, tokens.refresh) if tokens.refresh else None
    )
    conn.expires_at = tokens.expires_at
    conn.scopes = tokens.scopes
    db.commit()
    return "<html><body><h3>Spotify bağlandı. Uygulamaya dönebilirsin.</h3></body></html>"


@router.get("/connections")
def connections(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, str]]:
    rows = db.scalars(select(ServiceConnection).where(ServiceConnection.user_id == user.id))
    return [{"service": c.service, "external_user_id": c.external_user_id} for c in rows]
