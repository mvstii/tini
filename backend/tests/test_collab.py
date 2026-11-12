from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.catalog.collab import detect_collabs, split_parts
from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.service import clear_cache
from app.jobs.detect_collabs import run as detect_run
from app.models import (
    Artist,
    ArtistEdge,
    ArtistMember,
    GraphSnapshot,
    TasteProfile,
    User,
)
from app.recommend.service import compute_candidates

NOW = datetime(2026, 10, 31, tzinfo=UTC)


def test_split_parts():
    assert split_parts("Drake & 21 Savage") == ["Drake", "21 Savage"]
    assert split_parts("Maroon 5 feat. Christina Aguilera") == ["Maroon 5", "Christina Aguilera"]
    assert split_parts("Tyler, The Creator") == ["Tyler", "The Creator"]
    assert split_parts("Drake") == ["Drake"]


def test_detects_only_when_every_part_is_a_known_artist():
    artists = [
        (1, "Drake"), (2, "21 Savage"), (3, "Drake & 21 Savage"),
        (4, "Tyler, The Creator"), (5, "Captain & Tennille"), (6, "Captain"),
    ]
    got = detect_collabs(artists, with_edges={1, 2, 3, 4, 5, 6})
    assert got == {3: [1, 2]}  # "Tennille" ve "Tyler"/"The Creator" ayrı sanatçı değil


def test_member_without_edges_does_not_count():
    artists = [(1, "A"), (2, "B"), (3, "A & B")]
    assert detect_collabs(artists, with_edges={1, 3}) == {}


def test_name_is_not_its_own_member():
    assert detect_collabs([(1, "A & A")], with_edges={1}) == {}


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


def mk(db, name):
    a = Artist(name=name, name_norm=name.lower())
    db.add(a)
    db.flush()
    return a


def edge(a, b):
    return ArtistEdge(src=a.id, dst=b.id, source="lastfm", weight=0.9, fetched_at=NOW,
                      expires_at=NOW + timedelta(days=1))


def test_job_rebuilds_and_recommendation_skips_collab_node(db):
    clear_cache()
    seed, a, b = mk(db, "CSeed"), mk(db, "CX"), mk(db, "CY")
    collab = mk(db, "CX & CY")
    db.add_all([edge(seed, a), edge(seed, b), edge(seed, collab), edge(a, b)])
    db.add(GraphSnapshot(edge_count=4, params={}))
    user = User(email="collab@example.com", password_hash="x")
    db.add(user)
    db.flush()
    body = {
        "anchors": [{"artist_id": seed.id, "weight": 1.0}], "clusters": [], "avoid": [],
        "unclustered": [{"artist_id": seed.id, "affinity": 1.0}],
    }
    db.add(TasteProfile(user_id=user.id, version=1, algo_version="t", graph_version=1,
                        body=body))
    db.flush()
    pc, rc, gc = (ProfileSettings(_env_file=None), RecommendSettings(_env_file=None),
                  GraphSettings(_env_file=None))

    before = {c.artist_id for c in compute_candidates(db, user.id, NOW, rc, pc, gc).cands}
    assert collab.id in before

    members = sorted([a.id, b.id])
    for _ in range(2):  # tekrar çalıştırılabilir
        assert detect_run(db)[collab.id] == members
        rows = db.query(ArtistMember).filter(ArtistMember.collab_id == collab.id)
        assert sorted(r.member_id for r in rows) == members

    after = {c.artist_id for c in compute_candidates(db, user.id, NOW, rc, pc, gc).cands}
    assert collab.id not in after and {a.id, b.id} <= after
    clear_cache()
