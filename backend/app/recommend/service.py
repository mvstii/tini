"""Öneri veritabanı katmanı: son profil -> adaylar -> MMR listesi -> kalıcı liste."""
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.tags import load_genres
from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.matrix import GraphMatrix
from app.graph.service import get_matrix
from app.models import (
    ArtistMember,
    GeneratedList,
    ListFeedback,
    ListItem,
    Release,
    ReleaseArtist,
    TasteProfile,
    Track,
    TrackPopularity,
    UserTrackArtist,
    VoteEvent,
)
from app.profile.service import load_profile_votes, unheard_statuses
from app.recommend.bandit import SLOTS, allocate, far_share, slot_shares
from app.recommend.diverse import cached_labels, cap_share, home_weights, pick_far
from app.recommend.fresh import FreshRelease, rank_fresh
from app.recommend.genres import blend_labels
from app.recommend.outcomes import ArtistVote, ItemRef, derive_outcomes
from app.recommend.ppr import Candidate, Propagated, explain, propagate, score_candidates
from app.recommend.select import select_mmr
from app.releases.service import user_follows


class NoProfile(Exception):
    pass


class NoGraph(Exception):
    pass


class NoReleases(Exception):
    pass


@dataclass
class Scored:
    profile: TasteProfile
    graph_version: int
    gm: GraphMatrix
    cands: list[Candidate]
    prop: Propagated | None = None  # aynı yayılım Taze yuvasının gerekçelerinde yeniden kullanılır
    known: frozenset[int] = frozenset()


def latest_profile_graph(db: Session, user_id, gcfg: GraphSettings):
    row = db.scalar(
        select(TasteProfile)
        .where(TasteProfile.user_id == user_id)
        .order_by(TasteProfile.version.desc())
        .limit(1)
    )
    if row is None:
        raise NoProfile
    built = get_matrix(db, gcfg)
    if built is None:
        raise NoGraph
    return row, built[0], built[1]


def compute_candidates(
    db: Session, user_id, now: datetime, cfg: RecommendSettings, pcfg: ProfileSettings,
    gcfg: GraphSettings,
) -> Scored:
    row, graph_version, gm = latest_profile_graph(db, user_id, gcfg)
    known = {
        v.artist_id for v in load_profile_votes(db, user_id, now, pcfg) if v.artist_id is not None
    }
    # işbirliği düğümleri ("A & B") kendi başına önerilmez; üyeleri zaten ayrı skorlanır
    known |= set(db.scalars(select(ArtistMember.collab_id)))
    prop = propagate(gm, row.body, cfg)
    return Scored(
        row, graph_version, gm, score_candidates(gm, row.body, known, cfg, prop), prop,
        frozenset(known),
    )


def representative_pick(
    candidates: list[tuple[int, int]], seed: str, top_k: int
) -> int | None:
    """Saf: (parça, dinlenme) adaylarından en çok dinlenen `top_k` içinden tohumlu seçim.
    Aynı aday kümesi ve tohum her zaman aynı parçayı verir."""
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda c: (-c[1], c[0]))[: max(top_k, 1)]
    return random.Random(seed).choice(ranked)[0]


def _pick_tracks(
    db: Session, user_id, artist_ids: list[int], gcfg: GraphSettings | None = None,
    seed: str = "",
) -> dict[int, int]:
    """Sanatçı içi şarkı: kullanıcının oylamadığı parça. Omurga açıksa ve sanatçının dinlenme
    verisi varsa temsilci parça (en çok dinlenen K'dan tohumlu); yoksa en düşük kimlikli."""
    voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user_id)
    rows = db.execute(
        select(Track.artist_id, Track.id)
        .where(Track.artist_id.in_(artist_ids), Track.id.not_in(voted))
        .order_by(Track.artist_id, Track.id)
    ).all()
    picked: dict[int, int] = {}
    for artist_id, track_id in rows:
        picked.setdefault(artist_id, track_id)
    if gcfg is not None and gcfg.backbone_enabled and picked:
        pop = db.execute(
            select(Track.artist_id, Track.id, TrackPopularity.listens)
            .join(TrackPopularity, TrackPopularity.track_id == Track.id)
            .where(Track.artist_id.in_(list(picked)), Track.id.not_in(voted))
        ).all()
        by_artist: dict[int, list[tuple[int, int]]] = {}
        for artist_id, track_id, listens in pop:
            by_artist.setdefault(artist_id, []).append((track_id, listens))
        for artist_id, cands in by_artist.items():
            chosen = representative_pick(cands, f"{seed}:{artist_id}", gcfg.backbone_top_k)
            if chosen is not None:
                picked[artist_id] = chosen
    return picked


