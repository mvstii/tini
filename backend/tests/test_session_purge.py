import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User, UserSession
from app import session_purge, session_purge_scheduler

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
def db(test_engine):
    try:
        conn = test_engine.connect()
    except Exception:
        pytest.skip("PostgreSQL erişilemiyor")
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    trans.rollback()
    conn.close()


def _seed(db, offsets_seconds):
    u = User(email=f"{uuid.uuid4().hex[:8]}@t.dev", password_hash="x")
    db.add(u)
    db.flush()
    for off in offsets_seconds:
        db.add(
            UserSession(
                token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                user_id=u.id,
                expires_at=NOW + timedelta(seconds=off),
            )
        )
    db.flush()
    return u


def _count(db, user):
    return db.scalar(
        select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)
    )


def test_deletes_only_expired_beyond_grace(db):
    # -7200: çoktan dolmuş; -1800: dolmuş ama ek süre içinde; +3600: geçerli
    u = _seed(db, [-7200, -1800, 3600])
    assert session_purge.purge_expired_sessions(db, NOW, 3600, 100) == 1
    assert _count(db, u) == 2


def test_batches_until_done(db):
    u = _seed(db, [-7200] * 7 + [3600])
    assert session_purge.purge_expired_sessions(db, NOW, 3600, 3) == 7
    assert _count(db, u) == 1


def test_loop_survives_errors(monkeypatch):
    calls = []

    def fake_run():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(session_purge_scheduler, "run", fake_run)

    async def go():
        task = asyncio.create_task(session_purge_scheduler._loop(0, 0.01))
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(go())
    assert len(calls) >= 2


def test_lifespan_disabled(monkeypatch):
    class Cfg:
        enabled = False

    monkeypatch.setattr(session_purge_scheduler, "get_session_purge_settings", lambda: Cfg())
    started = []
    monkeypatch.setattr(session_purge_scheduler, "run", lambda: started.append(1))

    async def go():
        async with session_purge_scheduler.lifespan(None):
            await asyncio.sleep(0.05)

    asyncio.run(go())
    assert started == []
