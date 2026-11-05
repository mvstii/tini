"""Spotify adaptörü. Kapalı uç noktalar kullanılmaz (bkz. CLAUDE.md)."""
import time
from urllib.parse import quote

import httpx

from app.adapters.base import Library, LibraryTrack, TrackCard
from app.catalog.names import normalize_name

API = "https://api.spotify.com/v1"
MAX_RETRIES = 4
_SEARCH_PAGE = 10  # Development Mode'da /search en çok 10 sonuç döner
_ARTIST_SEARCH_PAGES = 3


def _match_key(name: str) -> str:
    """Sanatçı adı karşılaştırma anahtarı: aksan/noktalama yok sayılır, `$` → `s` (Travi$ Scott)."""
    return normalize_name(name.replace("$", "s")).replace(" ", "")


_COVER_SIZE = 300  # oylama kartı için yeterli; en yakın genişlikteki görsel seçilir


def _cover_url(images: list[dict] | None) -> str | None:
    """Albüm görselleri arasından ~300 px olanı; boyutsuz kayıtlar sona kalır."""
    usable = [i for i in images or [] if i.get("url")]
    if not usable:
        return None
    return min(usable, key=lambda i: abs((i.get("width") or 10_000) - _COVER_SIZE))["url"]


class SpotifyAdapter:
    service = "spotify"

    def __init__(self, http: httpx.Client, access_token: str, sleep=time.sleep):
        self._http = http
        self._auth = {"Authorization": f"Bearer {access_token}"}
        self._sleep = sleep

    def _request(self, method: str, path: str, **kw) -> dict:
        """429 gelirse Retry-After kadar bekler; sınırlı sayıda yeniden dener."""
        for attempt in range(MAX_RETRIES + 1):
            r = self._http.request(method, API + path, headers=self._auth, **kw)
            if r.status_code == 429 and attempt < MAX_RETRIES:
                self._sleep(min(int(r.headers.get("Retry-After", "1")), 30))
                continue
            r.raise_for_status()
            return r.json() if r.content else {}
        raise RuntimeError("ulaşılamaz")

    def _pages(self, path: str, limit: int, max_items: int, **params):
        offset = 0
        while offset < max_items:
            body = self._request("GET", path, params={"limit": limit, "offset": offset, **params})
            items = body.get("items", [])
            yield from items
            if not items or not body.get("next"):
                return
            offset += limit

    def read_library(self, max_tracks: int = 500) -> Library:
        lib, seen = Library(), set()
        raw = [i["track"] for i in self._pages("/me/tracks", 50, max_tracks) if i.get("track")]
        raw += list(self._pages("/me/top/tracks", 50, 50, time_range="long_term"))
        for t in raw:
            tid = t.get("id")
            if tid in seen:
                continue
            seen.add(tid)
            isrc = (t.get("external_ids") or {}).get("isrc")
            names = tuple(a["name"] for a in t.get("artists", []) if a.get("name"))
            if not (tid and isrc and t.get("name") and names):
                lib.skipped += 1
                continue
            lib.tracks.append(
                LibraryTrack(
                    tid, isrc.upper(), t["name"], names, t.get("duration_ms"),
                    _cover_url((t.get("album") or {}).get("images")),
                )
            )
        return lib

    def create_playlist(self, name: str, external_ids: list[str]) -> str:
        # /users/{id}/playlists canlıda 403 veriyor (31 Ekim 2026); /me/playlists çalışır.
        pl = self._request("POST", "/me/playlists", json={"name": name, "public": False})
        # /tracks artık 403 veriyor; Faz 0'da doğrulandı, /items kullanılır.
        for i in range(0, len(external_ids), 100):
            uris = [f"spotify:track:{x}" for x in external_ids[i : i + 100]]
            self._request("POST", f"/playlists/{pl['id']}/items", json={"uris": uris})
        return pl["id"]

    def _isrc_item(self, isrc: str) -> dict | None:
        body = self._request(
            "GET", "/search", params={"q": f"isrc:{isrc}", "type": "track", "limit": 1}
        )
        items = (body.get("tracks") or {}).get("items") or []
        return items[0] if items and items[0].get("id") else None

    def find_track(self, isrc: str) -> str | None:
        """ISRC'den servis parça kimliği; bulunamazsa None. Kimlik saklanmaz."""
        item = self._isrc_item(isrc)
        return item["id"] if item else None

    def find_artist_track(self, artist_name: str) -> str | None:
        """Sanatçının aramada çıkan ilk parçası (artist top-tracks kapalı); ad eşleşmezse None."""
        item = self._artist_item(artist_name)
        return item["id"] if item else None

    def find_card(self, isrc: str | None, artist_name: str) -> TrackCard | None:
        """Gösterim için başlık/sanatçı/kapak: ISRC varsa onunla, yoksa sanatçı aramasıyla.
        Hiçbir şey saklanmaz; çağıran yalnızca isteğe yanıt verir."""
        item = (self._isrc_item(isrc) if isrc else None) or self._artist_item(artist_name)
        if item is None:
            return None
        names = tuple(a["name"] for a in item.get("artists") or [] if a.get("name"))
        return TrackCard(
            item.get("name") or "", names, _cover_url((item.get("album") or {}).get("images"))
        )

    def _artist_item(self, artist_name: str) -> dict | None:
        if not artist_name:
            return None
        q = f'artist:"{artist_name}"'
        wanted = _match_key(artist_name)
        # Kısa adlarda ("NAV") doğru sanatçı ilk sayfada çıkmayabilir; birkaç sayfa taranır.
        for page in range(_ARTIST_SEARCH_PAGES):
            params = {"q": q, "type": "track", "limit": _SEARCH_PAGE, "offset": page * _SEARCH_PAGE}
            body = self._request("GET", "/search", params=params)
            items = (body.get("tracks") or {}).get("items") or []
            for t in items:
                names = {_match_key(a.get("name", "")) for a in t.get("artists") or []}
                if t.get("id") and wanted in names:
                    return t
            if not items:  # sayfa limitten kısa dönebilir (canlıda 5 öğe geldi); yalnız boşta dur
                break
        return None

    def open_url(
        self, isrc: str | None, artist_name: str, hint: str | None = None
    ) -> tuple[str, str]:
        try:
            tid = self.find_track(isrc) if isrc else None
            if not tid and not hint:
                tid = self.find_artist_track(artist_name)
        except httpx.HTTPError:
            tid = None  # servis yanıt vermiyorsa arama bağlantısına düş
        if tid:
            return "track", f"spotify:track:{tid}"
        query = f"{artist_name} {hint}".strip() if hint else artist_name
        return "search", f"spotify:search:{quote(query)}"
