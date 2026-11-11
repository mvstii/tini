"""Salt okunur tanı: kullanıcının oylanmamış kütüphane sanatçıları neden türsüz?

Sanatçıları dörde böler: (A) etiket çekme hiç denenmemiş, (B) denenmiş ama etiket yok,
(C) etiket var ama ana türe eşlenmiyor, (D) ana türü belli. Parça (kart) sayıları da verilir;
(C) için en sık eşlenmeyen etiketler yazılır. Dış çağrı yapmaz, veritabanına yazmaz.

CLI: python -m app.jobs.label_gap --email EPOSTA [--top 30]
"""
import argparse
from collections import Counter
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.models import (
    Artist,
    ArtistTag,
    ArtistTagFetch,
    FetchLog,
    Track,
    User,
    UserTrackArtist,
    UserTrackLink,
    VoteEvent,
)
from app.profile.track_artists import track_artists
from app.recommend.genres import main_genre

GROUPS = ("never_tried", "tried_no_tags", "tags_unmapped", "labeled")


def label_gap(
    track_artists: Sequence[int | None],
    attempted: set[int],
    tags: Mapping[int, Sequence[tuple[str, int]]],
    with_mbid: set[int],
    top: int = 30,
) -> dict:
    """`track_artists`: oylanmamış kütüphane parçalarının sanatçı kimlikleri (parça başına bir öğe;
    sanatçısı çözülmemiş parça None). Dönüş: grup başına sanatçı/parça/MBID'siz sanatçı sayısı,
    sanatçısız parça sayısı ve eşlenmeyen en sık etiketler."""
    per_artist = Counter(a for a in track_artists if a is not None)
    out = {g: {"artists": 0, "tracks": 0, "no_mbid": 0} for g in GROUPS}
    unmapped: Counter = Counter()
    for artist, n in per_artist.items():
        own = tags.get(artist) or []
        if own and main_genre(own) is not None:
            group = "labeled"
        elif own:
            group = "tags_unmapped"
            unmapped.update(t for t, _ in own)
        elif artist in attempted:
            group = "tried_no_tags"
        else:
            group = "never_tried"
        out[group]["artists"] += 1
        out[group]["tracks"] += n
        out[group]["no_mbid"] += artist not in with_mbid
    return {
        **out,
        "tracks_without_artist": sum(1 for a in track_artists if a is None),
        "top_unmapped_tags": unmapped.most_common(top),
    }


def artistless_breakdown(rows: Sequence[tuple[str | None, str | None, bool]]) -> dict:
    """Sanatçısız parçaların nedeni. `rows`: parça başına (MusicBrainz fetch_log durumu | None,
    Last.fm fetch_log durumu | None, kullanıcıya özel kademe B bağı var mı).

    Her parça tek gruba girer; bağ varsa `user_linked` (kuyruk bu bağı okumuyor)."""
    out = {
        "user_linked": 0, "mb_never_tried": 0, "mb_error": 0, "mb_ok_no_artist": 0,
        "mb_empty_lastfm_never_tried": 0, "mb_empty_lastfm_empty": 0, "mb_empty_lastfm_error": 0,
    }
    for mb, lfm, linked in rows:
        if linked:
            out["user_linked"] += 1
        elif mb is None:
            out["mb_never_tried"] += 1
        elif mb == "empty":
            out[f"mb_empty_lastfm_{lfm or 'never_tried'}"] += 1
        elif mb == "error":
            out["mb_error"] += 1
        else:
            out["mb_ok_no_artist"] += 1
    return out


def _artistless(db: Session, user_id, track_ids: Sequence[int]) -> dict:
    if not track_ids:
        return artistless_breakdown([])
    isrc = dict(db.execute(select(Track.id, Track.isrc).where(Track.id.in_(track_ids))).all())
    mb = dict(db.execute(
        select(FetchLog.key, FetchLog.status).where(
            FetchLog.source == "musicbrainz",
            FetchLog.key.in_([f"isrc:{i}" for i in isrc.values() if i]),
        )
    ).all())
    lfm = dict(db.execute(
        select(FetchLog.key, FetchLog.status).where(
            FetchLog.source == "lastfm", FetchLog.key.in_([f"track:{t}" for t in track_ids])
        )
    ).all())
    linked = set(db.scalars(
        select(UserTrackArtist.track_id).where(
            UserTrackArtist.user_id == user_id, UserTrackArtist.track_id.in_(track_ids)
        )
    ))
    return artistless_breakdown(
        [(mb.get(f"isrc:{isrc.get(t)}"), lfm.get(f"track:{t}"), t in linked) for t in track_ids]
    )


def run(email: str, top: int = 30) -> dict:
    engine = make_engine()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Kullanıcı yok: {email}")
        voted = select(VoteEvent.track_id).where(VoteEvent.user_id == user.id)
        rows = db.execute(
            select(Track.id, Track.artist_id)
            .join(UserTrackLink, UserTrackLink.track_id == Track.id)
            .where(UserTrackLink.user_id == user.id, Track.id.not_in(voted))
            .distinct()
        ).all()
        # Kuyrukla aynı kural: paylaşılan sanatçı, yoksa kullanıcıya özel bağ (kademe B).
        artist_of = track_artists(db, user.id, [t for t, _ in rows])
        ids = set(artist_of.values())
        attempted = set(
            db.scalars(select(ArtistTagFetch.artist_id).where(ArtistTagFetch.artist_id.in_(ids)))
        )
        tags: dict[int, list[tuple[str, int]]] = {}
        for aid, tag, weight in db.execute(
            select(ArtistTag.artist_id, ArtistTag.tag, ArtistTag.weight)
            .where(ArtistTag.artist_id.in_(ids))
        ):
            tags.setdefault(aid, []).append((tag, weight))
        with_mbid = set(
            db.scalars(select(Artist.id).where(Artist.id.in_(ids), Artist.mbid.is_not(None)))
        )
        out = label_gap([artist_of.get(t) for t, _ in rows], attempted, tags, with_mbid, top)
        # Paylaşılan sanatçısı (`track.artist_id`) olmayan parçaların dökümü.
        out["no_shared_artist"] = _artistless(db, user.id, [t for t, a in rows if a is None])
        out["db"] = f"{engine.url.host}/{engine.url.database}"
        return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--top", type=int, default=30)
    a = p.parse_args()
    for k, v in run(a.email, a.top).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