def slot_outcomes(db: Session, user_id) -> dict[str, tuple[int, int]]:
    """Önceki listelerin slot başına (başarı, başarısızlık) sayıları; olaylardan türetilir."""
    items = [
        ItemRef(*r)
        for r in db.execute(
            select(
                ListItem.list_id, ListItem.position, ListItem.artist_id, ListItem.slot,
                GeneratedList.created_at,
            )
            .join(GeneratedList, GeneratedList.id == ListItem.list_id)
            .where(GeneratedList.user_id == user_id, GeneratedList.kind == "main",
                ListItem.slot != "fresh",
            )
        )
    ]
    if not items:
        return {}
    artist = func.coalesce(Track.artist_id, UserTrackArtist.artist_id)
    votes = [
        ArtistVote(*r)
        for r in db.execute(
            select(VoteEvent.id, artist, VoteEvent.vote, VoteEvent.created_at)
            .join(Track, Track.id == VoteEvent.track_id)
            .outerjoin(
                UserTrackArtist,
                (UserTrackArtist.track_id == VoteEvent.track_id)
                & (UserTrackArtist.user_id == user_id),
            )
            .where(VoteEvent.user_id == user_id, artist.is_not(None))
        )
    ]
    feedback = {
        (r[0], r[1])
        for r in db.execute(
            select(ListFeedback.list_id, ListFeedback.position).where(
                ListFeedback.user_id == user_id
            )
        )
    }
    return derive_outcomes(items, votes, feedback)


def _pool_tracks(db: Session, user_id, pcfg: ProfileSettings) -> dict[int, int]:
    """Havuzdaki (süresi dolmamış, oylanmamış) parçalar: sanatçı -> en düşük kimlikli parça."""
    track_ids = [
        s.track_id for s in unheard_statuses(db, user_id, pcfg) if s.state != "expired"
    ]
    if not track_ids:
        return {}
    artist = func.coalesce(Track.artist_id, UserTrackArtist.artist_id)
    rows = db.execute(
        select(Track.id, artist)
        .outerjoin(
            UserTrackArtist,
            (UserTrackArtist.track_id == Track.id) & (UserTrackArtist.user_id == user_id),
        )
        .where(Track.id.in_(track_ids), artist.is_not(None))
        .order_by(Track.id)
    ).all()
    out: dict[int, int] = {}
    for track_id, artist_id in rows:
        out.setdefault(artist_id, track_id)
    return out


def split_slots(
    cands: list[Candidate], pool: dict[int, int], familiar_fraction: float
) -> dict[str, list[Candidate]]:
    """Havuz sanatçıları unheard; kalanın üst kesri familiar, gerisi explore."""
    ordered = sorted(cands, key=lambda c: (-c.score, c.artist_id))
    unheard = [c for c in ordered if c.artist_id in pool]
    rest = [c for c in ordered if c.artist_id not in pool]
    k = math.ceil(len(rest) * familiar_fraction)
    return {"familiar": rest[:k], "unheard": unheard, "explore": rest[k:]}


