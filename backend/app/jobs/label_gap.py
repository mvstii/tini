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
from app.models import Artist, ArtistTag, ArtistTagFetch, Track, User, UserTrackLink, VoteEvent
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
        ids = {a for _, a in rows if a is not None}
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
        out = label_gap([a for _, a in rows], attempted, tags, with_mbid, top)
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
