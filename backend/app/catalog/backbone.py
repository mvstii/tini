"""Tür omurgası (PR-4): kullanıcıdan bağımsız alt tür → temsilci parça havuzu kurar.

Akış (alt tür başına, bant başına): ListenBrainz etiket havuzu → sanatçılar → sanatçının en çok
dinlenen K kaydı → ISRC (ListenBrainz, yoksa MusicBrainz) → `Track` + `TrackPopularity` +
`GenreSeed`. Devam ettirilebilir: kaydı olan sanatçı bir daha sorulmaz. Spotify verisi yoktur.
"""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.catalog.resolve import upsert_artist
from app.config import GraphSettings
from app.models import Artist, GenreSeed, Track, TrackPopularity
from app.recommend.genres import SUB_GENRES, main_of
from app.sources.http import SourceError
from app.sources.listenbrainz import LbRecording, ListenBrainzClient
from app.sources.musicbrainz import MusicBrainzClient

BANDS = ("top", "mid", "tail")
SOURCE = "listenbrainz"


def band_windows(cfg: GraphSettings) -> dict[str, tuple[int, int]]:
    """Bant → (pop_begin, pop_end). ListenBrainz'de 0 en çok dinlenen uçtur."""
    return {
        "top": (0, cfg.backbone_top_end),
        "mid": (cfg.backbone_top_end, cfg.backbone_mid_end),
        "tail": (cfg.backbone_mid_end, 100),
    }


def band_for_percentile(pct: float, cfg: GraphSettings) -> str:
    """Dinlenme yüzdeliği (0 = en çok dinlenen) → bant."""
    if pct < cfg.backbone_top_end:
        return "top"
    if pct < cfg.backbone_mid_end:
        return "mid"
    return "tail"


def split_quota(cap: int) -> dict[str, int]:
    """Alt tür sanatçı üst sınırını bantlara böler; artan sanatçılar sırayla top, mid, tail'e."""
    base, extra = divmod(max(cap, 0), len(BANDS))
    return {b: base + (1 if i < extra else 0) for i, b in enumerate(BANDS)}


def pick_artists(
    pool: dict[str, LbRecording], skip: set[str], quota: int
) -> list[tuple[str, str | None]]:
    """Havuzdan (sanatçı MBID, ad) — sıra korunur, `skip` ve yinelenenler atlanır, en çok quota."""
    out: list[tuple[str, str | None]] = []
    seen = set(skip)
    for rec in pool.values():
        a = rec.artist_mbid
        if not a or a in seen:
            continue
        seen.add(a)
        out.append((a, rec.artist_name))
        if len(out) >= quota:
            break
    return out


@dataclass
class BackboneStats:
    artists: int = 0
    recordings: int = 0
    with_isrc: int = 0
    seeds: int = 0
    errors: int = 0
    per_sub: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        ratio = self.with_isrc / self.recordings if self.recordings else None
        return {
            "artists": self.artists, "recordings": self.recordings, "with_isrc": self.with_isrc,
            "isrc_ratio": ratio, "seeds": self.seeds, "errors": self.errors,
            "per_sub": dict(self.per_sub),
        }


def _resolve(lb: ListenBrainzClient, mbids: list[str], batch: int) -> dict[str, LbRecording]:
    out: dict[str, LbRecording] = {}
    for i in range(0, len(mbids), batch):
        out.update(lb.recordings(mbids[i : i + batch]))
    return out


def _upsert_track(db: Session, isrc: str, rec_mbid: str, artist_id: int) -> int:
    row = db.execute(select(Track.id, Track.artist_id).where(Track.isrc == isrc)).first()
    if row is None:
        return db.execute(
            insert(Track)
            .values(isrc=isrc, mbid=uuid.UUID(rec_mbid), artist_id=artist_id)
            .returning(Track.id)
        ).scalar_one()
    if row.artist_id is None:
        db.execute(Track.__table__.update().where(Track.id == row.id).values(artist_id=artist_id))
    return row.id


def _store_seed(
    db: Session, *, sub: str, track_id: int, artist_id: int, band: str, listens: int
) -> bool:
    db.execute(
        insert(TrackPopularity)
        .values(track_id=track_id, band=band, listens=listens)
        .on_conflict_do_update(
            index_elements=["track_id"],
            set_={"band": band, "listens": listens, "fetched_at": func.now()},
        )
    )
    res = db.execute(
        insert(GenreSeed)
        .values(
            sub_genre=sub, track_id=track_id, main_genre=main_of(sub), artist_id=artist_id,
            band=band, source=SOURCE,
        )
        .on_conflict_do_nothing(index_elements=["sub_genre", "track_id"])
    )
    return bool(res.rowcount)


