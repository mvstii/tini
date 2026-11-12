"""Aktif öğrenme kuyruğu için DB katmanı: sanatçı belirsizliği ve awaiting olayları."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.service import get_matrix
from app.models import TasteProfile, UnheardEvent
from app.profile.active import uncertainty
from app.recommend.ppr import artist_scores

UNSET: Any = object()  # "ön yüklenmedi" işareti (None geçerli bir değerdir: profil yok)


def artist_uncertainties(
    db: Session, user_id, artist_ids: set[int], pcfg: ProfileSettings, rcfg: RecommendSettings,
    gcfg: GraphSettings, profile: TasteProfile | None = UNSET,
) -> dict[int, float]:
    """Profil veya graf yoksa boş sözlük döner (hepsi 'bilinmiyor' değerini alır).
    `profile` (son anlık görüntü ya da None) verilirse yeniden okunmaz."""
    row = profile
    if row is UNSET:
        row = db.scalar(
            select(TasteProfile)
            .where(TasteProfile.user_id == user_id)
            .order_by(TasteProfile.version.desc())
            .limit(1)
        )
    built = get_matrix(db, gcfg)
    if row is None or built is None:
        return {}
    scores = artist_scores(built[1], row.body, rcfg)
    ref = sorted(scores.values())
    return {
        a: uncertainty(scores.get(a), ref, pcfg.active_unknown_uncertainty) for a in artist_ids
    }


def mark_awaiting(db: Session, user_id, served_pool: set[int], statuses) -> None:
    """Kuyrukta sunulan havuz parçaları için 'awaiting' olayı (zaten awaiting değilse)."""
    already = {s.track_id for s in statuses if s.state == "awaiting"}
    for t in sorted(served_pool - already):
        db.add(UnheardEvent(user_id=user_id, track_id=t, state="awaiting"))
    if served_pool - already:
        db.commit()
