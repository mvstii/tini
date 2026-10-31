"""Takip kümesi (saf): profilden otomatik takip + elle takip - bırakılanlar."""


def auto_follows(profile: dict) -> set[int]:
    """Profildeki net pozitif sanatçılar (kümeler, kümesizler) ve çapalar."""
    out = {a["artist_id"] for a in profile.get("anchors", [])}
    for c in profile.get("clusters", []):
        out |= {a["artist_id"] for a in c["artists"]}
    out |= {a["artist_id"] for a in profile.get("unclustered", [])}
    return out


def effective_follows(auto: set[int], manual: set[int], muted: set[int]) -> dict[int, str]:
    """artist_id -> 'manual' | 'auto'. Sanatçı başına tek kayıt: manual ve muted çakışmaz."""
    out = {a: "auto" for a in auto - muted}
    out.update({a: "manual" for a in manual})
    return out