def _artist_seeds(
    db: Session, lb: ListenBrainzClient, mb: MusicBrainzClient | None, cfg: GraphSettings,
    sub: str, band: str, artist_mbid: str, name: str | None, stats: BackboneStats,
) -> bool:
    """Sanatçının en çok dinlenen K kaydını yazar; ISRC'li kayıt yoksa hiçbir şey yazmaz."""
    top = lb.top_recordings(artist_mbid, cfg.backbone_top_k)
    if not top:
        return False
    meta = _resolve(lb, [m for m, _ in top], cfg.backbone_meta_batch)
    seeds: list[tuple[str, str, int]] = []  # (isrc, kayıt mbid, dinlenme)
    for rec_mbid, listens in top:
        stats.recordings += 1
        isrcs = list(meta[rec_mbid].isrcs) if rec_mbid in meta else []
        if not isrcs and mb is not None:
            isrcs = mb.recording_isrcs(rec_mbid)
        if isrcs:
            stats.with_isrc += 1
            seeds.append((isrcs[0], rec_mbid, listens))
    if not seeds:
        return False  # ISRC'siz sanatçı yazılmaz (PR-4b boşluğu); sonraki koşuda yeniden denenir
    fallback = next((r.artist_name for r in meta.values() if r.artist_name), None)
    artist_id = upsert_artist(db, uuid.UUID(artist_mbid), name or fallback or artist_mbid)
    for isrc, rec_mbid, listens in seeds:
        track_id = _upsert_track(db, isrc, rec_mbid, artist_id)
        if _store_seed(
            db, sub=sub, track_id=track_id, artist_id=artist_id, band=band, listens=listens
        ):
            stats.seeds += 1
    stats.artists += 1
    stats.per_sub[sub] = stats.per_sub.get(sub, 0) + 1
    return True


def build_sub_genre(
    db: Session, lb: ListenBrainzClient, mb: MusicBrainzClient | None, cfg: GraphSettings,
    sub: str, *, budget: int | None = None, stats: BackboneStats | None = None,
) -> BackboneStats:
    """Bir alt türü bantlara bölerek kurar. `budget`: bu çağrıda en çok kaç yeni sanatçı işlenir."""
    stats = stats if stats is not None else BackboneStats()
    started = stats.artists
    tag = SUB_GENRES[sub][1][0]
    done = {
        (str(m), b)
        for m, b in db.execute(
            select(Artist.mbid, GenreSeed.band)
            .join(GenreSeed, GenreSeed.artist_id == Artist.id)
            .where(GenreSeed.sub_genre == sub, Artist.mbid.is_not(None))
            .distinct()
        )
    }
    done_artists = {m for m, _ in done}
    quotas = split_quota(cfg.backbone_artists_per_sub_genre_cap)
    for band, (begin, end) in band_windows(cfg).items():
        need = quotas[band] - sum(1 for _, b in done if b == band)
        if budget is not None:
            need = min(need, budget - (stats.artists - started))
        if need <= 0:
            continue
        try:
            mbids = lb.radio_tags(tag, cfg.backbone_pool_count, begin, end)
            pool = _resolve(lb, mbids, cfg.backbone_meta_batch)
        except SourceError:
            stats.errors += 1
            continue
        for amb, name in pick_artists(pool, done_artists, need):
            try:
                _artist_seeds(db, lb, mb, cfg, sub, band, amb, name, stats)
                db.commit()
            except SourceError:
                db.rollback()
                stats.errors += 1
                continue
            done_artists.add(amb)
    return stats


def sub_genres_for(selector: str | None) -> list[str]:
    """`--genre` seçicisi: alt tür kısaltması, ana tür (altındaki tüm alt türler) ya da hepsi."""
    if selector is None:
        return list(SUB_GENRES)
    if selector in SUB_GENRES:
        return [selector]
    subs = [s for s, (main, _) in SUB_GENRES.items() if main == selector]
    if not subs:
        raise ValueError(f"bilinmeyen tür: {selector}")
    return subs


def run_backbone(
    db: Session, lb: ListenBrainzClient, mb: MusicBrainzClient | None, cfg: GraphSettings,
    *, selector: str | None = None, limit: int | None = None,
) -> BackboneStats:
    """Seçilen alt türleri sırayla kurar; `limit` toplam yeni sanatçı üst sınırıdır."""
    stats = BackboneStats()
    for sub in sub_genres_for(selector):
        if limit is not None and stats.artists >= limit:
            break
        build_sub_genre(
            db, lb, mb, cfg, sub,
            budget=None if limit is None else limit - stats.artists, stats=stats,
        )
    return stats


def report(db: Session) -> dict:
    """Alt tür başına tohum/sanatçı sayıları ve veritabanı boyutu (staging raporu)."""
    rows = db.execute(
        select(
            GenreSeed.sub_genre, func.count(), func.count(func.distinct(GenreSeed.artist_id))
        ).group_by(GenreSeed.sub_genre)
    ).all()
    size = db.scalar(select(func.pg_database_size(func.current_database())))
    return {
        "per_sub": {s: {"seeds": n, "artists": a} for s, n, a in sorted(rows)},
        "sub_genres_with_data": len(rows),
        "sub_genres_total": len(SUB_GENRES),
        "below_15_artists": sorted(s for s, _, a in rows if a < 15),
        "db_size_bytes": size,
    }
