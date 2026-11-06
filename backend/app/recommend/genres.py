"""Tür etiketlerinden ana tür (saf). Serbest etiketleri ~14 ana türe indirger.

Eşleme tablosu veridir (zevke göre düzeltilir); algoritma `main_genre` ve `blend_labels`tir.
Sanatçının ana türü, etiket ağırlıklarının tür başına toplamının en büyüğüdür; eşitlikte
`GENRES` sırası kazanır. Eşleşen etiket yoksa tür yoktur (None).
"""
import re
from collections.abc import Iterable

GENRES: dict[str, tuple[str, ...]] = {
    "rap": ("hip hop", "hiphop", "rap", "trap", "drill", "grime", "boom bap"),
    "rnb_soul": ("r&b", "rnb", "r and b", "soul", "funk", "motown", "neo soul"),
    "pop": ("pop", "dance pop", "synthpop", "synth pop", "europop", "k pop", "j pop", "teen pop"),
    "rock": ("rock", "grunge", "hard rock", "classic rock", "psychedelic", "blues rock"),
    "indie_alt": ("indie", "alternative", "shoegaze", "dream pop", "lo fi", "bedroom pop", "emo"),
    "metal": ("metal", "thrash", "doom", "deathcore", "metalcore", "grindcore"),
    "punk": ("punk", "hardcore", "ska punk", "post hardcore"),
    "electronic": (
        "electronic", "electronica", "house", "techno", "edm", "trance", "dubstep", "ambient",
        "drum and bass", "dnb", "disco", "idm", "hardstyle", "synthwave", "downtempo", "trip hop",
    ),
    "jazz_blues": ("jazz", "bebop", "swing", "blues", "bossa nova", "big band"),
    "classical": ("classical", "orchestral", "opera", "baroque", "piano", "soundtrack", "score"),
    "folk_country": ("folk", "country", "bluegrass", "singer songwriter", "americana", "acoustic"),
    "latin": ("latin", "reggaeton", "salsa", "bachata", "flamenco", "cumbia", "latino", "bossa"),
    "reggae": ("reggae", "dancehall", "dub", "ska", "roots"),
    "turkish": ("turkish", "turkce", "türk", "arabesk", "anadolu", "turkish pop", "turkish rock"),
}
_ORDER = list(GENRES)
_RE = {
    g: re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(p) for p in ps) + r")(?![a-z0-9])")
    for g, ps in GENRES.items()
}


def _norm(tag: str) -> str:
    return re.sub(r"[\s_\-/]+", " ", tag.lower()).strip()


def main_genre(tags: Iterable[tuple[str, int]]) -> str | None:
    """(etiket, ağırlık) listesinden ana tür; eşleşme yoksa None."""
    score: dict[str, int] = {}
    for tag, weight in tags:
        t = _norm(tag)
        for g, rx in _RE.items():
            if rx.search(t):
                score[g] = score.get(g, 0) + max(int(weight), 1)
    if not score:
        return None
    return max(score, key=lambda g: (score[g], -_ORDER.index(g)))


GENRE_BASE = 1000  # tür etiketleri topluluk etiketleriyle (0..k-1) çakışmasın


def blend_labels(
    community: dict[int, int], genre_of: dict[int, str]
) -> dict[int, int]:
    """Düğüm etiketi: ana tür biliniyorsa tür kimliği (GENRE_BASE+sıra), yoksa grafik topluluğu."""
    out = dict(community)
    for artist, g in genre_of.items():
        if artist in out and g in _ORDER:
            out[artist] = GENRE_BASE + _ORDER.index(g)
    return out
