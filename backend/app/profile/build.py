"""Profil anlık görüntüsü kurucusu (saf): aynı oylar + aynı matris + aynı tohum = aynı profil.

Sanatçı başına net eğilim = Σ skor·ağırlık. Pozitif sanatçılar grafikteki komşuluk satırlarına
göre KMeans ile zevk modlarına ayrılır; Amazing'li pozitif sanatçılar çapadır; net negatif
sanatçılar kaçınma bölgesidir (Awful içerenler "sert").
"""
from collections import defaultdict
from dataclasses import dataclass

from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize

from app.config import ProfileSettings
from app.graph.matrix import GraphMatrix


@dataclass(frozen=True)
class ProfileVote:
    track_id: int
    artist_id: int | None  # çözülmemişse None; profile girmez
    vote: int
    score: float
    weight: float


def _cluster(
    artists: list[int], gm: GraphMatrix | None, cfg: ProfileSettings
) -> tuple[dict[int, int], list[int]]:
    """(sanatçı -> ham küme etiketi, grafikte olmayanlar). Etiketler sıralı artists'e göre."""
    if gm is None:
        return {}, list(artists)
    pos = {a: gm.position(a) for a in artists}
    in_graph = [a for a in artists if pos[a] is not None]
    outside = [a for a in artists if pos[a] is None]
    if not in_graph:
        return {}, outside
    k = min(cfg.cluster_count, len(in_graph) // cfg.cluster_min_artists)
    if k < 2:
        return {a: 0 for a in in_graph}, outside
    rows = normalize(gm.matrix[[pos[a] for a in in_graph]])
    labels = KMeans(
        n_clusters=k, n_init=cfg.cluster_n_init, random_state=cfg.cluster_seed
    ).fit_predict(rows)
    return {a: int(lab) for a, lab in zip(in_graph, labels, strict=True)}, outside


def build_profile(
    votes: list[ProfileVote],
    gm: GraphMatrix | None,
    cfg: ProfileSettings,
    graph_version: int | None,
) -> dict:
    net: dict[int, float] = defaultdict(float)
    anchor_w: dict[int, float] = defaultdict(float)
    hard: set[int] = set()
    unresolved = 0
    for v in votes:
        if v.artist_id is None:
            unresolved += 1
            continue
        net[v.artist_id] += v.score * v.weight
        if v.vote == cfg.anchor_vote:
            anchor_w[v.artist_id] += v.score * v.weight
        if v.vote in cfg.hard_avoid_votes:
            hard.add(v.artist_id)

    positives = sorted(a for a, n in net.items() if n > 0)
    raw, outside = _cluster(positives, gm, cfg)

    groups: dict[int, list[int]] = defaultdict(list)
    for a, label in raw.items():
        groups[label].append(a)
    # Etiketler keyfî; ağırlığa (azalan), eşitlikte en küçük sanatçı kimliğine göre sırala.
    ordered = sorted(groups.values(), key=lambda m: (-sum(net[a] for a in m), min(m)))
    clusters = [
        {
            "id": i,
            "weight": round(sum(net[a] for a in m), 6),
            "artists": [{"artist_id": a, "affinity": round(net[a], 6)} for a in sorted(m)],
        }
        for i, m in enumerate(ordered)
    ]
    return {
        "algo_version": cfg.profile_algo_version,
        "graph_version": graph_version,
        "cluster_seed": cfg.cluster_seed,
        "vote_count": len(votes),
        "unresolved_votes": unresolved,
        "clusters": clusters,
        "unclustered": [{"artist_id": a, "affinity": round(net[a], 6)} for a in outside],
        "anchors": [
            {"artist_id": a, "weight": round(w, 6)}
            for a, w in sorted(anchor_w.items())
            if net[a] > 0 and w > 0
        ],
        "avoid": [
            {"artist_id": a, "strength": round(-n, 6), "hard": a in hard}
            for a, n in sorted(net.items())
            if n < 0
        ],
    }

