"""Günün şarkısı seçimi (saf): aynı kullanıcı, gün ve liste her zaman aynı öğeyi seçer."""
import hashlib
from collections.abc import Collection, Sequence
from datetime import date


def _key(user_id: str, day: date, position: int, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{user_id}:{day.isoformat()}:{position}".encode()).hexdigest()


def pick_daily(
    candidates: Sequence[tuple[int, int | None]],
    day: date,
    user_id: str,
    voted_tracks: Collection[int],
    salt: str,
) -> int | None:
    """candidates: (liste konumu, parça kimliği ya da None). Oylanmış parçalar elenir; kalanlar
    arasından gün/kullanıcı tohumlu özetin en küçüğü seçilir. Aday kalmazsa None."""
    pool = [p for p, track in candidates if track is None or track not in voted_tracks]
    if not pool:
        return None
    return min(pool, key=lambda p: _key(user_id, day, p, salt))
