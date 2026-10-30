import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db import make_engine
from app.models import Track, User, UserTrackLink, VoteEvent


@pytest.fixture
def session():
    engine = make_engine()
    try:
        conn = engine.connect()
    except Exception:
        pytest.skip("PostgreSQL erişilemiyor")
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    trans.rollback()
    conn.close()


def _seed(s):
    u = User(email="a@example.com", password_hash="x")
    t = Track(isrc="TRAAA0000001")
    s.add_all([u, t])
    s.flush()
    return u, t


def test_vote_range_enforced(session):
    u, t = _seed(session)
    session.add(VoteEvent(user_id=u.id, track_id=t.id, vote=7))
    with pytest.raises(IntegrityError):
        session.flush()


def test_vote_event_is_append_only(session):
    u, t = _seed(session)
    session.add(VoteEvent(user_id=u.id, track_id=t.id, vote=4))
    session.flush()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(text("UPDATE vote_event SET vote = 5"))


def test_current_vote_is_latest_event(session):
    u, t = _seed(session)
    session.add_all([VoteEvent(user_id=u.id, track_id=t.id, vote=v) for v in (4, 6)])
    session.flush()
    latest = session.scalars(
        select(VoteEvent.vote)
        .where(VoteEvent.user_id == u.id, VoteEvent.track_id == t.id)
        .order_by(VoteEvent.id.desc())
        .limit(1)
    ).one()
    assert latest == 6


def test_account_delete_removes_personal_data_only(session):
    u, t = _seed(session)
    session.add_all(
        [
            VoteEvent(user_id=u.id, track_id=t.id, vote=5),
            UserTrackLink(user_id=u.id, service="spotify", external_id="abc", track_id=t.id),
        ]
    )
    session.flush()
    session.execute(delete(User).where(User.id == u.id))
    assert session.scalars(select(VoteEvent).where(VoteEvent.user_id == u.id)).all() == []
    assert session.scalars(select(UserTrackLink).where(UserTrackLink.user_id == u.id)).all() == []
    assert session.scalars(select(Track).where(Track.id == t.id)).one()
