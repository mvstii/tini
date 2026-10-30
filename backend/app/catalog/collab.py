"""İşbirliği düğümü tespiti: "A & B" gibi adlar, parçaları ayrı sanatçıysa işbirliğidir.

Yalnızca ada bakmak "Tyler, The Creator" ya da "Captain & Tennille" gibi gerçek sanatçıları
bozar; bu yüzden her parçanın katalogda kendi başına (kenarı olan) bir sanatçı olması aranır.
Saf fonksiyon: aynı girdi aynı sonucu verir.
"""
import re

from app.catalog.names import normalize_name

_SEP = re.compile(r"\s+(?:&|and|x|\+|feat\.?|ft\.?|with)\s+|\s*,\s*", re.IGNORECASE)


def split_parts(name: str) -> list[str]:
    return [p.strip() for p in _SEP.split(name) if p and p.strip()]


def detect_collabs(
    artists: list[tuple[int, str | None]], with_edges: set[int]
) -> dict[int, list[int]]:
    """{işbirliği_id: [üye_id, ...]}. Üye adayı yalnızca kenarı olan sanatçıdır (en küçük id)."""
    by_norm: dict[str, int] = {}
    for aid, name in sorted(artists):
        if name and aid in with_edges:
            by_norm.setdefault(normalize_name(name), aid)
    out: dict[int, list[int]] = {}
    for aid, name in artists:
        if not name:
            continue
        parts = split_parts(name)
        if len(parts) < 2:
            continue
        members = [by_norm.get(normalize_name(p)) for p in parts]
        if any(m is None or m == aid for m in members) or len(set(members)) < 2:
            continue
        out[aid] = sorted(set(members))  # type: ignore[arg-type]
    return out
