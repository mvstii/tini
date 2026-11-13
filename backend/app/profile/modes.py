"""Zevk modlarına ad verme (saf). Küme sanatçılarının tür etiketlerinden okunur ad türetilir.

Ad, kümede en belirgin (alt) türdür: afinite ağırlıklı payı × kümeye özgülüğü; sonraki iki tür
`tags` olur. Aynı ad iki kümeye düşerse ikinci tür eklenir ("Pop Rap · Trap"), yine olursa numara.
Etiketi olan sanatçı yoksa ad None kalır (istemci "Mod N" gösterir).
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
    # Tüm kümelerde ortak baskın bir tür (ör. pop rap) her moda aynı adı vermesin: ad ve etiketler
    # türün kümedeki payı × kümeye özgülüğü (küme payı / genel pay) ile sıralanır.
    per: list[dict[str, float]] = []
    for c in clusters:
        score: dict[str, float] = defaultdict(float)
        for a in c.get("artists", []):
            pair = genre_of.get(a["artist_id"])
            if pair is None:
                continue
            main, sub = pair
            score[sub or main] += max(float(a.get("affinity", 0)), 0.0)
        per.append({k: v for k, v in score.items() if v > 0})
    total: dict[str, float] = defaultdict(float)
    grand = 0.0
    for sc in per:
        for k, v in sc.items():
            total[k] += v
            grand += v
    out: list[dict] = []
    seen: dict[str, int] = defaultdict(int)
    for c, sc in zip(clusters, per, strict=True):
        if not sc:
            out.append({"id": c["id"], "name": None, "tags": []})
            continue
        size = sum(sc.values())

        def rank(k: str, sc=sc, size=size) -> float:
            share = sc[k] / size
            return share * (share / (total[k] / grand))

        # Eşitlikte anahtara göre sırala (aynı veri → aynı ad).
        ranked = sorted(sc, key=lambda k: (-rank(k), k))
        name = label(ranked[0])
        tags = [label(k) for k in ranked[1 : 1 + MAX_TAGS]]
        if seen[name] and tags:  # aynı ad: en ayırt edici ikinci türle ayır
            name = f"{name} · {tags[0]}"
        seen[name] += 1
        if seen[name] > 1:
            name = f"{name} {seen[name]}"
        out.append({"id": c["id"], "name": name, "tags": tags})
    return out
