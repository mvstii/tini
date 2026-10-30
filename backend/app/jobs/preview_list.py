"""Kapı için elle bakış: kullanıcının son profilinden listeyi üretir ve gerekçeleriyle yazdırır.

Listeyi kaydetmez. CLI: python -m app.jobs.preview_list EPOSTA [--size N]
"""
import argparse
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    get_graph_settings,
    get_profile_settings,
    get_recommend_settings,
)
from app.db import make_engine
from app.models import Artist, User
from app.recommend.select import select_mmr
from app.recommend.service import compute_candidates


def run(email: str, size: int | None = None) -> list[str]:
    cfg, pcfg, gcfg = get_recommend_settings(), get_profile_settings(), get_graph_settings()
    with Session(make_engine()) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Kullanıcı yok: {email}")
        sc = compute_candidates(db, user.id, datetime.now(UTC), cfg, pcfg, gcfg)
        chosen = select_mmr(sc.cands, sc.gm, size or cfg.list_size, cfg.mmr_lambda)
        ids = {c.artist_id for c in chosen} | {r.seed_id for c in chosen for r in c.reasons}
        names = dict(db.execute(select(Artist.id, Artist.name).where(Artist.id.in_(ids))).all())
    lines = [
        f"profil v{sc.profile.version} · grafik v{sc.graph_version} · "
        f"{len(sc.cands)} aday, {len(chosen)} seçildi"
    ]
    for pos, c in enumerate(chosen, start=1):
        why = ", ".join(
            f"{names.get(r.seed_id, r.seed_id)}{'★' if r.is_anchor else ''} %{r.share * 100:.0f}"
            for r in c.reasons
        )
        lines.append(f"{pos:>2}. {names.get(c.artist_id, c.artist_id)}  ({c.score:.4f})  ← {why}")
    return lines


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("--size", type=int)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolu (cp1254) ← ve ★ yazamaz
    print("\n".join(run(args.email, args.size)))
