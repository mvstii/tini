# ruff: noqa: F811
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import ArtistEdge, GraphSnapshot
from tests.test_profile_api import NOW, client, db, library_track, mk_artist, register  # noqa: F401


def edge(a, b, w=0.9):
    return ArtistEdge(src=a.id, dst=b.id, source="lastfm", weight=w, fetched_at=NOW,
                      expires_at=NOW + timedelta(days=1))


def test_candidates_404_without_profile(client, db):
    h = register(client, "r0@example.com")
    assert client.get("/recommend/candidates", headers=h).status_code == 404


def test_candidates_with_reasons_and_known_excluded(client, db):
    h = register(client, "r1@example.com")
    seed, cand, voted = (mk_artist(db, n) for n in ("RSeed", "RCand", "RVoted"))
    db.add_all([edge(seed, cand), edge(seed, voted)])
    db.add(GraphSnapshot(edge_count=2, params={}))
    db.flush()
    t1 = library_track(db, "r1@example.com", "ZZR000000001", seed)
    t2 = library_track(db, "r1@example.com", "ZZR000000002", voted)
    client.post("/votes", json={"track": t1.id, "vote": 6}, headers=h)
    client.post("/votes", json={"track": t2.id, "vote": 4}, headers=h)
    client.post("/profile/rebuild", headers=h)

    body = client.get("/recommend/candidates", headers=h).json()
    got = {c["artist_id"]: c for c in body["candidates"]}
    assert cand.id in got and voted.id not in got and seed.id not in got
    reasons = got[cand.id]["reasons"]  # Good oylu RVoted da tohum; çapa boost'u ilk sırada
    assert reasons[0]["seed_id"] == seed.id and reasons[0]["seed_name"] == "RSeed"
    assert reasons[0]["is_anchor"] and not reasons[1]["is_anchor"]
    assert sum(r["share"] for r in reasons) == pytest.approx(1.0, abs=1e-3)
    assert got[cand.id]["name"] == "RCand"
    assert body["algo_version"] == "recommend-1" and body["profile_version"] == 1
    assert body["graph_version"] == db.scalar(select(GraphSnapshot.version).order_by(
        GraphSnapshot.version.desc()).limit(1))
