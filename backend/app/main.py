from fastapi import FastAPI

app = FastAPI(title="Tını")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
