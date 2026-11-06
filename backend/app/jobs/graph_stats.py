"""Salt okunur tanı: sanatçı grafiğinin topluluk dağılımı (çeşitlilik planının 1. adımı).

CLI:
  python -m app.jobs.graph_stats [--k 12] [--email EPOSTA]

Grafiği SVD + KMeans ile k topluluğa böler; her topluluğun boyutunu ve en bağlantılı sanatçılarını
yazar. `--email` verilirse kullanıcının güncel oyu 4+ olan sanatçılarının topluluklara dağılımını da
gösterir. Veritabanına hiçbir şey yazmaz.
"""
import argparse
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_graph_settings
from app.db import make_engine
from app.graph.service import get_matrix
from app.models import Artist, Track, User, VoteEvent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--email")
    args = ap.parse_args()
    with Session(make_engine()) as db:
        built = get_matrix(db, get_graph_settings())
        if built is None:
            raise SystemExit("Grafik snapshot'ı yok")
        _, gm = built
        n = len(gm.node_ids)
        print(f"Düğüm: {n}, kenar: {gm.matrix.nnz // 2}")
        comps = max(2, min(32, n - 1))
        emb = normalize(TruncatedSVD(comps, random_state=0).fit_transform(gm.matrix))
        labels = KMeans(args.k, n_init=10, random_state=0).fit_predict(emb)
        deg = np.asarray(gm.matrix.sum(axis=1)).ravel()
        names = dict(db.execute(select(Artist.id, Artist.name)).all())
        liked: Counter = Counter()
        if args.email:
            user = db.scalar(select(User).where(User.email == args.email))
            if user is None:
                raise SystemExit("Kullanıcı yok")
            last: dict[int, int] = {}
            rows = db.execute(
                select(VoteEvent.track_id, VoteEvent.vote)
                .where(VoteEvent.user_id == user.id)
                .order_by(VoteEvent.id)
            ).all()
            for t, v in rows:
                last[t] = v
            pos_tracks = [t for t, v in last.items() if v >= 4]
            artists = {
                a
                for a in db.scalars(select(Track.artist_id).where(Track.id.in_(pos_tracks)))
                if a is not None
            }
            for a in artists:
                p = gm.position(a)
                if p is not None:
                    liked[int(labels[p])] += 1
            print(f"Sevdiğin sanatçılar (grafikte): {sum(liked.values())}")
        for c in sorted(range(args.k), key=lambda c: -int((labels == c).sum())):
            idx = np.where(labels == c)[0]
            top = idx[np.argsort(-deg[idx])[:6]]
            tops = ", ".join(str(names.get(int(gm.node_ids[i])) or "?") for i in top)
            mine = f" · senin: {liked[c]}" if args.email else ""
            print(f"[{c}] {len(idx)} sanatçı{mine} · {tops}")


if __name__ == "__main__":
    main()
