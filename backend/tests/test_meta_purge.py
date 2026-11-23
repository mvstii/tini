import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Track, User, UserTrackMeta
from app.profile import meta_purge, meta_purge_scheduler

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
    """Her kaydırma için ayrı parça; expires_at = NOW + kaydırma."""
    u = User(email=f"{uuid.uuid4().hex[:8]}@t.dev", password_hash="x")
    db.add(u)
    db.flush()
    for i, off in enumerate(offsets_seconds):
        t = Track(isrc=f"TRPURGE{uuid.uuid4().hex[:5].upper()}{i}")
        db.add(t)
        db.flush()
        db.add(
            UserTrackMeta(
                user_id=u.id, track_id=t.id, title="T", artist_names=["A"],
                duration_ms=1, expires_at=NOW + timedelta(seconds=off),
            )
        )
    db.flush()
    return u


def _count(db, user):
    return db.scalar(
        select(func.count()).select_from(UserTrackMeta).where(UserTrackMeta.user_id == user.id)
    )


def test_deletes_only_expired_beyond_grace(db):
    # -7200: süresi çoktan dolmuş; -1800: dolmuş ama ek süre içinde; +3600: geçerli
    u = _seed(db, [-7200, -1800, 3600])
    n = meta_purge.purge_expired_meta(db, NOW, grace_seconds=3600, batch_size=100)
    assert n == 1
    assert _count(db, u) == 2


def test_batches_until_done(db):
    u = _seed(db, [-7200] * 7 + [3600])
    n = meta_purge.purge_expired_meta(db, NOW, grace_seconds=3600, batch_size=3)
    assert n == 7
    assert _count(db, u) == 1


def test_idempotent(db):
    u = _seed(db, [-7200])
    assert meta_purge.purge_expired_meta(db, NOW, 3600, 10) == 1
    assert meta_purge.purge_expired_meta(db, NOW, 3600, 10) == 0
    assert _count(db, u) == 0


def test_loop_survives_errors(monkeypatch):
    calls = []

    def fake_run():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(meta_purge_scheduler, "run", fake_run)

    async def go():
        task = asyncio.create_task(meta_purge_scheduler._loop(0, 0.01))
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(go())
    assert len(calls) >= 2


def test_lifespan_disabled(monkeypatch):
    class Cfg:
        enabled = False

    monkeypatch.setattr(meta_purge_scheduler, "get_meta_purge_settings", lambda: Cfg())
    started = []
    monkeypatch.setattr(meta_purge_scheduler, "run", lambda: started.append(1))

    async def go():
        async with meta_purge_scheduler.lifespan(None):
            await asyncio.sleep(0.05)

    asyncio.run(go())
    assert started == []
