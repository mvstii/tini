"""Hesabı ve tüm kişisel veriyi siler: python -m app.jobs.delete_user e-posta [--yes]

--yes olmadan yalnızca neyin silineceğini söyler. Kişisel tabloların hepsi users'a
ON DELETE CASCADE ile bağlıdır; paylaşılan katalog/grafik verisine dokunulmaz.
"""
import argparse

from sqlalchemy import select

from app.db import make_session_factory
from app.models import User


def delete_user(db, email: str) -> bool:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        return False
    db.delete(user)
    db.flush()
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("--yes", action="store_true", help="gerçekten sil")
    args = ap.parse_args()
    with make_session_factory()() as db:
        if not args.yes:
            found = db.scalar(select(User.id).where(User.email == args.email))
            print("Bulundu, --yes ile silinir." if found else "Kullanıcı yok.")
            return
        if not delete_user(db, args.email):
            print("Kullanıcı yok.")
            return
        db.commit()
    print("Silindi.")


if __name__ == "__main__":
    main()
