from fastapi import FastAPI

from app.auth import router as auth_router
from app.connect import router as connect_router
from app.graph.api import router as graph_router
from app.library import router as library_router
from app.profile.api import router as votes_router

app = FastAPI(title="Tını")
app.include_router(votes_router)
app.include_router(graph_router)
app.include_router(auth_router)
app.include_router(connect_router)
app.include_router(library_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
