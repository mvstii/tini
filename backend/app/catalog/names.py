import re
import unicodedata
from functools import lru_cache

_NON_ALNUM = re.compile(r"[^0-9a-z]+")


@lru_cache(maxsize=16384)
def normalize_name(name: str) -> str:
    """Karşılaştırma anahtarı: aksan/büyük-küçük harf/noktalama farkı yok sayılır.

    Yalnızca eşleştirme ipucudur; aynı normalize ad kimlik anlamına gelmez (bkz. resolve).
    """
    # ı NFKD'de ayrışmaz; Last.fm/MB sık sık ASCII yazar (Bayındır/Bayindir), i'ye katlanır.
    s = unicodedata.normalize("NFKD", name).casefold().replace("ı", "i")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", s).strip()
