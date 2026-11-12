"""Geçici, salt okunur tanı (commitlenmez): kullanıcı için hazır kart sayıları."""
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.models import GenreSeed, ListenLater, Track, User, UserTrackLink, UserTrackMeta, VoteEvent

email = sys.argv[1]
from app.config import get_settings
print("bağlanılan host:", get_settings().database_url.split("@")[-1].split("/")[0])
now = datetime.now(UTC)
with Session(make_engine()) as db:
    u = db.scalar(select(User).where(User.email == email))
    voted = set(db.scalars(select(VoteEvent.track_id).where(VoteEvent.user_id == u.id)))
    later = set(db.scalars(select(ListenLater.track_id).where(ListenLater.user_id == u.id)))
    fresh = set(db.scalars(select(UserTrackMeta.track_id).where(
        UserTrackMeta.user_id == u.id, UserTrackMeta.expires_at > now)))
    allmeta = db.scalar(select(func.count()).select_from(UserTrackMeta)
                        .where(UserTrackMeta.user_id == u.id))
    seeds = set(db.scalars(select(GenreSeed.track_id)))
    links = db.scalar(select(func.count()).select_from(UserTrackLink)
                      .where(UserTrackLink.user_id == u.id))
    from app.models import ServiceConnection
    print("son oy:", db.scalar(select(func.max(VoteEvent.created_at))
                                .where(VoteEvent.user_id == u.id)))
    print("son meta bitişi:", db.scalar(select(func.max(UserTrackMeta.expires_at))
                                        .where(UserTrackMeta.user_id == u.id)))
    print("servis bağlantısı:", list(db.scalars(select(ServiceConnection.service)
                                                .where(ServiceConnection.user_id == u.id))))
    print("şimdi:", now)
    print("oylanan:", len(voted), "| sonra dinle:", len(later))
    print("kütüphane bağlantısı:", links)
    print("meta toplam:", allmeta, "| süresi dolmamış:", len(fresh))
    print("süresi dolmamış ve oylanmamış:", len(fresh - voted - later))
    print("omurga parça sayısı:", len(seeds))
    print("hazır omurga kartı (oylanmamış):", len((fresh & seeds) - voted - later))
