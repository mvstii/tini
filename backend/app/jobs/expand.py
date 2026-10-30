"""Genişletme işi: kütüphane sanatçılarından Last.fm benzerlik kenarlarını çeker.

CLI: python -m app.jobs.expand [--limit N] [--depth D]
"""
import argparse
import logging

import httpx
from sqlalchemy.orm import Session

from app.config import get_graph_settings
from app.db import make_engine
from app.graph.expand import expand
from app.jobs.enrich import _quiet_http_logs, make_lastfm

log = logging.getLogger("tini.expand")


def run(limit: int = 100, depth: int | None = None) -> dict:
    _quiet_http_logs()
    cfg = get_graph_settings()
    with httpx.Client(timeout=20) as client, Session(make_engine()) as db:
        lfm = make_lastfm(client)
        if lfm is None:
            raise RuntimeError("LASTFM_API_KEY tanımlı değil")
        return expand(db, lfm, cfg, limit=limit, depth=depth)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--depth", type=int, default=None)
    args = ap.parse_args()
    print(run(args.limit, args.depth))
