from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session_factory
from app.models import User, UserSession
from app.security import hash_token


def get_db() -> Iterator[Session]:
    with get_session_factory()() as s:
        yield s


def current_user(
    request: Request, authorization: str = Header(default=""), db: Session = Depends(get_db)
) -> User:
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(401, "Kimlik doğrulama gerekli")
    sess = db.get(UserSession, hash_token(value))
    if sess is None or sess.expires_at <= datetime.now(UTC):
        raise HTTPException(401, "Oturum geçersiz")
    request.state.user_id = sess.user_id
    return db.get(User, sess.user_id)
