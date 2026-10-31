"""Yayın tespiti işi: takip edilen (MBID'li) sanatçıların yeni yayınlarını MusicBrainz'den çeker.

CLI: python -m app.jobs.detect_releases
"""
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.config import get_releases_settings
from app.db import make_engine
from app.jobs.enrich import make_musicbrainz
from app.releases.service import DetectResult, detect_releases

log = logging.getLogger("tini.releases")


def run() -> DetectResult:
    with httpx.Client(timeout=30) as client, Session(make_engine()) as db:
        res = detect_releases(
            db, make_musicbrainz(client), get_releases_settings(), datetime.now(UTC)
        )
    log.info("detect_releases: %s", res)
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
