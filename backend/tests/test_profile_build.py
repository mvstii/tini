import numpy as np

from app.config import GraphSettings, ProfileSettings
from app.graph.matrix import build_matrix
from app.profile.build import ProfileVote, build_profile

CFG = ProfileSettings(_env_file=None, cluster_count=2, cluster_min_artists=2)
GCFG = GraphSettings(_env_file=None)


def two_communities():
    """Sanatçı 1–4 hub 100/101'e, 11–14 hub 200/201'e bağlı; iki ayrı topluluk."""
    src, dst = [], []
    for group, hubs in (([1, 2, 3, 4], [100, 101]), ([11, 12, 13, 14], [200, 201])):
        for a in group:
            for h in hubs:
                src.append(a)
                dst.append(h)
    return build_matrix(np.array(src), np.array(dst), np.full(len(src), 0.8), GCFG)


def pv(track, artist, vote, score, weight=1.0):
    return ProfileVote(track, artist, vote, score, weight)


def likes():
    return [pv(i, a, 5, 0.7) for i, a in enumerate([1, 2, 3, 4, 11, 12, 13, 14], start=1)]


def test_two_communities_become_two_clusters():
    body = build_profile(likes(), two_communities(), CFG, graph_version=7)
    got = sorted(sorted(x["artist_id"] for x in c["artists"]) for c in body["clusters"])
    assert got == [[1, 2, 3, 4], [11, 12, 13, 14]]
    assert body["graph_version"] == 7 and body["algo_version"] == "profile-2"


def test_deterministic_across_input_order_and_cluster_ids_stable():
    gm = two_communities()
    a = build_profile(likes(), gm, CFG, 1)
    b = build_profile(list(reversed(likes())), gm, CFG, 1)
    assert a == b
    assert [c["id"] for c in a["clusters"]] == [0, 1]


def test_no_graph_means_unclustered():
    body = build_profile(likes(), None, CFG, None)
    assert body["clusters"] == []
    assert len(body["unclustered"]) == 8


def test_artist_outside_graph_is_unclustered():
    votes = likes() + [pv(99, 999, 4, 0.35)]
    body = build_profile(votes, two_communities(), CFG, 1)
    assert [u["artist_id"] for u in body["unclustered"]] == [999]


def test_too_few_artists_gives_single_cluster():
    votes = [pv(1, 1, 5, 0.7), pv(2, 2, 5, 0.7), pv(3, 11, 5, 0.7)]
    body = build_profile(votes, two_communities(), CFG, 1)
    assert len(body["clusters"]) == 1


def test_anchors_only_amazing_with_positive_net():
    votes = [
        pv(1, 1, 6, 1.0),
        pv(2, 2, 5, 0.7),
        pv(3, 3, 6, 1.0),
        pv(4, 3, 1, -1.0),  # aynı sanatçıda Awful: net 0 -> çapa değil
    ]
    body = build_profile(votes, two_communities(), CFG, 1)
    assert body["anchors"] == [{"artist_id": 1, "weight": 1.0}]


def test_avoid_zone_net_negative_and_hard_flag():
    votes = [
        pv(1, 1, 1, -1.0),
        pv(2, 2, 2, -0.6),
        pv(3, 3, 4, 0.35),
        pv(4, 3, 2, -0.6),  # net -0.25 -> kaçınma, sert değil
        pv(5, 4, 6, 1.0),
    ]
    body = build_profile(votes, two_communities(), CFG, 1)
    avoid = {a["artist_id"]: a for a in body["avoid"]}
    assert set(avoid) == {1, 2, 3}
    assert avoid[1]["hard"] and not avoid[2]["hard"] and not avoid[3]["hard"]
    assert avoid[3]["strength"] == 0.25


def test_weight_scales_affinity_and_unresolved_counted():
    votes = [pv(1, 1, 5, 0.7, weight=0.5), pv(2, None, 5, 0.7)]
    body = build_profile(votes, None, CFG, None)
    assert body["unclustered"] == [{"artist_id": 1, "affinity": 0.35}]
    assert body["unresolved_votes"] == 1 and body["vote_count"] == 2
