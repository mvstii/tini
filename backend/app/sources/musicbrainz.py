"""MusicBrainz istemcisi: ISRC → kayıt → sanatçı kredileri."""
import uuid
from dataclasses import dataclass
from datetime import date

from app.sources.http import SourceClient


@dataclass(frozen=True)
class MbArtist:
    mbid: uuid.UUID
    name: str  # MusicBrainz'in kanonik adı


@dataclass(frozen=True)
class MbRecording:
    mbid: uuid.UUID
    artists: tuple[MbArtist, ...]  # kredi sırasıyla


class MusicBrainzClient:
    def __init__(self, http: SourceClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def lookup_isrc(self, isrc: str) -> MbRecording | None:
        """ISRC'ye bağlı ilk kaydı döndürür; yoksa None."""
        data = self._http.get_json(
            f"{self._base}/isrc/{isrc}", {"fmt": "json", "inc": "artist-credits"}
        )
        if not data:
            return None
        for rec in data.get("recordings") or []:
            artists = tuple(
                MbArtist(uuid.UUID(c["artist"]["id"]), c["artist"]["name"])
                for c in rec.get("artist-credit") or []
                if c.get("artist", {}).get("id") and c["artist"].get("name")
            )
            if artists:
                return MbRecording(uuid.UUID(rec["id"]), artists)
        return None

    def artist_isrcs(self, artist_mbid: uuid.UUID, limit: int) -> list[tuple[str, uuid.UUID]]:
        """Sanatçının kayıtlarından (ISRC, kayıt MBID) çiftleri; ISRC'siz kayıt atlanır."""
        # Tarama ucu (`recording?artist=`) kayıtların ~%2'sinde ISRC döndürür; arama ucu yalnızca
        # ISRC'li kayıtları getirir (gerçek yanıtla doğrulandı, 4 Kasım 2026).
        data = self._http.get_json(
            f"{self._base}/recording",
            {"query": f"arid:{artist_mbid} AND isrc:*", "fmt": "json", "limit": str(limit)},
        )
        return parse_artist_isrcs(data)

    def release_groups(
        self, artist_mbid: uuid.UUID, since: date, until: date, types: tuple[str, ...], limit: int
    ) -> list["MbReleaseGroup"]:
        """[since, until] aralığındaki yayınlar (Lucene arama ucu; sanatçı başına tek istek)."""
        kinds = " OR ".join(f"primarytype:{t}" for t in types)
        query = (
            f"arid:{artist_mbid} AND firstreleasedate:[{since.isoformat()} TO "
            f"{until.isoformat()}] AND ({kinds})"
        )
        data = self._http.get_json(
            f"{self._base}/release-group", {"query": query, "fmt": "json", "limit": str(limit)}
        )
        return parse_release_groups(data, types)


@dataclass(frozen=True)
class MbReleaseGroup:
    mbid: uuid.UUID
    title: str
    primary_type: str  # küçük harf: album | ep | single ...
    first_release_date: date  # yalnızca tam gün hassasiyetli kayıtlar
    artist_mbids: tuple[uuid.UUID, ...]  # kredi sırasıyla


def parse_release_groups(data: dict | None, types: tuple[str, ...]) -> list[MbReleaseGroup]:
    """Arama yanıtından tam tarihli ve izinli türdeki yayınlar. Kısmi/eksik tarih atlanır."""
    out: list[MbReleaseGroup] = []
    for g in (data or {}).get("release-groups") or []:
        raw = g.get("first-release-date") or ""
        ptype = (g.get("primary-type") or "").lower()
        if len(raw) != 10 or ptype not in types or not g.get("id") or not g.get("title"):
            continue
        try:
            when = date.fromisoformat(raw)
        except ValueError:
            continue
        credits = tuple(
            uuid.UUID(c["artist"]["id"])
            for c in g.get("artist-credit") or []
            if c.get("artist", {}).get("id")
        )
        out.append(MbReleaseGroup(uuid.UUID(g["id"]), g["title"], ptype, when, credits))
    return out



def parse_artist_isrcs(data: dict | None) -> list[tuple[str, uuid.UUID]]:
    out: list[tuple[str, uuid.UUID]] = []
    seen: set[str] = set()
    for rec in (data or {}).get("recordings") or []:
        for isrc in rec.get("isrcs") or []:
            if len(isrc) == 12 and isrc not in seen and rec.get("id"):
                seen.add(isrc)
                out.append((isrc, uuid.UUID(rec["id"])))
                break  # kayıt başına tek ISRC
    return out
