"""Salt okunur tanı: MusicBrainz sanatçı etiketlerinin kapsamı (tür planının 1. adımı).

CLI:
  python -m app.jobs.tag_coverage [--n 60]

MBID'li rastgele (sabit tohum) n sanatçı için etiketleri çeker, kaçında etiket bulunduğunu ve en
sık etiketleri yazar. Veritabanına yazmaz.
"""
import argparse
from collections import Counter

import httpx
from sqlalchemy import Text, func, select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.jobs.enrich import make_lastfm, make_musicbrainz
from app.models import Artist


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    args = ap.parse_args()
    with Session(make_engine()) as db, httpx.Client(timeout=30) as client:
        rows = db.execute(
            select(Artist.mbid, Artist.name)
            .where(Artist.mbid.is_not(None))
            .order_by(func.md5(Artist.mbid.cast(Text)))
            .limit(args.n)
        ).all()
        mb = make_musicbrainz(client)
        lfm = make_lastfm(client)
        top: Counter = Counter()
        hit = lfm_hit = 0
        for mbid, name in rows:
            tags = mb.artist_tags(mbid)
            if tags:
                hit += 1
            elif lfm is not None:
                tags = [(t, c) for t, c in lfm.get_top_tags(mbid=mbid) if c >= 20]
                lfm_hit += bool(tags)
            top.update(t for t, _ in tags[:5])
            print(f"{name}: {[t for t, _ in tags[:5]]}")
        print(f"\nMusicBrainz etiketli: {hit}/{len(rows)}; Last.fm ile eklenen: {lfm_hit}")
        print("En sık:", top.most_common(25))


if __name__ == "__main__":
    main()
