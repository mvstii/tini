from alembic import context

from app import models  # noqa: F401  (tabloları metadata'ya kaydeder)
from app.db import Base, make_engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = context.config.get_main_option("sqlalchemy.url")
    with make_engine(url or None).connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
