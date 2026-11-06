"""Sanatçı tür etiketleri: normalleştirme (saf) ve toplu çekme."""
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import GraphSettings
from app.models import Artist, ArtistTag, ArtistTagFetch
from app.sources.lastfm import LastfmClient
from app.sources.musicbrainz import MusicBrainzClient


def normalize_tags(
    raw: Iterable[tuple[str, int]], *, relative: bool, min_weight: int, max_n: int
) -> list[tuple[str, int]]:
    """(etiket, ham oy) → (etiket, 0–100 ağırlık).

    `relative`: en çok oyluya göre ölçekle (MusicBrainz
    sayıları mutlak; Last.fm zaten 0–100). Eşiğin altı atılır, en çok `max_n` etiket kalır."""
    items = [(t[:64], max(int(c), 0)) for t, c in raw if t]
    top = max((c for _, c in items), default=0)
    if relative:
        items = [(t, round(100 * c / top) if top else 0) for t, c in items]
    items = [(t, min(c, 100)) for t, c in items if c >= min_weight]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return items[:max_n]


def load_genres(db: Session, artist_ids: Iterable[int]) -> dict[int, str]:
    """artist_id -> ana tür (yalnız etiketi olan ve bir türe eşlenebilen sanatçılar)."""
    from app.recommend.genres import main_genre

    by_artist: dict[int, list[tuple[str, int]]] = {}
    for aid, tag, weight in db.execute(
        select(ArtistTag.artist_id, ArtistTag.tag, ArtistTag.weight).where(
            ArtistTag.artist_id.in_(list(artist_ids))
        )
    ):
        by_artist.setdefault(aid, []).append((tag, weight))
    genres = {aid: main_genre(t) for aid, t in by_artist.items()}
    return {aid: g for aid, g in genres.items() if g is not None}


def fetch_artist_tags(
    db: Session, mb: MusicBrainzClient, lfm: LastfmClient | None, cfg: GraphSettings, limit: int
) -> dict[str, int]:
    """Henüz denenmemiş sanatçılar için etiket çeker: önce MusicBrainz, boşsa Last.fm. Etiketsiz de
    olsa deneme kaydedilir (bir daha sorulmaz)."""
    done = select(ArtistTagFetch.artist_id)
    rows = db.execute(
        select(Artist.id, Artist.mbid, Artist.name)
        .where(Artist.id.not_in(done), (Artist.mbid.is_not(None)) | (Artist.name.is_not(None)))
        .order_by(Artist.id)
        .limit(limit)
    ).all()
    stats = {"tried": 0, "musicbrainz": 0, "lastfm": 0, "none": 0}
    for aid, mbid, name in rows:
        tags: list[tuple[str, int]] = []
        source = ""
        if mbid is not None:
            tags = normalize_tags(
                mb.artist_tags(mbid), relative=True,
                min_weight=cfg.tag_min_weight, max_n=cfg.tag_max_per_artist,
            )
            source = "musicbrainz"
        if not tags and lfm is not None:
            tags = normalize_tags(
                lfm.get_top_tags(name=None if mbid else name, mbid=mbid), relative=False,
                min_weight=cfg.tag_min_weight, max_n=cfg.tag_max_per_artist,
            )
            source = "lastfm"
        stats["tried"] += 1
        if tags:
            stats[source] += 1
            db.execute(
                insert(ArtistTag)
                .values([
                    {"artist_id": aid, "tag": t, "weight": w, "source": source} for t, w in tags
                ])
                .on_conflict_do_nothing()
            )
        else:
            stats["none"] += 1
        db.execute(
            insert(ArtistTagFetch)
            .values(artist_id=aid, found=bool(tags))
            .on_conflict_do_nothing()
        )
        db.commit()
    return stats
