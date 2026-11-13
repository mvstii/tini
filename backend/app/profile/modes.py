"""Zevk modlarına ad verme (saf). Küme sanatçılarının tür etiketlerinden okunur ad türetilir.

Ad, kümedeki sanatçıların (alt) türlerinin afinite ağırlıklı toplamının en büyüğüdür; sonraki en
büyük iki tür `tags` olur. Etiketi olan sanatçı yoksa ad None kalır (istemci "Mod N" gösterir).
Profil gövdesi değişmez; adlar okuma anında güncel etiketlerden türetilir (sürümlü anlık görüntü
bozulmaz, etiketler zenginleştikçe adlar iyileşir).
"""
from collections import defaultdict
from collections.abc import Mapping

# Alt tür/ana tür anahtarı → görünen ad. Tabloda olmayan anahtar "boom_bap" → "Boom Bap" olur.
LABELS: dict[str, str] = {
    "rnb_soul": "R&B / Soul",
    "indie_alt": "Indie / Alternatif",
    "jazz_blues": "Caz / Blues",
    "folk_country": "Folk / Country",
    "contemporary_rnb": "R&B",
    "k_pop": "K-Pop",
    "j_pop": "J-Pop",
    "edm": "EDM",
    "electronic": "Elektronik",
    "classical": "Klasik",
    "turkish": "Türkçe",
    "latin": "Latin",
    "rap": "Rap",
}

MAX_TAGS = 2


def label(key: str) -> str:
    return LABELS.get(key) or key.replace("_", " ").title()


def name_clusters(
    clusters: list[dict], genre_of: Mapping[int, tuple[str, str | None]]
) -> list[dict]:
    """Her küme için `{"id", "name", "tags"}`; girdiyi değiştirmez, kümelerle aynı sırada döner.

    `genre_of`: sanatçı → (ana tür, alt tür | None). Alt tür varsa o, yoksa ana tür sayılır.
    Aynı adı alan kümelere sırayla " 2", " 3" eklenir (adlar ayırt edilebilsin)."""
    out: list[dict] = []
    seen: dict[str, int] = defaultdict(int)
    for c in clusters:
        score: dict[str, float] = defaultdict(float)
        for a in c.get("artists", []):
            pair = genre_of.get(a["artist_id"])
            if pair is None:
                continue
            main, sub = pair
            score[sub or main] += max(float(a.get("affinity", 0)), 0.0)
        # Ağırlık eşitse anahtara göre sırala (aynı veri → aynı ad).
        ranked = sorted((k for k in score if score[k] > 0), key=lambda k: (-score[k], k))
        if not ranked:
            out.append({"id": c["id"], "name": None, "tags": []})
            continue
        name = label(ranked[0])
        seen[name] += 1
        if seen[name] > 1:
            name = f"{name} {seen[name]}"
        out.append(
            {"id": c["id"], "name": name, "tags": [label(k) for k in ranked[1 : 1 + MAX_TAGS]]}
        )
    return out
