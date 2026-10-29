from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    return create_engine(url or get_settings().database_url, pool_pre_ping=True)


def make_session_factory(engine=None) -> sessionmaker[Session]:
    return sessionmaker(engine or make_engine(), expire_on_commit=False)