def generate_list(
    db: Session, user_id, now: datetime, cfg: RecommendSettings, pcfg: ProfileSettings,
    gcfg: GraphSettings, nonce: int = 0,
) -> GeneratedList:
    """`nonce` (list-6): "Yeniden üret" sayacı. 0 iken liste yalnız profile bağlıdır; > 0 iken
    slot içi seçim (profil sürümü, nonce) tohumuyla sarsılır. Aynı girdi + nonce = aynı liste."""
    sc = compute_candidates(db, user_id, now, cfg, pcfg, gcfg)
    v6 = cfg.list6_enabled
    outcomes = slot_outcomes(db, user_id)
    far_frac = far_share(outcomes, cfg, sc.profile.version) if v6 else cfg.far_share
    cluster_cap = cfg.list6_max_cluster_share if v6 else cfg.max_cluster_share
    tau = cfg.list_gumbel_tau if v6 and nonce > 0 else 0.0
    fresh, _ = fresh_ranked(db, user_id, sc.profile, sc.gm, now.date(), cfg, sc.prop)
    fresh = fresh[: round(cfg.list_size * cfg.fresh_share)]
    fresh_artists = {i.artist_id for i in fresh}
    pool = _pool_tracks(db, user_id, pcfg)
    labels = cached_labels(sc.gm, sc.graph_version, cfg.community_count, cfg.community_seed)
    genre_of = load_genres(db, sc.gm.node_ids.tolist()) if cfg.use_genre_labels else {}
    labels = blend_labels(labels, genre_of)
    seeds = (
        list(zip(map(int, sc.prop.seed_ids), map(float, sc.prop.w), strict=True))
        if sc.prop is not None else []
    )
    home = home_weights(seeds, labels)
    wide_cfg = cfg.model_copy(update={"candidate_top_n": cfg.far_pool_size})
    wide = score_candidates(sc.gm, sc.profile.body, set(sc.known), wide_cfg, sc.prop)
    far = [
        c for c in pick_far(
            [c for c in wide if c.artist_id not in fresh_artists], labels, home,
            round(cfg.list_size * far_frac), cfg.far_home_exclude,
            cfg.far_true_count if v6 else None,
        )
    ]
    far_ids = {c.artist_id for c in far}
    pools = split_slots(
        [c for c in sc.cands if c.artist_id not in fresh_artists | far_ids], pool,
        cfg.familiar_fraction,
    )
    shares = slot_shares(outcomes, cfg, sc.profile.version)
    room = cfg.list_size - len(fresh) - len(far)
    counts = allocate(room, shares, {s: len(pools[s]) for s in SLOTS})
    slot_of: dict[int, str] = {c.artist_id: "far" for c in far}
    chosen = list(far)
    for slot in SLOTS:
        picked = select_mmr(
            pools[slot], sc.gm, counts[slot], cfg.mmr_lambda, tau, sc.profile.version * 1000 + nonce
        )
        for c in picked:
            slot_of[c.artist_id] = slot
            chosen.append(c)
    chosen.sort(key=lambda c: (-c.score, c.artist_id))
    spare = [c for c in sc.cands if c.artist_id not in fresh_artists]
    kept = cap_share(chosen, spare, labels, cfg.list_size, cluster_cap)
    for c in kept:
        slot_of.setdefault(c.artist_id, "explore")  # tavan sonrası dolgu adayları
    chosen = kept
    tracks = (
        _pick_tracks(
            db, user_id, [c.artist_id for c in chosen], gcfg, f"{user_id}:{sc.profile.version}"
        )
        if chosen else {}
    )
    tracks.update({a: t for a, t in pool.items() if slot_of.get(a) == "unheard"})
    lst = GeneratedList(
        user_id=user_id,
        algo_version=cfg.list6_algo_version if v6 else cfg.list_algo_version,
        candidate_algo_version=cfg.recommend_algo_version,
        profile_version=sc.profile.version,
        graph_version=sc.graph_version,
        params={
            "list_size": cfg.list_size, "mmr_lambda": cfg.mmr_lambda,
            "ppr_alpha": cfg.ppr_alpha, "ppr_iterations": cfg.ppr_iterations,
            "anchor_boost": cfg.anchor_boost, "bad_penalty_beta": cfg.bad_penalty_beta,
            "novelty_gamma": cfg.novelty_gamma, "candidate_top_n": cfg.candidate_top_n,
            "slot_shares": {k: round(v, 6) for k, v in shares.items()},
            "slot_counts": counts,
            "far_count": len(far), "far_share": round(far_frac, 6),
            "max_cluster_share": cluster_cap, "community_count": cfg.community_count,
            **(
                {"nonce": nonce, "gumbel_tau": tau, "far_true_count": cfg.far_true_count,
                 "far_floor_share": cfg.far_floor_share, "far_max_share": cfg.far_max_share}
                if v6 else {}
            ),
            "genre_labeled": len(genre_of),
            "fresh_share": cfg.fresh_share, "fresh_count": len(fresh),
            "slot_outcomes": {k: list(v) for k, v in outcomes.items()},
        },
    )
    db.add(lst)
    db.flush()
    for pos, c in enumerate(chosen, start=1):
        db.add(
            ListItem(
                list_id=lst.id, position=pos, artist_id=c.artist_id,
                track_id=tracks.get(c.artist_id), score=c.score, slot=slot_of[c.artist_id],
                reasons=[
                    {"seed_id": r.seed_id, "share": r.share, "is_anchor": r.is_anchor}
                    for r in c.reasons
                ],
            )
        )
    for pos, i in enumerate(fresh, start=len(chosen) + 1):  # "Yeni" yuvası listenin sonunda
        db.add(_fresh_item(lst.id, pos, i))
    db.commit()
    return lst


