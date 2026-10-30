"""Öneri veritabanı katmanı: son profil -> adaylar -> MMR listesi -> kalıcı liste."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.matrix import GraphMatrix
from app.graph.service import get_matrix
from app.models import ArtistMember, GeneratedList, ListItem, TasteProfile, Track, VoteEvent
from app.profile.service import load_profile_votes
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


def generate_list(
    db: Session, user_id, now: datetime, cfg: RecommendSettings, pcfg: ProfileSettings,
    gcfg: GraphSettings,
) -> GeneratedList:
    sc = compute_candidates(db, user_id, now, cfg, pcfg, gcfg)
    chosen = select_mmr(sc.cands, sc.gm, cfg.list_size, cfg.mmr_lambda)
    tracks = _pick_tracks(db, user_id, [c.artist_id for c in chosen]) if chosen else {}
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
        },
    )
    db.add(lst)
    db.flush()
    for pos, c in enumerate(chosen, start=1):
        db.add(
            ListItem(
                list_id=lst.id, position=pos, artist_id=c.artist_id,
                track_id=tracks.get(c.artist_id), score=c.score,
                reasons=[
                    {"seed_id": r.seed_id, "share": r.share, "is_anchor": r.is_anchor}
                    for r in c.reasons
                ],
            )
        )
    db.commit()
    return lst
