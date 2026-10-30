"""GET /recommend/candidates: son profilden gerekçeli PPR adayları (paylaşılan katalog verisi)."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    GraphSettings,
    ProfileSettings,
    RecommendSettings,
    get_graph_settings,
    get_profile_settings,
    get_recommend_settings,
)
from app.deps import current_user, get_db
from app.graph.service import get_matrix
from app.models import Artist, TasteProfile, User
from app.profile.service import load_profile_votes
from app.recommend.ppr import score_candidates

router = APIRouter(prefix="/recommend")


@router.get("/candidates")
def candidates(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    pcfg: ProfileSettings = Depends(get_profile_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    row = db.scalar(
        select(TasteProfile)
        .where(TasteProfile.user_id == user.id)
        .order_by(TasteProfile.version.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(404, "Henüz profil üretilmedi")
    built = get_matrix(db, gcfg)
    if built is None:
        raise HTTPException(409, "Grafik henüz kurulmadı")
    graph_version, gm = built

    known = {
        v.artist_id for v in load_profile_votes(db, user.id, datetime.now(UTC), pcfg)
        if v.artist_id is not None
    }
    cands = score_candidates(gm, row.body, known, cfg)
    ids = {c.artist_id for c in cands} | {r.seed_id for c in cands for r in c.reasons}
    names = dict(db.execute(select(Artist.id, Artist.name).where(Artist.id.in_(ids))).all())
    return {
        "algo_version": cfg.recommend_algo_version,
        "profile_version": row.version,
        "profile_graph_version": row.graph_version,
        "graph_version": graph_version,
        "candidates": [
            {
                "artist_id": c.artist_id,
                "name": names.get(c.artist_id),
                "score": round(c.score, 6),
                "raw": round(c.raw, 6),
                "novelty": round(c.novelty, 4),
                "penalty": round(c.penalty, 6),
                "reasons": [
                    {
                        "seed_id": r.seed_id,
                        "seed_name": names.get(r.seed_id),
                        "share": round(r.share, 4),
                        "is_anchor": r.is_anchor,
                    }
                    for r in c.reasons
                ],
            }
            for c in cands
        ],
    }
