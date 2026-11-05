import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.artwork import router as artwork_router
from app.auth import router as auth_router
from app.config import get_settings
from app.connect import router as connect_router
from app.feedback import router as feedback_router
from app.graph.api import router as graph_router
from app.graph.scheduler import lifespan as graph_lifespan
from app.library import router as library_router
from app.preview import router as preview_router
from app.profile.api import profile_router
from app.profile.api import router as votes_router
from app.recommend.api import lists_router
from app.recommend.api import router as recommend_router
from app.releases.api import router as releases_router
from app.releases.scheduler import lifespan as releases_lifespan
from app.requestlog import install as install_request_log
from app.tracks import comments_router, later_router, search_router

logging.getLogger("tini.request").setLevel(logging.INFO)
if not logging.getLogger("tini.request").handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logging.getLogger("tini.request").addHandler(_h)

def docs_urls(app_env: str) -> dict[str, str | None]:
    """Canlıda (prod) API şeması ve etkileşimli dokümanlar kapalıdır."""
    if app_env == "prod":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with releases_lifespan(app), graph_lifespan(app):
        yield


app = FastAPI(title="Tını", lifespan=lifespan, **docs_urls(get_settings().app_env))
install_request_log(app)
app.include_router(votes_router)
app.include_router(profile_router)
app.include_router(recommend_router)
app.include_router(lists_router)
app.include_router(releases_router)
app.include_router(graph_router)
app.include_router(auth_router)
app.include_router(connect_router)
app.include_router(library_router)
app.include_router(feedback_router)
app.include_router(artwork_router)
app.include_router(preview_router)
app.include_router(search_router)
app.include_router(later_router)
app.include_router(comments_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
