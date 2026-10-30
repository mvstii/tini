"""İşbirliği düğümlerini bulup artist_member tablosunu yeniden yazar (tekrar çalıştırılabilir).

CLI: python -m app.jobs.detect_collabs
"""
import sys

from sqlalchemy import delete, select, union
from sqlalchemy.orm import Session

from app.catalog.collab import detect_collabs
from app.db import make_engine
from app.models import Artist, ArtistEdge, ArtistMember


def run(db: Session) -> dict[int, list[int]]:
    artists = [(i, n) for i, n in db.execute(select(Artist.id, Artist.name)).all()]
    with_edges = set(
        db.scalars(union(select(ArtistEdge.src), select(ArtistEdge.dst)))
    )
    found = detect_collabs(artists, with_edges)
    db.execute(delete(ArtistMember))
    db.add_all(ArtistMember(collab_id=c, member_id=m) for c, ms in found.items() for m in ms)
    db.commit()
    return found


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    with Session(make_engine()) as session:
        res = run(session)
        names = dict(session.execute(select(Artist.id, Artist.name)).all())
    print(f"{len(res)} işbirliği düğümü")
    for c, ms in list(res.items())[:15]:
        print(f"  {names[c]} -> {', '.join(names[m] for m in ms)}")
