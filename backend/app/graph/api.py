"""GET /graph/neighborhood: kullanıcının kütüphanesindeki bir parçanın sanatçı komşuluğu.

Yanıtta yalnızca paylaşılan kanonik sanatçı adı ve türetilmiş skor bulunur (Spotify metni yok).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GraphSettings, get_graph_settings
from app.deps import current_user, get_db
from app.graph.neighborhood import Neighbor, neighborhood
from app.graph.service import get_matrix
from app.models import Artist, Track, User, UserTrackArtist, UserTrackLink

router = APIRouter(prefix="/graph")


def anchor_artist_id(db: Session, user_id, track_id: int) -> int | None:
    """Kullanıcının kütüphanesindeki parçanın sanatçısı (kademe A, yoksa kullanıcıya özel B)."""
    owned = db.scalar(
        select(UserTrackLink.track_id)
        .where(UserTrackLink.user_id == user_id, UserTrackLink.track_id == track_id)
        .limit(1)
    )
    if owned is None:
        return None
    artist_id = db.scalar(select(Track.artist_id).where(Track.id == track_id))
    if artist_id is not None:
        return artist_id
    return db.scalar(
        select(UserTrackArtist.artist_id).where(
            UserTrackArtist.user_id == user_id, UserTrackArtist.track_id == track_id
        )
    )


@router.get("/neighborhood")
def get_neighborhood(
    track: int,
    depth: int = Query(2, ge=1),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cfg: GraphSettings = Depends(get_graph_settings),
) -> dict:
    anchor = anchor_artist_id(db, user.id, track)
    if anchor is None:
        raise HTTPException(404, "Parça kütüphanede yok veya sanatçısı henüz çözülmedi")
    built = get_matrix(db, cfg)
    if built is None:
        raise HTTPException(503, "Benzerlik grafiği henüz hazır değil")
    version, gm = built
    hood = neighborhood(gm, anchor, depth, cfg)
    if hood is None:
        raise HTTPException(404, "Sanatçı benzerlik grafiğinde yok")

    def ids(ns: list[Neighbor]) -> set[int]:
        return {n.artist_id for n in ns} | {n.via for n in ns if n.via is not None}

    need = {anchor} | ids(hood.depth1) | ids(hood.depth2)
    names = dict(db.execute(select(Artist.id, Artist.name).where(Artist.id.in_(need))).all())

    def ref(i: int) -> dict:
        return {"artist_id": i, "name": names.get(i)}

    def row(n: Neighbor) -> dict:
        out = {**ref(n.artist_id), "score": round(n.score, 6)}
        if n.via is not None:
            out["via"] = ref(n.via)
        return out

    return {
        "algo_version": cfg.graph_algo_version,
        "snapshot": version,
        "anchor": ref(anchor),
        "depth1": [row(n) for n in hood.depth1],
        "depth2": [row(n) for n in hood.depth2],
    }
