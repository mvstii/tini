"""Salt okunur tanı: ana tür dağılımı ve etiketleme durumu.

CLI: python -m app.jobs.genre_stats [--email EPOSTA]

Grafik düğümlerinin ana tür dağılımını, etiketsiz kalanları ve (verilirse) kullanıcının güncel oyu
4+ olan sanatçılarının tür dağılımını yazar. Veritabanına hiçbir şey yazmaz.
"""
import argparse
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.tags import load_genres
from app.config import get_graph_settings
from app.db import make_engine
from app.graph.service import get_matrix
from app.models import Artist, ArtistTagFetch, Track, User, VoteEvent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email")
    args = ap.parse_args()
    with Session(make_engine()) as db:
        total = db.scalar(select(func.count()).select_from(Artist))
        tried = db.scalar(select(func.count()).select_from(ArtistTagFetch))
        print(f"Sanatçı: {total}, etiket denenen: {tried}, kalan: {total - tried}")
        built = get_matrix(db, get_graph_settings())
        if built is None:
            raise SystemExit("Grafik snapshot'ı yok")
        nodes = built[1].node_ids.tolist()
        genres = load_genres(db, nodes)
        print(f"\nGrafik düğümü: {len(nodes)}, türü olan: {len(genres)}")
        for g, n in Counter(genres.values()).most_common():
            print(f"  {g:14s} {n}")
        if args.email:
            user = db.scalar(select(User).where(User.email == args.email))
            if user is None:
                raise SystemExit("Kullanıcı yok")
            last: dict[int, int] = {}
            for t, v in db.execute(
                select(VoteEvent.track_id, VoteEvent.vote)
                .where(VoteEvent.user_id == user.id).order_by(VoteEvent.id)
            ).all():
                last[t] = v
            pos = [t for t, v in last.items() if v >= 4]
            arts = {a for a in db.scalars(select(Track.artist_id).where(Track.id.in_(pos))) if a}
            ug = load_genres(db, arts)
            print(f"\nSenin 4+ sanatçın: {len(arts)}, türü olan: {len(ug)}")
            for g, n in Counter(ug.values()).most_common():
                print(f"  {g:14s} {n}")


if __name__ == "__main__":
    main()
