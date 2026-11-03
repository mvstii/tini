from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import current_user, get_db
from app.models import User, UserSession
from app.ratelimit import AuthLimits, client_ip, get_auth_limits, too_many
from app.security import (
    burn_verify,
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)

router = APIRouter()


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class SessionOut(BaseModel):
    token: str


def _issue(db: Session, user: User) -> SessionOut:
    value, digest = new_session_token()
    days = get_settings().session_ttl_days
    db.add(
        UserSession(
            token_hash=digest,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=days),
        )
    )
    db.commit()
    return SessionOut(token=value)


@router.post("/auth/register", status_code=201)
def register(
    body: Credentials,
    request: Request,
    db: Session = Depends(get_db),
    limits: AuthLimits = Depends(get_auth_limits),
) -> SessionOut:
    ip = client_ip(request)
    wait = limits.register_ip.retry_after(ip)
    if wait is not None:
        raise too_many(wait)
    limits.register_ip.hit(ip)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Bu e-posta zaten kayıtlı")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    return _issue(db, user)


@router.post("/auth/login")
def login(
    body: Credentials,
    request: Request,
    db: Session = Depends(get_db),
    limits: AuthLimits = Depends(get_auth_limits),
) -> SessionOut:
    ip = client_ip(request)
    email = body.email.lower()
    waits = [limits.login_email.retry_after(email), limits.login_ip.retry_after(ip)]
    if any(w is not None for w in waits):
        raise too_many(max(w for w in waits if w is not None))
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        burn_verify(body.password)
    if user is None or not verify_password(user.password_hash, body.password):
        limits.login_email.hit(email)
        limits.login_ip.hit(ip)
        raise HTTPException(401, "E-posta veya parola hatalı")
    limits.login_email.reset(email)
    return _issue(db, user)


@router.post("/auth/logout", status_code=204)
def logout(
    authorization: str = Header(default=""),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    value = authorization.partition(" ")[2]
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(value)))
    db.commit()


class PasswordConfirm(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.delete("/me", status_code=204)
def delete_me(
    body: PasswordConfirm,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    limits: AuthLimits = Depends(get_auth_limits),
) -> None:
    """Hesabı ve tüm kişisel veriyi siler (parola onayıyla); paylaşılan katalog kalır."""
    wait = limits.login_email.retry_after(user.email)
    if wait is not None:
        raise too_many(wait)
    if not verify_password(user.password_hash, body.password):
        limits.login_email.hit(user.email)
        raise HTTPException(403, "Parola hatalı")
    db.delete(user)
    db.commit()
    limits.login_email.reset(user.email)


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict[str, str]:
    return {"id": str(user.id), "email": user.email}
