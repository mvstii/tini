"""Profil kurulumu için veritabanı katmanı: oy olayları -> ProfileVote -> anlık görüntü."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import GraphSettings, ProfileSettings
from app.graph.service import get_matrix
from app.models import TasteProfile, Track, TrackLike, UnheardEvent, UserTrackArtist, VoteEvent
from app.profile.build import ProfileVote, build_profile
from app.profile.scoring import VoteEvt, implicit_negatives, implicit_positives, score_votes
from app.profile.unheard import UnheardEvt, UnheardStatus, resolve


def unheard_statuses(db: Session, user_id, cfg: ProfileSettings) -> list[UnheardStatus]:
    events = [
        UnheardEvt(*r)
        for r in db.execute(
            select(
                UnheardEvent.id, UnheardEvent.track_id, UnheardEvent.state, UnheardEvent.created_at
            ).where(UnheardEvent.user_id == user_id)
        )
    ]
    last_vote = dict(
        db.execute(
            select(VoteEvent.track_id, func.max(VoteEvent.created_at))
            .where(VoteEvent.user_id == user_id)
            .group_by(VoteEvent.track_id)
        ).all()
    )
    return resolve(events, last_vote, cfg.unheard_expire_after)


def load_profile_votes(
    db: Session, user_id, now: datetime, cfg: ProfileSettings
) -> list[ProfileVote]:
    rows = db.execute(
        select(VoteEvent.id, VoteEvent.track_id, VoteEvent.vote, VoteEvent.created_at).where(
            VoteEvent.user_id == user_id
        )
    ).all()
    scored = score_votes([VoteEvt(*r) for r in rows], now, cfg)
    scored += implicit_negatives(unheard_statuses(db, user_id, cfg), now, cfg)
    likes = db.execute(
        select(TrackLike.track_id, TrackLike.created_at).where(TrackLike.user_id == user_id)
    ).all()
    scored += implicit_positives(likes, {r[1] for r in rows}, now, cfg)
    track_ids = [s.track_id for s in scored]
    shared = dict(
        db.execute(select(Track.id, Track.artist_id).where(Track.id.in_(track_ids))).all()
    )
    private = dict(
        db.execute(
            select(UserTrackArtist.track_id, UserTrackArtist.artist_id).where(
                UserTrackArtist.user_id == user_id, UserTrackArtist.track_id.in_(track_ids)
            )
        ).all()
    )
    return [
        ProfileVote(
            s.track_id, shared.get(s.track_id) or private.get(s.track_id), s.vote, s.score, s.weight
        )
        for s in scored
    ]


def rebuild_profile(
    db: Session, user_id, now: datetime, cfg: ProfileSettings, graph_cfg: GraphSettings
) -> TasteProfile:
    votes = load_profile_votes(db, user_id, now, cfg)
    built = get_matrix(db, graph_cfg)
    graph_version, gm = built if built is not None else (None, None)
    body = build_profile(votes, gm, cfg, graph_version)
    version = (
        db.scalar(select(func.max(TasteProfile.version)).where(TasteProfile.user_id == user_id))
        or 0
    ) + 1
    row = TasteProfile(
        user_id=user_id,
        version=version,
        algo_version=cfg.profile_algo_version,
        graph_version=graph_version,
        body=body,
    )
    db.add(row)
    db.commit()
    return row
