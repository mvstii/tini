from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import current_user, get_db
from app.models import User, UserSession
from app.security import hash_password, hash_token, new_session_token, verify_password

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
def register(body: Credentials, db: Session = Depends(get_db)) -> SessionOut:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Bu e-posta zaten kayıtlı")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    return _issue(db, user)


@router.post("/auth/login")
def login(body: Credentials, db: Session = Depends(get_db)) -> SessionOut:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "E-posta veya parola hatalı")
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


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict[str, str]:
    return {"id": str(user.id), "email": user.email}
