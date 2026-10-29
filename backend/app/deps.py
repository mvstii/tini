from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import make_session_factory
from app.models import User, UserSession
from app.security import hash_token

_factory = None


def get_db() -> Iterator[Session]:
    global _factory
    if _factory is None:
        _factory = make_session_factory()
    with _factory() as s:
        yield s


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(401, "Kimlik doğrulama gerekli")
    sess = db.get(UserSession, hash_token(value))
    if sess is None or sess.expires_at <= datetime.now(UTC):
        raise HTTPException(401, "Oturum geçersiz")
    return db.get(User, sess.user_id)
