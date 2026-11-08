"""GET /artists/images: sanatçı portreleri (önbellekten, eksikler tembel doldurulur)."""
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends

from app.catalog.artist_images import fill_images
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
from app.models import User
from app.sources.deezer import DeezerClient
from app.sources.http import SourceClient

router = APIRouter(prefix="/artists")

MAX_IDS = 40


def get_fetcher(
    http: httpx.Client = Depends(get_http),
    cfg: ArtworkSettings = Depends(get_artwork_settings),
    gcfg: GraphSettings = Depends(get_graph_settings),
) -> Callable[[str], str | None]:
    contact = get_settings().musicbrainz_contact or "dev"
    src = SourceClient.from_settings(
        http,
        gcfg,
        user_agent=f"Tini/0.1 ( {contact} )",
        min_interval=cfg.deezer_min_interval_seconds,
        source="deezer",
    )
    return DeezerClient(src, cfg.deezer_base_url).artist_picture


@router.get("/images")
def images(
    ids: str,
    user: User = Depends(current_user),
    db=Depends(_get_db),
    fetch: Callable[[str], str | None] = Depends(get_fetcher),
    cfg: ArtworkSettings = Depends(get_artwork_settings),
) -> dict:
    """`ids` virgülle ayrılmış sanatçı kimlikleri. Dönen `pending` > 0 ise istemci tekrar sorar."""
    wanted = [int(p) for p in ids.split(",") if p.strip().isdigit()][:MAX_IDS]
    if not cfg.enabled:
        return {"images": {}, "pending": 0}
    known, pending = fill_images(db, wanted, fetch, cfg, datetime.now(UTC))
    return {"images": {str(k): v for k, v in known.items()}, "pending": pending}
