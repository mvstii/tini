import re
import unicodedata

_NON_ALNUM = re.compile(r"[^0-9a-zı]+")


def normalize_name(name: str) -> str:
    """Karşılaştırma anahtarı: aksan/büyük-küçük harf/noktalama farkı yok sayılır.

    Yalnızca eşleştirme ipucudur; aynı normalize ad kimlik anlamına gelmez (bkz. resolve).
    """
    s = unicodedata.normalize("NFKD", name).casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", s).strip()
