"""Deezer istemcisi: sanatçı adı → portre URL'si. Yalnızca URL döner; görsel dosyası saklanmaz.

Deezer API koşulları görsel saklamayı yasaklar ve ticari kullanım için anlaşma ister; bu yüzden
kaynak yalnızca kapalı testte kullanılır (docs/ARCHITECTURE.md, "Sanatçı fotoğrafları").
"""
from app.catalog.names import normalize_name
from app.sources.http import SourceClient, SourceError

# Deezer kotayı/yoğunluğu HTTP 200 + {"error": {"code": ...}} ile bildirir: 4 = kota aşıldı,
# 700 = servis meşgul. Bunlar "sonuç yok" değil geçici hatadır; miss olarak önbelleğe yazılmaz.
_TRANSIENT_CODES = {4, 700}


def check_error(data: dict | None) -> dict | None:
    """Geçici Deezer hatasında SourceError fırlatır; diğer yanıtı (800 "veri yok" dahil) döner."""
    err = (data or {}).get("error") if isinstance(data, dict) else None
    if isinstance(err, dict) and err.get("code") in _TRANSIENT_CODES:
        msg = f"{err.get('code')} {err.get('message') or ''}".strip()
        raise SourceError(f"Deezer geçici hata: {msg}")
    return data


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


def pick_album_cover(data: dict | None, name: str) -> str | None:
    """Parça aramasından, sanatçısı adıyla birebir eşleşen ilk parçanın albüm kapağı.

    Portresi olmayan (ya da adı sanatçı aramasında eşleşmeyen) sanatçı için yedek görsel."""
    want = normalize_name(name)
    for t in (data or {}).get("data") or []:
        if normalize_name(((t or {}).get("artist") or {}).get("name") or "") != want:
            continue
        album = t.get("album") or {}
        for key in ("cover_xl", "cover_big", "cover_medium"):
            url = album.get(key)
            if url and "/cover//" not in url:
                return url
    return None


class DeezerClient:
    def __init__(self, http: SourceClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def _get(self, url: str, params: dict[str, str] | None = None) -> dict | None:
        return check_error(self._http.get_json(url, params))

    def artist_picture(self, name: str) -> str | None:
        """Sanatçı portresi; yoksa sanatçının bir parçasının albüm kapağı (boş kalmasın)."""
        data = self._get(f"{self._base}/search/artist", {"q": name, "limit": "5"})
        found = pick_picture(data, name)
        if found:
            return found
        tracks = self._get(f"{self._base}/search", {"q": f'artist:"{name}"', "limit": "10"})
        return pick_album_cover(tracks, name)

    def album_tracks(self, artist: str, title: str) -> list[dict]:
        """Yayının parça listesi: [{id, title}] (önizleme URL'si süreli olduğundan alınmaz)."""
        found = self._get(
            f"{self._base}/search/album",
            {"q": f'artist:"{artist}" album:"{title}"', "limit": "5"},
        )
        album = pick_album(found, artist, title)
        if album is None:
            return []
        data = self._get(f"{self._base}/album/{album}/tracks", {"limit": "50"})
        return [
            {"id": t["id"], "title": t["title"]}
            for t in (data or {}).get("data") or []
            if t.get("id") and t.get("title")
        ]

    def track_preview_by_id(self, deezer_id: int) -> tuple[str, str] | None:
        return pick_preview(self._get(f"{self._base}/track/{deezer_id}"))

    def track_preview(self, isrc: str | None, artist: str | None) -> tuple[str, str] | None:
        """30 sn önizleme: önce ISRC, olmazsa sanatçı adıyla arama. (url, başlık) ya da None."""
        if isrc:
            found = pick_preview(self._get(f"{self._base}/track/isrc:{isrc}"))
            if found:
                return found
        if artist:
            data = self._get(
                f"{self._base}/search", {"q": artist, "limit": "10"}
            )
            return pick_preview(data, artist)
        return None


def pick_album(data: dict | None, artist: str, title: str) -> int | None:
    """Albüm aramasından sanatçı ve başlığı birebir (normalize) eşleşen ilk albümün kimliği."""
    want_a, want_t = normalize_name(artist), normalize_name(title)
    for a in (data or {}).get("data") or []:
        if (
            normalize_name((a.get("artist") or {}).get("name") or "") == want_a
            and normalize_name(a.get("title") or "") == want_t
        ):
            return a.get("id")
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
