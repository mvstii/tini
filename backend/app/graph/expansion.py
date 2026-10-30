"""Tembel genişleme planı (saf): hangi sanatçıların komşuları çekilmeli?

Girdi yalnızca değerlerdir (veritabanı/ağ yok); aynı girdi her zaman aynı planı üretir.
"""
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ExpansionPlan:
    to_fetch: list[int]  # komşuları çekilecek sanatçılar, çapaya yakın olan önce
    cached: int  # önbellekte geçerli bulunan (çekilmeyecek) düğüm sayısı

    @property
    def visited(self) -> int:
        return self.cached + len(self.to_fetch)


def plan_expansion(
    anchors: Sequence[int],
    depth: int,
    fresh: Collection[int],
    edges: Mapping[int, Sequence[int]],
) -> ExpansionPlan:
    """Çapalardan `depth` adım uzaklığa kadar kenarı bilinmesi gereken düğümleri bulur.

    `fresh`: geçerli (süresi dolmamış) çekimi olan sanatçılar; boş/hata sonucu da dahil,
    böylece negatif önbellek tekrar çağrıyı önler. `edges`: fresh sanatçıların bilinen komşuları.
    Çekilmesi gereken bir düğümün komşuları henüz bilinmez; plan o dalda durur, iş çekimden
    sonra yeniden planlar.
    """
    visited: set[int] = set()
    to_fetch: list[int] = []
    cached = 0
    frontier = sorted(dict.fromkeys(anchors))
    for _ in range(depth):
        nxt: list[int] = []
        for node in frontier:
            if node in visited:
                continue
            visited.add(node)
            if node in fresh:
                cached += 1
                nxt.extend(edges.get(node, ()))
            else:
                to_fetch.append(node)
        frontier = sorted(dict.fromkeys(nxt))
    return ExpansionPlan(to_fetch, cached)
