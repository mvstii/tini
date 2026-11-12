"""Faz 5 değerlendirme raporu: ölçütleri kişisel olay kayıtlarından hesaplar. Yalnızca okur.

CLI: python -m app.jobs.evaluate EPOSTA
"""
import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_recommend_settings
from app.db import make_engine
from app.models import (
    GeneratedList,
    ListFeedback,
    ListItem,
    Track,
    UnheardEvent,
    User,
    UserTrackArtist,
    VoteEvent,
)
from app.recommend.metrics import (
    EvalItem,
    PoolEvent,
    Report,
    SourceStat,
    TrackVote,
    evaluate_items,
    evaluate_sources,
    evaluate_unheard,
    format_report,
    format_sources,
)
from app.recommend.outcomes import ArtistVote


def collect(db: Session, user_id) -> Report:
    items = [
        EvalItem(*r)
        for r in db.execute(
            select(
                ListItem.list_id, ListItem.position, ListItem.artist_id, ListItem.slot,
                ListItem.score, GeneratedList.created_at,
            )
            .join(GeneratedList, GeneratedList.id == ListItem.list_id)
            .where(GeneratedList.user_id == user_id)
        )
    ]
    artist = func.coalesce(Track.artist_id, UserTrackArtist.artist_id)
    artist_votes = [
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
    rep = evaluate_items(items, artist_votes, feedback)
    pool = [
        PoolEvent(*r)
        for r in db.execute(
            select(UnheardEvent.track_id, UnheardEvent.state, UnheardEvent.created_at).where(
                UnheardEvent.user_id == user_id
            )
        )
    ]
    track_votes = [
        TrackVote(*r)
        for r in db.execute(
            select(VoteEvent.id, VoteEvent.track_id, VoteEvent.vote, VoteEvent.created_at).where(
                VoteEvent.user_id == user_id
            )
        )
    ]
    evaluate_unheard(rep, pool, track_votes)
    return rep


def collect_sources(db: Session, user_id) -> dict[str, SourceStat]:
    votes = db.execute(
        select(VoteEvent.id, VoteEvent.track_id, VoteEvent.vote, VoteEvent.source).where(
            VoteEvent.user_id == user_id
        )
    ).all()
    unheard = db.execute(
        select(UnheardEvent.track_id, UnheardEvent.source).where(UnheardEvent.user_id == user_id)
    ).all()
    return evaluate_sources(votes, unheard)


def run(email: str) -> list[str]:
    cfg = get_recommend_settings()
    with Session(make_engine()) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Kullanıcı yok: {email}")
        return [
            *format_report(collect(db, user.id), cfg.eval_min_sample),
            *format_sources(collect_sources(db, user.id), cfg.eval_min_sample),
        ]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolu ↔ ve ★ yazamaz
    print("\n".join(run(args.email)))
