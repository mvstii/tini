"""GET /preview: parçanın 30 sn'lik önizleme URL'si, istek anında çözülür.

URL imzalı ve süreli olduğundan hiçbir yerde saklanmaz; ses dosyası da indirilmez (istemci yayın
olarak çalar). Kaynak Deezer olduğundan yalnızca kapalı testte kullanılır
(docs/ARCHITECTURE.md, "Kısa önizleme")."""
from collections.abc import Callable

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    ArtworkSettings,
    GraphSettings,
    get_artwork_settings,
    get_graph_settings,
    get_settings,
)
from app.connect import get_http
from app.deps import current_user
from app.deps import get_db as _get_db
from app.models import Artist, Track, User
from app.sources.deezer import DeezerClient
from app.sources.http import SourceClient, SourceError

router = APIRouter()


def get_deezer(
    http: httpx.Client = Depends(get_http),
    cfg: ArtworkSettings = Depends(get_artwork_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> DeezerClient:
    contact = get_settings().musicbrainz_contact or "dev"
    src = SourceClient.from_settings(
        http,
        gcfg,
        user_agent=f"Tini/0.1 ( {contact} )",
        min_interval=cfg.deezer_min_interval_seconds,
    )
    return DeezerClient(src, cfg.deezer_base_url)


def get_preview_fetcher(
    deezer: DeezerClient = Depends(get_deezer),
) -> Callable[[str | None, str | None], tuple[str, str] | None]:
    return deezer.track_preview


def get_preview_by_id(
    deezer: DeezerClient = Depends(get_deezer),
) -> Callable[[int], tuple[str, str] | None]:
    return deezer.track_preview_by_id


@router.get("/preview")
def preview(
    artist_id: int | None = None,
    track_id: int | None = None,
    deezer_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(_get_db),
    fetch: Callable[[str | None, str | None], tuple[str, str] | None] = Depends(
        get_preview_fetcher
    ),
    by_id: Callable[[int], tuple[str, str] | None] = Depends(get_preview_by_id),
    cfg: ArtworkSettings = Depends(get_artwork_settings),
) -> dict:
    """ISRC'li parça için önce ISRC, değilse sanatçı adıyla aranır. Bulunamazsa `url` null."""
    empty = {"url": None, "title": None}
    if not cfg.preview_enabled:
        return empty
    if deezer_id is not None:  # yeni çıkan parça: Deezer kimliğiyle doğrudan
        try:
            found = by_id(deezer_id)
        except SourceError:
            return empty
        return {"url": found[0], "title": found[1]} if found else empty
    isrc = db.scalar(select(Track.isrc).where(Track.id == track_id)) if track_id else None
    name = db.scalar(select(Artist.name).where(Artist.id == artist_id)) if artist_id else None
    if not isrc and not name:
        return empty
    try:
        found = fetch(isrc, name)
    except SourceError:
        return empty
    return {"url": found[0], "title": found[1]} if found else empty
