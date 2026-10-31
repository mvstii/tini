"""Spotify adaptörü. Kapalı uç noktalar kullanılmaz (bkz. CLAUDE.md)."""
import time
from urllib.parse import quote

import httpx

from app.adapters.base import Library, LibraryTrack

API = "https://api.spotify.com/v1"
MAX_RETRIES = 4


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
                LibraryTrack(tid, isrc.upper(), t["name"], names, t.get("duration_ms"))
            )
        return lib

    def create_playlist(self, name: str, external_ids: list[str]) -> str:
        me = self._request("GET", "/me")["id"]
        pl = self._request(
            "POST", f"/users/{me}/playlists", json={"name": name, "public": False}
        )
        # /tracks artık 403 veriyor; Faz 0'da doğrulandı, /items kullanılır.
        for i in range(0, len(external_ids), 100):
            uris = [f"spotify:track:{x}" for x in external_ids[i : i + 100]]
            self._request("POST", f"/playlists/{pl['id']}/items", json={"uris": uris})
        return pl["id"]

    def open_url(self, isrc: str | None, artist_name: str) -> tuple[str, str]:
        if isrc:
            body = self._request(
                "GET", "/search", params={"q": f"isrc:{isrc}", "type": "track", "limit": 1}
            )
            items = (body.get("tracks") or {}).get("items") or []
            if items and items[0].get("id"):
                return "track", f"spotify:track:{items[0]['id']}"
        return "search", f"spotify:search:{quote(artist_name)}"
