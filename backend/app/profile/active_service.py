"""Aktif öğrenme kuyruğu için DB katmanı: sanatçı belirsizliği ve awaiting olayları."""
import threading
from collections import OrderedDict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GraphSettings, ProfileSettings, RecommendSettings
from app.graph.matrix import GraphMatrix
from app.graph.service import get_matrix
from app.models import TasteProfile, UnheardEvent
from app.profile.active import uncertainty
from app.recommend.ppr import artist_scores

UNSET: Any = object()  # "ön yüklenmedi" işareti (None geçerli bir değerdir: profil yok)

# PPR skorları saf bir türevdir (matris + profil gövdesi + ayarlar); profil anlık görüntüsü ve
# matris değişmedikçe yeniden hesaplanmaz. Süreç içi, kullanıcı başına tek kayıt, sınırlı boyut.
_SCORE_CACHE_USERS = 8
_score_lock = threading.Lock()
_score_cache: OrderedDict[Any, tuple[tuple, GraphMatrix, RecommendSettings, list[float], dict]] = (
    OrderedDict()
)


def clear_score_cache() -> None:
    with _score_lock:
        _score_cache.clear()


def _cached_scores(
    gm: GraphMatrix, row: TasteProfile, rcfg: RecommendSettings
) -> tuple[list[float], dict[int, float]]:
    """(sıralı skorlar, sanatçı → skor). Anahtar: profil anlık görüntüsü, matris, ayarlar."""
    key = (row.id, row.version, row.created_at)
    with _score_lock:
        hit = _score_cache.get(row.user_id)
        if hit is not None and hit[0] == key and hit[1] is gm and hit[2] == rcfg:
            _score_cache.move_to_end(row.user_id)
            return hit[3], hit[4]
    scores = artist_scores(gm, row.body, rcfg)
    ref = sorted(scores.values())
    with _score_lock:
        _score_cache[row.user_id] = (key, gm, rcfg, ref, scores)
        _score_cache.move_to_end(row.user_id)
        while len(_score_cache) > _SCORE_CACHE_USERS:
            _score_cache.popitem(last=False)
    return ref, scores


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
    ref, scores = _cached_scores(built[1], row, rcfg)
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
