"""Faz 3 kapısı için oy girişi: CSV dışa aktar, doldur, içe aktar (mobil oylama Faz 4'te).

CLI:
  python -m app.jobs.votes_csv export EPOSTA DOSYA [--count 80] [--seed 0]
  python -m app.jobs.votes_csv import EPOSTA DOSYA

Dışa aktarma, sanatçısı çözülmüş parçalardan tohumlu rastgele bir örnek yazar (başlık ve sanatçı
kullanıcıya özel önbellekten gelir; dosya yerel kalır, repoya girmez). `oy` sütununa 1–6 yazılır;
boş satırlar atlanır. İçe aktarma her dolu satırı yeni bir oy olayı olarak ekler.
"""
import argparse
import csv
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.models import Track, User, UserTrackLink, UserTrackMeta, VoteEvent

FIELDS = ["track_id", "sanatci", "baslik", "oy"]


def _user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise SystemExit(f"Kullanıcı yok: {email}")
    return user


def export_rows(db: Session, email: str, count: int, seed: int) -> list[dict]:
    user = _user(db, email)
    rows = db.execute(
        select(Track.id, UserTrackMeta.artist_names, UserTrackMeta.title)
        .join(UserTrackLink, UserTrackLink.track_id == Track.id)
        .join(
            UserTrackMeta,
            (UserTrackMeta.track_id == Track.id) & (UserTrackMeta.user_id == user.id),
        )
        .where(UserTrackLink.user_id == user.id, Track.artist_id.is_not(None))
        .order_by(Track.id)
    ).all()
    uniq = list({r[0]: r for r in rows}.values())
    picked = random.Random(seed).sample(uniq, min(count, len(uniq)))
    picked.sort(key=lambda r: (", ".join(r[1]).lower(), r[2].lower()))
    return [
        {"track_id": t, "sanatci": ", ".join(names), "baslik": title, "oy": ""}
        for t, names, title in picked
    ]


def import_votes(db: Session, email: str, path: str) -> int:
    user = _user(db, email)
    owned = set(
        db.scalars(select(UserTrackLink.track_id).where(UserTrackLink.user_id == user.id))
    )
    n = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            raw = (row.get("oy") or "").strip()
            if not raw:
                continue
            vote, track = int(raw), int(row["track_id"])
            if not 1 <= vote <= 6:
                raise SystemExit(f"Geçersiz oy ({raw}) — track_id {track}")
            if track not in owned:
                raise SystemExit(f"Parça kütüphanede yok: {track}")
            db.add(VoteEvent(user_id=user.id, track_id=track, vote=vote))
            n += 1
    db.commit()
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["export", "import"])
    ap.add_argument("email")
    ap.add_argument("path")
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    with Session(make_engine()) as session:
        if args.action == "export":
            data = export_rows(session, args.email, args.count, args.seed)
            with open(args.path, "w", newline="", encoding="utf-8-sig") as out:
                w = csv.DictWriter(out, fieldnames=FIELDS)
                w.writeheader()
                w.writerows(data)
            print(f"{len(data)} parça yazıldı: {args.path}")
        else:
            print(f"{import_votes(session, args.email, args.path)} oy eklendi")
