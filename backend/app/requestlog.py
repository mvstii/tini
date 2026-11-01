"""İstek günlüğü (Faz 6): her istek için tek satır JSON; üçüncü taraf hata servisi yok.

Alanlar: istek kimliği, yöntem, yol, durum, süre (ms), kullanıcı kimliği (varsa).
İstek gövdesi ve başlıklar yazılmaz (token, parola, kişisel veri sızmasın).
"""
import json
import logging
import time
import uuid

from fastapi import FastAPI, Request

log = logging.getLogger("tini.request")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-Id"] = rid
            return response
        except Exception:
            log.exception("unhandled request_id=%s", rid)
            raise
        finally:
            uid = getattr(request.state, "user_id", None)
            log.log(
                logging.ERROR if status >= 500 else logging.INFO,
                json.dumps({
                    "request_id": rid, "method": request.method, "path": request.url.path,
                    "status": status, "ms": round((time.perf_counter() - t0) * 1000),
                    "user": str(uid) if uid else None,
                }),
            )
