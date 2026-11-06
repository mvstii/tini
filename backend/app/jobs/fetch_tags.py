"""Sanatçı tür etiketlerini çeker (paylaşılan katalog; Spotify verisi kullanılmaz).

CLI: python -m app.jobs.fetch_tags [--limit 200]   (tekrar çalıştırılabilir; denenenler atlanır)
"""
import argparse
import logging

import httpx
from sqlalchemy.orm import Session

from app.catalog.tags import fetch_artist_tags
from app.config import get_graph_settings
from app.db import make_engine
from app.jobs.enrich import make_lastfm, make_musicbrainz


def run(limit: int = 200) -> dict[str, int]:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    with httpx.Client(timeout=30) as client, Session(make_engine()) as db:
        return fetch_artist_tags(
            db, make_musicbrainz(client), make_lastfm(client), get_graph_settings(), limit
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    print(run(ap.parse_args().limit))
