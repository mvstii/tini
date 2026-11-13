"""Sanatçı portresi önbelleği: paylaşılan `artist_image` tablosu, tembel doldurma."""
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import ArtworkSettings
from app.models import Artist, ArtistImage
from app.sources.http import SourceError

# Kaynak sürümü: albüm kapağı yedeği gelmeden önce yazılmış "bulunamadı" kayıtları ("deezer")
# geçersiz sayılır ve bir kez yeniden denenir; bulunmuş URL'ler etkilenmez.
SOURCE = "deezer-2"


def cached_images(db: Session, ids: Iterable[int], now: datetime) -> dict[int, str | None]:
    """Süresi dolmamış kayıtlar: {sanatçı: url | None (bulunamadı)}; kaydı olmayan anahtar yok."""
    ids = list(ids)
    if not ids:
        return {}
    rows = db.execute(
        select(ArtistImage.artist_id, ArtistImage.url).where(
            ArtistImage.artist_id.in_(ids),
            ArtistImage.expires_at > now,
            ArtistImage.url.is_not(None) | (ArtistImage.source == SOURCE),
        )
    ).all()
    return dict(rows)


def fill_images(
    db: Session,
    ids: Iterable[int],
    fetch: Callable[[str], str | None],
    cfg: ArtworkSettings,
    now: datetime,
) -> tuple[dict[int, str | None], int]:
    """Eksik/süresi dolmuş sanatçılar için en çok `fill_limit` kaynak sorgusu yapar.

    Döner: (bilinen görseller, hâlâ eksik sayısı). Kaynak hata verirse dolum durur ve eksik
    olanlar sonraki çağrıya kalır; hata kaydı yazılmaz."""
    wanted = list(dict.fromkeys(ids))
    known = cached_images(db, wanted, now)
    missing = [i for i in wanted if i not in known]
    names = dict(db.execute(select(Artist.id, Artist.name).where(Artist.id.in_(missing))).all())
    done = 0
    for aid in missing:
        if done >= cfg.fill_limit:
            break
        name = names.get(aid)
        try:
            url = fetch(name) if name else None
        except SourceError:
            break
        days = cfg.ttl_days if url else cfg.miss_ttl_days
        row = {"artist_id": aid, "url": url, "source": SOURCE, "fetched_at": now,
               "expires_at": now + timedelta(days=days)}
        db.execute(insert(ArtistImage).values(**row).on_conflict_do_update(
            index_elements=["artist_id"], set_={k: v for k, v in row.items() if k != "artist_id"}
        ))
        known[aid] = url
        done += 1
    db.commit()
    return known, len([i for i in wanted if i not in known])
