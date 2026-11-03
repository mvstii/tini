"""Deezer istemcisi: sanatçı adı → portre URL'si. Yalnızca URL döner; görsel dosyası saklanmaz.

Deezer API koşulları görsel saklamayı yasaklar ve ticari kullanım için anlaşma ister; bu yüzden
kaynak yalnızca kapalı testte kullanılır (docs/ARCHITECTURE.md, "Sanatçı fotoğrafları").
"""
from app.catalog.names import normalize_name
from app.sources.http import SourceClient


def pick_picture(data: dict | None, name: str) -> str | None:
    """Arama yanıtından adı birebir eşleşen ilk sanatçının büyük portresi.

    Deezer görseli olmayan sanatçıya boş karma içeren yer tutucu URL verir; o None sayılır."""
    want = normalize_name(name)
    for a in (data or {}).get("data") or []:
        if normalize_name(a.get("name") or "") != want:
            continue
        for key in ("picture_xl", "picture_big", "picture_medium"):
            url = a.get(key)
            if url and "/artist//" not in url:
                return url
        return None
    return None


class DeezerClient:
    def __init__(self, http: SourceClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def artist_picture(self, name: str) -> str | None:
        data = self._http.get_json(f"{self._base}/search/artist", {"q": name, "limit": "5"})
        return pick_picture(data, name)

    def track_preview(self, isrc: str | None, artist: str | None) -> tuple[str, str] | None:
        """30 sn önizleme: önce ISRC, olmazsa sanatçı adıyla arama. (url, başlık) ya da None."""
        if isrc:
            found = pick_preview(self._http.get_json(f"{self._base}/track/isrc:{isrc}"))
            if found:
                return found
        if artist:
            data = self._http.get_json(
                f"{self._base}/search", {"q": artist, "limit": "10"}
            )
            return pick_preview(data, artist)
        return None


def pick_preview(data: dict | None, artist: str | None = None) -> tuple[str, str] | None:
    """Parça ya da arama yanıtından (önizleme URL'si, başlık); `artist` verilirse adı eşleşen.

    Deezer önizleme URL'leri imzalı ve süreli olduğundan çağıran bunu saklamaz."""
    rows = data.get("data") if data and "data" in data else [data] if data else []
    want = normalize_name(artist) if artist else None
    for t in rows:
        url = (t or {}).get("preview")
        if not url:
            continue
        if want and normalize_name(((t.get("artist") or {}).get("name")) or "") != want:
            continue
        return url, t.get("title") or ""
    return None
