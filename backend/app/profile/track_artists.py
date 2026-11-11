"""Parçanın sanatçısı: paylaşılan `track.artist_id` (kademe A), yoksa kullanıcıya özel bağ
(`user_track_artist`, kademe B). Profil hesabıyla (`build_profile_votes`) aynı kural."""
from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Track, UserTrackArtist


def merge_track_artists(
    shared: Mapping[int, int | None], private: Mapping[int, int]
) -> dict[int, int]:
    """track -> artist. Paylaşılan sanatçı önceliklidir; ikisi de yoksa parça sözlükte yer almaz."""
    out = {t: a for t, a in private.items() if a is not None}
    out.update({t: a for t, a in shared.items() if a is not None})
    return out


def track_artists(db: Session, user_id, track_ids: Iterable[int]) -> dict[int, int]:
    ids = list(track_ids)
    if not ids:
        return {}
    shared = dict(db.execute(select(Track.id, Track.artist_id).where(Track.id.in_(ids))).all())
    private = dict(
        db.execute(
            select(UserTrackArtist.track_id, UserTrackArtist.artist_id).where(
                UserTrackArtist.user_id == user_id, UserTrackArtist.track_id.in_(ids)
            )
        ).all()
    )
    return merge_track_artists(shared, private)