def window_releases(
    db: Session, artist_ids, today: date, days: int, exclude_release_ids=()
) -> list[FreshRelease]:
    """Verilen sanatçıların pencere içindeki yayınları (sanatçı, yayın) çiftleri."""
    if not artist_ids:
        return []
    rows = db.execute(
        select(Release.id, ReleaseArtist.artist_id, Release.first_release_date)
        .join(ReleaseArtist, ReleaseArtist.release_id == Release.id)
        .where(
            ReleaseArtist.artist_id.in_(list(artist_ids)),
            Release.first_release_date >= today - timedelta(days=days),
            Release.first_release_date <= today,
        )
    ).all()
    skip = set(exclude_release_ids)
    return [FreshRelease(*r) for r in rows if r[0] not in skip]


def fresh_ranked(
    db: Session, user_id, prof: TasteProfile, gm: GraphMatrix, today: date, cfg: RecommendSettings,
    prop: Propagated | None = None,
):
    """Takip edilen sanatçıların, önceki listelerde çıkmamış yayınları; sıralı ve gerekçeli."""
    follows = user_follows(db, user_id)
    seen = set(
        db.scalars(
            select(ListItem.release_id)
            .join(GeneratedList, GeneratedList.id == ListItem.list_id)
            .where(GeneratedList.user_id == user_id, ListItem.release_id.is_not(None))
        )
    )
    releases = window_releases(db, follows, today, cfg.fresh_window_days, seen)
    scores = explain(gm, prof.body, {r.artist_id for r in releases}, cfg, prop)
    return rank_fresh(releases, scores, today, cfg), len(follows)


def _fresh_item(list_id: int, pos: int, i) -> ListItem:
    return ListItem(
        list_id=list_id, position=pos, artist_id=i.artist_id, release_id=i.release_id,
        score=i.score, slot="fresh",
        reasons=[
            {"seed_id": r.seed_id, "share": r.share, "is_anchor": r.is_anchor} for r in i.reasons
        ],
    )


def generate_fresh(
    db: Session, user_id, now: datetime, cfg: RecommendSettings, gcfg: GraphSettings
) -> GeneratedList:
    """Haftalık Taze liste: takip edilen sanatçıların yayınları (albüm düzeyi), gerekçeli."""
    prof, graph_version, gm = latest_profile_graph(db, user_id, gcfg)
    ranked, followed = fresh_ranked(db, user_id, prof, gm, now.date(), cfg)
    if not ranked:
        raise NoReleases
    lst = GeneratedList(
        user_id=user_id, kind="fresh", algo_version=cfg.fresh_algo_version,
        candidate_algo_version=cfg.recommend_algo_version, profile_version=prof.version,
        graph_version=graph_version,
        params={
            "fresh_list_size": cfg.fresh_list_size, "fresh_window_days": cfg.fresh_window_days,
            "fresh_half_life_days": cfg.fresh_half_life_days, "ppr_alpha": cfg.ppr_alpha,
            "ppr_iterations": cfg.ppr_iterations, "anchor_boost": cfg.anchor_boost,
            "novelty_gamma": cfg.novelty_gamma, "followed": followed,
        },
    )
    db.add(lst)
    db.flush()
    for pos, i in enumerate(ranked, start=1):
        db.add(_fresh_item(lst.id, pos, i))
    db.commit()
    return lst
