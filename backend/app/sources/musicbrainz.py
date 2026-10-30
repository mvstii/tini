"""MusicBrainz istemcisi: ISRC → kayıt → sanatçı kredileri."""
import uuid
from dataclasses import dataclass

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
