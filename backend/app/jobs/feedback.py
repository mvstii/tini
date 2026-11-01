"""Geri bildirimleri listeler (salt okuma): python -m app.jobs.feedback [--kind bug]"""
import argparse

from sqlalchemy import select

from app.db import make_session_factory
from app.models import AppFeedback, User


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["bug", "idea", "other"])
    args = ap.parse_args()
    q = (
        select(AppFeedback, User.email)
        .join(User, User.id == AppFeedback.user_id)
        .order_by(AppFeedback.created_at.desc())
    )
    if args.kind:
        q = q.where(AppFeedback.kind == args.kind)
    with make_session_factory()() as db:
        rows = db.execute(q).all()
    for f, email in rows:
        print(f"[{f.created_at:%Y-%m-%d %H:%M}] {f.kind:5} {email} · {f.screen} · v{f.app_version}")
        print(f"    {f.message}")
    print(f"{len(rows)} kayıt")


if __name__ == "__main__":
    main()
