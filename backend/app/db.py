import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    return create_engine(url or get_settings().database_url, pool_pre_ping=True)


def make_session_factory(engine=None) -> sessionmaker[Session]:
    return sessionmaker(engine or make_engine(), expire_on_commit=False)


# Süreç geneli ortak engine: her oy/istek yeni bağlantı havuzu açmasın.
_lock = threading.Lock()
_engine = None
_factory: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    with _lock:
        if _engine is None:
            _engine = make_engine()
        return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _factory
    engine = get_engine()
    with _lock:
        if _factory is None:
            _factory = make_session_factory(engine)
        return _factory


def reset_engine() -> None:
    """Ortak engine'i kapatıp sıfırlar (DATABASE_URL değişimi / test izolasyonu)."""
    global _engine, _factory
    with _lock:
        engine, _engine, _factory = _engine, None, None
    if engine is not None:
        engine.dispose()
