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


# Alt türler (tür omurgası, PR-4): ana tür + etiket kalıpları. Veridir; veriyle büyür.
# Kalıpların İLK öğesi ListenBrainz etiket sorgusunda kullanılır. Sıra eşitlikte kazananı belirler
# (özel olan genelden önce). Her alt türün ana türü `GENRES` anahtarlarından biridir.
SUB_GENRES: dict[str, tuple[str, tuple[str, ...]]] = {
    # rap
    "trap": ("rap", ("trap", "trap rap")),
    "drill": ("rap", ("drill", "uk drill")),
    "boom_bap": ("rap", ("boom bap", "east coast hip hop", "underground hip hop")),
    "gangsta_rap": ("rap", ("gangsta rap", "west coast hip hop", "g funk")),
    "conscious_rap": ("rap", ("conscious hip hop", "alternative hip hop", "jazz rap")),
    "pop_rap": ("rap", ("hip hop", "rap", "pop rap")),
    # rnb_soul
    "contemporary_rnb": ("rnb_soul", ("r&b", "contemporary r&b", "alternative r&b", "rnb")),
    "neo_soul": ("rnb_soul", ("neo soul",)),
    "soul": ("rnb_soul", ("soul", "motown", "northern soul", "southern soul")),
    "funk": ("rnb_soul", ("funk", "p funk")),
    # pop
    "dance_pop": ("pop", ("dance pop", "europop", "teen pop")),
    "synthpop": ("pop", ("synthpop", "synth pop", "electropop")),
    "k_pop": ("pop", ("k-pop", "k pop", "kpop")),
    "j_pop": ("pop", ("j-pop", "j pop", "jpop")),
    "mainstream_pop": ("pop", ("pop", "art pop")),
    # rock
    "classic_rock": ("rock", ("classic rock", "southern rock", "blues rock")),
    "hard_rock": ("rock", ("hard rock", "glam rock", "heavy rock")),
    "grunge": ("rock", ("grunge", "post grunge")),
    "psychedelic_rock": ("rock", ("psychedelic rock", "psychedelic", "stoner rock", "krautrock")),
    "progressive_rock": ("rock", ("progressive rock", "prog rock", "art rock")),
    "alt_rock": ("rock", ("alternative rock", "rock", "modern rock")),
    # indie_alt
    "indie_rock": ("indie_alt", ("indie rock", "indie")),
    "indie_pop": ("indie_alt", ("indie pop", "bedroom pop", "jangle pop")),
    "shoegaze": ("indie_alt", ("shoegaze", "dream pop")),
    "emo": ("indie_alt", ("emo", "midwest emo")),
    "lofi": ("indie_alt", ("lo fi", "lofi")),
    "alternative": ("indie_alt", ("alternative", "post rock")),
    # metal
    "heavy_metal": ("metal", ("heavy metal", "power metal", "speed metal")),
    "thrash_metal": ("metal", ("thrash metal", "thrash")),
    "death_metal": ("metal", ("death metal", "melodic death metal", "grindcore")),
    "black_metal": ("metal", ("black metal", "atmospheric black metal")),
    "doom_metal": ("metal", ("doom metal", "doom", "sludge metal")),
    "metalcore": ("metal", ("metalcore", "deathcore")),
    "nu_metal": ("metal", ("nu metal", "alternative metal", "metal")),
    # punk
    "punk_rock": ("punk", ("punk rock", "punk", "pop punk")),
    "hardcore_punk": ("punk", ("hardcore punk", "hardcore", "post hardcore")),
    "ska_punk": ("punk", ("ska punk", "skate punk")),
    # electronic
    "house": ("electronic", ("house", "deep house", "tech house", "progressive house")),
    "techno": ("electronic", ("techno", "minimal techno", "acid techno")),
    "trance": ("electronic", ("trance", "psytrance", "uplifting trance")),
    "drum_and_bass": ("electronic", ("drum and bass", "dnb", "jungle", "liquid funk")),
    "dubstep": ("electronic", ("dubstep", "brostep", "riddim")),
    "ambient": ("electronic", ("ambient", "drone", "downtempo", "chillout")),
    "synthwave": ("electronic", ("synthwave", "retrowave", "vaporwave")),
    "disco": ("electronic", ("disco", "nu disco", "italo disco")),
    "edm": ("electronic", ("edm", "electro house", "big room", "electronic", "electronica")),
    "trip_hop": ("electronic", ("trip hop", "idm")),
    # jazz_blues
    "bebop": ("jazz_blues", ("bebop", "hard bop", "cool jazz")),
    "swing": ("jazz_blues", ("swing", "big band", "vocal jazz")),
    "fusion": ("jazz_blues", ("jazz fusion", "smooth jazz", "acid jazz")),
    "blues": ("jazz_blues", ("blues", "delta blues", "chicago blues", "electric blues")),
    "bossa_nova": ("jazz_blues", ("bossa nova",)),
    "jazz": ("jazz_blues", ("jazz", "contemporary jazz")),
    # classical
    "baroque": ("classical", ("baroque",)),
    "opera": ("classical", ("opera",)),
    "piano_classical": ("classical", ("piano", "solo piano", "neoclassical")),
    "orchestral": ("classical", ("classical", "orchestral", "romantic")),
    "soundtrack": ("classical", ("soundtrack", "score", "film score")),
    # folk_country
    "country": ("folk_country", ("country", "country pop", "outlaw country")),
    "bluegrass": ("folk_country", ("bluegrass", "americana")),
    "singer_songwriter": ("folk_country", ("singer songwriter", "acoustic")),
    "folk": ("folk_country", ("folk", "indie folk")),
    # latin
    "reggaeton": ("latin", ("reggaeton", "latin trap", "urbano latino")),
    "salsa": ("latin", ("salsa", "son cubano", "timba")),
    "bachata": ("latin", ("bachata", "merengue")),
    "cumbia": ("latin", ("cumbia", "vallenato")),
    "flamenco": ("latin", ("flamenco", "rumba flamenca")),
    "latin_pop": ("latin", ("latin pop", "latin", "latino")),
    # reggae
    "reggae": ("reggae", ("reggae", "roots reggae", "dub")),
    "dancehall": ("reggae", ("dancehall", "ragga")),
    "ska": ("reggae", ("ska", "rocksteady", "two tone")),
    # turkish (Türkçe alt türler; "turkish" ana etiketi kalıplarda genel yedektir)
    "arabesk": ("turkish", ("arabesk", "arabesk rap", "fantezi")),
    "anadolu_rock": ("turkish", ("anatolian rock", "anadolu rock", "turkish rock", "turkce rock")),
    "turkce_pop": ("turkish", ("turkish pop", "turkce pop", "türkçe pop")),
    "turk_halk": ("turkish", ("turkish folk", "turk halk muzigi", "türk halk müziği", "halk")),
    "turk_sanat": ("turkish", ("turkish classical", "turk sanat muzigi", "türk sanat müziği")),
    "turkce_rap": ("turkish", ("turkish rap", "turkish hip hop", "turkce rap", "türkçe rap")),
}
_SUB_RE = {
    g: re.compile(
        r"(?<![a-z0-9])(?:" + "|".join(re.escape(_norm(p)) for p in ps) + r")(?![a-z0-9])"
    )
    for g, (_, ps) in SUB_GENRES.items()
}
_SUB_ORDER = list(SUB_GENRES)


def sub_genre(tags: Iterable[tuple[str, int]]) -> str | None:
    """(etiket, ağırlık) listesinden alt tür; eşleşme yoksa None.

    Her etiket yalnızca en özel (en uzun kalıpla eşleşen) alt türe oy verir; böylece "metal" gibi
    genel etiket "death metal"i ezmez. Eşitlikte daha özel kalıp, sonra `SUB_GENRES` sırası kazanır.
    """
    score: dict[str, int] = {}
    spec: dict[str, int] = {}
    for tag, weight in tags:
        t = _norm(tag)
        best: tuple[int, int, str] | None = None
        for i, (g, rx) in enumerate(_SUB_RE.items()):
            m = rx.search(t)
            if m:
                cand = (len(m.group(0)), -i, g)
                if best is None or cand > best:
                    best = cand
        if best is not None:
            g = best[2]
            score[g] = score.get(g, 0) + max(int(weight), 1)
            spec[g] = max(spec.get(g, 0), best[0])
    if not score:
        return None
    return max(score, key=lambda g: (score[g], spec[g], -_SUB_ORDER.index(g)))


def main_of(sub: str) -> str:
    """Alt türün ana türü (bilinmeyen alt tür KeyError)."""
    return SUB_GENRES[sub][0]


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
