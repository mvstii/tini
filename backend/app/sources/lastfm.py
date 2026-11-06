"""Last.fm istemcisi: artist.getInfo (kanonik ad/MBID) ve artist.getSimilar.

API anahtarı sorgu parametresidir; URL'leri loglamayın (bkz. app.jobs.enrich).
"""
import uuid
from dataclasses import dataclass

from app.sources.http import SourceClient, SourceError

_NOT_FOUND = 6  # Last.fm: "The artist you supplied could not be found"


@dataclass(frozen=True)
class LfmArtist:
    name: str  # Last.fm'in kanonik adı
    mbid: uuid.UUID | None


@dataclass(frozen=True)
class LfmSimilar:
    name: str
    mbid: uuid.UUID | None
    match: float  # 0–1, ham


def _mbid(v: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(v) if v else None
    except ValueError:
        return None


class LastfmClient:
    def __init__(self, http: SourceClient, base_url: str, api_key: str) -> None:
        if not api_key:
            raise ValueError("LASTFM_API_KEY zorunlu")
        self._http = http
        self._base = base_url
        self._key = api_key

    def _call(
        self, method: str, name: str | None, mbid: uuid.UUID | None, **extra: str
    ) -> dict | None:
        params = {"method": method, "api_key": self._key, "format": "json", "autocorrect": "1"}
        if mbid is not None:
            params["mbid"] = str(mbid)
        elif name:
            params["artist"] = name
        else:
            raise ValueError("ad veya mbid gerekli")
        params.update(extra)
        data = self._http.get_json(self._base, params)
        if data is None:
            return None
        if "error" in data:
            if data["error"] == _NOT_FOUND:
                return None
            raise SourceError(f"Last.fm hata {data['error']}")
        return data

    def get_info(self, name: str | None = None, mbid: uuid.UUID | None = None) -> LfmArtist | None:
        data = self._call("artist.getInfo", name, mbid)
        art = (data or {}).get("artist")
        if not art or not art.get("name"):
            return None
        return LfmArtist(art["name"], _mbid(art.get("mbid")))

    def get_top_tags(
        self, name: str | None = None, mbid: uuid.UUID | None = None
    ) -> list[tuple[str, int]]:
        """(küçük harf etiket, oy 0–100) çiftleri, oya göre azalan; sanatçı yoksa boş."""
        data = self._call("artist.getTopTags", name, mbid)
        out: list[tuple[str, int]] = []
        for t in ((data or {}).get("toptags") or {}).get("tag") or []:
            tag = (t.get("name") or "").strip().lower()
            if tag:
                out.append((tag, int(t.get("count") or 0)))
        return out

    def get_similar(
        self, name: str | None = None, mbid: uuid.UUID | None = None, limit: int = 20
    ) -> list[LfmSimilar]:
        data = self._call("artist.getSimilar", name, mbid, limit=str(limit))
        items = ((data or {}).get("similarartists") or {}).get("artist") or []
        out = []
        for a in items:
            try:
                out.append(LfmSimilar(a["name"], _mbid(a.get("mbid")), float(a["match"])))
            except (KeyError, ValueError, TypeError):
                continue
        return out
