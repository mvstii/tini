"""/recommend/candidates (ham PPR adayları) ve /lists (kalıcı MMR listesi).

Yanıtlardaki adlar yalnızca paylaşılan katalogdaki sanatçı adlarıdır.
"""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
from app.models import Artist, GeneratedList, ListFeedback, ListItem, User, UserTrackMeta
from app.recommend.service import NoGraph, NoProfile, compute_candidates, generate_list

router = APIRouter(prefix="/recommend")
lists_router = APIRouter(prefix="/lists")


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    return dict(db.execute(select(Artist.id, Artist.name).where(Artist.id.in_(ids))).all())


def _reason(r: dict, names: dict) -> dict:
    return {
        "seed_id": r["seed_id"],
        "seed_name": names.get(r["seed_id"]),
        "share": round(r["share"], 4),
        "is_anchor": r["is_anchor"],
    }


@router.get("/candidates")
def candidates(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    pcfg: ProfileSettings = Depends(get_profile_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    try:
        sc = compute_candidates(db, user.id, datetime.now(UTC), cfg, pcfg, gcfg)
    except NoProfile:
        raise HTTPException(404, "Henüz profil üretilmedi") from None
    except NoGraph:
        raise HTTPException(409, "Grafik henüz kurulmadı") from None
    cands = sc.cands
    names = _names(db, {c.artist_id for c in cands} | {r.seed_id for c in cands for r in c.reasons})
    return {
        "algo_version": cfg.recommend_algo_version,
        "profile_version": sc.profile.version,
        "profile_graph_version": sc.profile.graph_version,
        "graph_version": sc.graph_version,
        "candidates": [
            {
                "artist_id": c.artist_id,
                "name": names.get(c.artist_id),
                "score": round(c.score, 6),
                "raw": round(c.raw, 6),
                "novelty": round(c.novelty, 4),
                "penalty": round(c.penalty, 6),
                "reasons": [
                    _reason(
                        {"seed_id": r.seed_id, "share": r.share, "is_anchor": r.is_anchor}, names
                    )
                    for r in c.reasons
                ],
            }
            for c in cands
        ],
    }


def _list_out(db: Session, lst: GeneratedList) -> dict:
    items = db.scalars(
        select(ListItem).where(ListItem.list_id == lst.id).order_by(ListItem.position)
    ).all()
    ids = {i.artist_id for i in items} | {r["seed_id"] for i in items for r in i.reasons}
    names = _names(db, ids)
    metas = {
        m.track_id: m
        for m in db.scalars(
            select(UserTrackMeta).where(
                UserTrackMeta.user_id == lst.user_id,
                UserTrackMeta.track_id.in_([i.track_id for i in items if i.track_id]),
            )
        )
    }
    return {
        "id": lst.id,
        "created_at": lst.created_at.isoformat(),
        "algo_version": lst.algo_version,
        "candidate_algo_version": lst.candidate_algo_version,
        "profile_version": lst.profile_version,
        "graph_version": lst.graph_version,
        "params": lst.params,
        "items": [
            {
                "position": i.position,
                "artist_id": i.artist_id,
                "name": names.get(i.artist_id),
                "track_id": i.track_id,
                "title": metas[i.track_id].title if i.track_id in metas else None,
                "score": round(i.score, 6),
                "reasons": [_reason(r, names) for r in i.reasons],
            }
            for i in items
        ],
    }


@lists_router.post("/generate", status_code=201)
def generate(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: RecommendSettings = Depends(get_recommend_settings),
    pcfg: ProfileSettings = Depends(get_profile_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    try:
        lst = generate_list(db, user.id, datetime.now(UTC), cfg, pcfg, gcfg)
    except NoProfile:
        raise HTTPException(404, "Henüz profil üretilmedi") from None
    except NoGraph:
        raise HTTPException(409, "Grafik henüz kurulmadı") from None
    return _list_out(db, lst)


@lists_router.get("/{list_id}")
def get_list(
    list_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    lst = db.scalar(
        select(GeneratedList).where(GeneratedList.id == list_id, GeneratedList.user_id == user.id)
    )
    if lst is None:
        raise HTTPException(404, "Liste yok")
    return _list_out(db, lst)


class FeedbackIn(BaseModel):
    kind: Literal["wrong_reason"] = "wrong_reason"
    seed_id: int | None = None


@lists_router.post("/{list_id}/items/{position}/feedback", status_code=201)
def item_feedback(
    list_id: int, position: int, body: FeedbackIn,
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> dict:
    """Gerekçe itirazı: yalnızca olay kaydı (algoritmaya etkisi Faz 5)."""
    item = db.scalar(
        select(ListItem)
        .join(GeneratedList, GeneratedList.id == ListItem.list_id)
        .where(
            ListItem.list_id == list_id, ListItem.position == position,
            GeneratedList.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(404, "Liste öğesi yok")
    if body.seed_id is not None and body.seed_id not in {r["seed_id"] for r in item.reasons}:
        raise HTTPException(422, "Bu çapa öğenin gerekçesinde yok")
    ev = ListFeedback(
        user_id=user.id, list_id=list_id, position=position, seed_id=body.seed_id, kind=body.kind
    )
    db.add(ev)
    db.commit()
    return {"id": ev.id, "list": list_id, "position": position, "seed_id": ev.seed_id,
            "kind": ev.kind}
