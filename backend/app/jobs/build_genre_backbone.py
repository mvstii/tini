"""Tür omurgasını kurar (paylaşılan katalog; Spotify verisi kullanılmaz).

CLI: python -m app.jobs.build_genre_backbone [--genre rap|trap|...] [--limit N]
         [--expand-limit N] [--report]
Bilgisayardan hedef veritabanına (Neon) çalışır; canlı sunucuda koşmaz. Tekrar çalıştırılabilir
(kaydı olan sanatçı bir daha sorulmaz). Gerekli ortam: LISTENBRAINZ_TOKEN, MUSICBRAINZ_CONTACT.
"""
import argparse
import logging

import httpx
from sqlalchemy.orm import Session

from app.catalog.backbone import report, run_backbone
from app.config import get_graph_settings
from app.db import make_engine
from app.jobs.enrich import _quiet_http_logs, make_lastfm, make_listenbrainz, make_musicbrainz
from app.models import GenreSeed


def run(
    selector: str | None = None, limit: int | None = None, expand_limit: int = 0
) -> dict:
    _quiet_http_logs()
    cfg = get_graph_settings()
    with httpx.Client(timeout=30) as client, Session(make_engine()) as db:
        stats = run_backbone(
            db, make_listenbrainz(client), make_musicbrainz(client), cfg,
            selector=selector, limit=limit,
        )
        out: dict = {"backbone": stats.as_dict()}
        if expand_limit > 0:
            lfm = make_lastfm(client)
            if lfm is None:
                raise RuntimeError("LASTFM_API_KEY tanımlı değil")
            from sqlalchemy import select

            from app.graph.expand import expand

            anchors = sorted(set(db.scalars(select(GenreSeed.artist_id)).all()))
            out["expand"] = expand(db, lfm, cfg, limit=expand_limit, depth=1, anchors=anchors)
        out["report"] = report(db)
        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--genre", default=None, help="alt tür, ana tür ya da boş (hepsi)")
    ap.add_argument("--limit", type=int, default=None, help="bu koşuda en çok yeni sanatçı")
    ap.add_argument("--expand-limit", type=int, default=0, help="Last.fm 1 adım genişleme çekimi")
    ap.add_argument("--report", action="store_true", help="yalnızca rapor yazdır")
    a = ap.parse_args()
    if a.report:
        with Session(make_engine()) as db:
            print(report(db))
    else:
        print(run(a.genre, a.limit, a.expand_limit))
