"""Öneri veritabanı katmanı: son profil -> adaylar -> MMR listesi -> kalıcı liste."""
import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.matrix import GraphMatrix
from app.graph.service import get_matrix
from app.models import (
    ArtistMember,
    GeneratedList,
    ListFeedback,
    ListItem,
    TasteProfile,
    Track,
    UserTrackArtist,
    VoteEvent,
)
from app.profile.service import load_profile_votes, unheard_statuses
from app.recommend.bandit import SLOTS, allocate, slot_shares
from app.recommend.outcomes import ArtistVote, ItemRef, derive_outcomes
from app.recommend.ppr import Candidate, score_candidates
from app.recommend.select import select_mmr


class NoProfile(Exception):
    pass


class NoGraph(Exception):
    pass


@dataclass
class Scored:
    profile: TasteProfile
    graph_version: int
    gm: GraphMatrix
    cands: list[Candidate]


def compute_candidates(
    db: Session, user_id, now: datetime, cfg: RecommendSettings, pcfg: ProfileSettings,
    gcfg: GraphSettings,
) -> Scored:
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
    graph_version, gm = built
    known = {
        v.artist_id for v in load_profile_votes(db, user_id, now, pcfg) if v.artist_id is not None
    }
    # işbirliği düğümleri ("A & B") kendi başına önerilmez; üyeleri zaten ayrı skorlanır
    known |= set(db.scalars(select(ArtistMember.collab_id)))
    return Scored(row, graph_version, gm, score_candidates(gm, row.body, known, cfg))


def _pick_tracks(db: Session, user_id, artist_ids: list[int]) -> dict[int, int]:
    """Sanatçı içi şarkı: katalogdaki, kullanıcının oylamadığı en düşük kimlikli parça."""
    voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user_id)
    rows = db.execute(
        select(Track.artist_id, Track.id)
        .where(Track.artist_id.in_(artist_ids), Track.id.not_in(voted))
        .order_by(Track.artist_id, Track.id)
    ).all()
    picked: dict[int, int] = {}
    for artist_id, track_id in rows:
        picked.setdefault(artist_id, track_id)
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
            .where(GeneratedList.user_id == user_id)
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
    gcfg: GraphSettings,
) -> GeneratedList:
    sc = compute_candidates(db, user_id, now, cfg, pcfg, gcfg)
    pool = _pool_tracks(db, user_id, pcfg)
    pools = split_slots(sc.cands, pool, cfg.familiar_fraction)
    outcomes = slot_outcomes(db, user_id)
    shares = slot_shares(outcomes, cfg, sc.profile.version)
    counts = allocate(cfg.list_size, shares, {s: len(pools[s]) for s in SLOTS})
    slot_of: dict[int, str] = {}
    chosen = []
    for slot in SLOTS:
        for c in select_mmr(pools[slot], sc.gm, counts[slot], cfg.mmr_lambda):
            slot_of[c.artist_id] = slot
            chosen.append(c)
    chosen.sort(key=lambda c: (-c.score, c.artist_id))
    tracks = _pick_tracks(db, user_id, [c.artist_id for c in chosen]) if chosen else {}
    tracks.update({a: t for a, t in pool.items() if slot_of.get(a) == "unheard"})
    lst = GeneratedList(
        user_id=user_id,
        algo_version=cfg.list_algo_version,
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
    db.commit()
    return lst
