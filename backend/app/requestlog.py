"""İstek günlüğü (Faz 6): her istek için tek satır JSON; üçüncü taraf hata servisi yok.

Alanlar: istek kimliği, yöntem, yol, durum, süre (ms), kullanıcı kimliği (varsa), aşama süreleri
(`stages`, varsa; `server_timing_enabled` bayrağı).
İstek gövdesi ve başlıklar yazılmaz (token, parola, kişisel veri sızmasın).
"""
import json
import logging
import time
import uuid

from fastapi import FastAPI, Request

from app.config import get_settings
from app.jobs.worker import touch

log = logging.getLogger("tini.request")


def _stages(request: Request):
    """Uç noktanın `request.state.stages` altına koyduğu ölçümler (bayrak kapalıysa yok)."""
    st = getattr(request.state, "stages", None)
    return st if st is not None and st.as_dict() and get_settings().server_timing_enabled else None


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        touch()
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-Id"] = rid
            stages = _stages(request)
            if stages:
                response.headers["Server-Timing"] = stages.header()
            return response
        except Exception:
            log.exception("unhandled request_id=%s", rid)
            raise
        finally:
            uid = getattr(request.state, "user_id", None)
            line = {
                "request_id": rid, "method": request.method, "path": request.url.path,
                "status": status, "ms": round((time.perf_counter() - t0) * 1000),
                "user": str(uid) if uid else None,
            }
            stages = _stages(request)
            if stages:
                line["stages"] = stages.as_dict()
            log.log(logging.ERROR if status >= 500 else logging.INFO, json.dumps(line))
