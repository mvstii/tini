"""Zenginleştirme işi: sanatçısı çözülmemiş parçaları MusicBrainz'den eşler.

CLI: python -m app.jobs.enrich [--limit N]
"""
import argparse
import logging

import httpx
from sqlalchemy.orm import Session

from app.catalog.resolve import resolve_pending
from app.config import get_graph_settings, get_settings
from app.db import make_engine
from app.sources.http import SourceClient
from app.sources.musicbrainz import MusicBrainzClient

log = logging.getLogger("tini.enrich")


def make_musicbrainz(client: httpx.Client) -> MusicBrainzClient:
    contact = get_settings().musicbrainz_contact
    if not contact:
        raise RuntimeError("MUSICBRAINZ_CONTACT tanımlı değil")
    cfg = get_graph_settings()
    http = SourceClient.from_settings(
        client, cfg, user_agent=f"Tini/0.1 ( {contact} )",
        min_interval=cfg.musicbrainz_min_interval_seconds,
    )
    return MusicBrainzClient(http, cfg.musicbrainz_base_url)


def run(limit: int = 100) -> dict[str, int]:
    cfg = get_graph_settings()
    engine = make_engine()
    with httpx.Client(timeout=20) as client, Session(engine) as db:
        counts = resolve_pending(db, make_musicbrainz(client), cfg, limit=limit)
    log.info("enrich: %s", counts)
    return counts


def run_background(limit: int = 100) -> None:
    """BackgroundTasks için: hata isteği etkilemez, yalnızca loglanır."""
    try:
        run(limit)
    except Exception:  # noqa: BLE001
        log.exception("enrich başarısız")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    print(run(ap.parse_args().limit))
