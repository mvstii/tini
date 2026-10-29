from fastapi import FastAPI

from app.auth import router as auth_router

app = FastAPI(title="Tını")
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
