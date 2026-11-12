import pytest
from sqlalchemy.orm import Session

from app.graph.store import neighbor_artist_id


@pytest.fixture
def db(test_engine):
    engine = test_engine
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


def test_overlong_neighbor_name_does_not_overflow_ref_and_is_stable(db):
    name = "nu" * 150  # Last.fm'den gelen gerçek çöp ad: provider_id sütununu (128) aşar
    a = neighbor_artist_id(db, None, name)
    b = neighbor_artist_id(db, None, name)
    assert a == b
    other = neighbor_artist_id(db, None, "nu" * 151)
    assert other != a  # kesilen önek aynı olsa da özet ayırır
