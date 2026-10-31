from fastapi import FastAPI

from app.auth import router as auth_router
from app.connect import router as connect_router
from app.graph.api import router as graph_router
from app.library import router as library_router
from app.profile.api import profile_router
from app.profile.api import router as votes_router
from app.recommend.api import lists_router
from app.recommend.api import router as recommend_router
from app.releases.api import router as releases_router

app = FastAPI(title="Tını")
app.include_router(votes_router)
app.include_router(profile_router)
app.include_router(recommend_router)
app.include_router(lists_router)
app.include_router(releases_router)
app.include_router(graph_router)
app.include_router(auth_router)
app.include_router(connect_router)
app.include_router(library_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
