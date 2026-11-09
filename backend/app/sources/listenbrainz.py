"""ListenBrainz kaynak istemcisi (tür omurgası, PR-4): etiketten kayıt havuzu, sanatçının en çok
dinlenen kayıtları ve kayıt MBID → ISRC/sanatçı çözümü. Yalnızca bu modül ListenBrainz'e çıkar."""
import uuid
from dataclasses import dataclass

from app.sources.http import SourceClient


@dataclass(frozen=True)
class LbRecording:
    """Kayıt meta verisi (ListenBrainz /metadata/recording)."""

    mbid: str
    title: str | None
    artist_name: str | None
    artist_mbid: str | None
    isrcs: tuple[str, ...]


def _records(body: object) -> list[dict]:
    """lb-radio yanıtı liste ya da {'payload'|'recordings'|'data': [...]} olabilir."""
    if isinstance(body, list):
        return [r for r in body if isinstance(r, dict)]
    if isinstance(body, dict):
        for key in ("payload", "recordings", "data"):
            v = body.get(key)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
            if isinstance(v, dict):
                for kk in ("recordings", "data", "payload"):
                    if isinstance(v.get(kk), list):
                        return [r for r in v[kk] if isinstance(r, dict)]
    return []


def parse_radio(body: object) -> list[str]:
    """lb-radio/tags yanıtından benzersiz kayıt MBID'leri (sıra korunur)."""
    seen: dict[str, None] = {}
    for r in _records(body):
        m = r.get("recording_mbid")
        if isinstance(m, str) and m:
            seen.setdefault(m, None)
    return list(seen)


def parse_top_recordings(body: object, k: int) -> list[tuple[str, int]]:
    """top-recordings-for-artist yanıtından en çok dinlenen k (kayıt MBID, dinlenme) çifti."""
    rows = [
        (r["recording_mbid"], int(r.get("total_listen_count") or 0))
        for r in _records(body)
        if isinstance(r.get("recording_mbid"), str) and r["recording_mbid"]
    ]
    rows.sort(key=lambda x: (-x[1], x[0]))
    return rows[:k]


def parse_metadata(body: object) -> dict[str, LbRecording]:
    """metadata/recording yanıtı ({mbid: {recording, artist, ...}}) → kayıt sözlüğü."""
    out: dict[str, LbRecording] = {}
    if not isinstance(body, dict):
        return out
    for mbid, e in body.items():
        if not isinstance(e, dict):
            continue
        art = e.get("artist") if isinstance(e.get("artist"), dict) else {}
        rec = e.get("recording") if isinstance(e.get("recording"), dict) else {}
        credits = art.get("artists") if isinstance(art.get("artists"), list) else []
        first = credits[0] if credits and isinstance(credits[0], dict) else {}
        isrcs = tuple(
            i for i in (rec.get("isrcs") or []) if isinstance(i, str) and len(i) == 12
        )
        out[mbid] = LbRecording(
            mbid=mbid,
            title=rec.get("name"),
            artist_name=art.get("name") or first.get("name"),
            artist_mbid=first.get("artist_mbid"),
            isrcs=isrcs,
        )
    return out


class ListenBrainzClient:
    def __init__(self, http: SourceClient, base_url: str, token: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._token = token  # yalnızca Authorization başlığında; loglanmaz

    def radio_tags(self, tag: str, count: int, pop_begin: int = 0, pop_end: int = 100) -> list[str]:
        """Etiketle kayıt havuzu (anonim). pop_begin/pop_end: 0 en çok dinlenen yüzdelik ucu."""
        data = self._http.get_json(
            f"{self._base}/lb-radio/tags",
            {
                "tag": tag, "operator": "OR", "pop_begin": str(pop_begin),
                "pop_end": str(pop_end), "count": str(count),
            },
        )
        return parse_radio(data)

    def top_recordings(self, artist_mbid: uuid.UUID | str, k: int) -> list[tuple[str, int]]:
        """Sanatçının en çok dinlenen k kaydı (belirteç gerekir)."""
        data = self._http.get_json(
            f"{self._base}/popularity/top-recordings-for-artist/{artist_mbid}",
            headers=self._auth(),
        )
        return parse_top_recordings(data, k)

    def recordings(self, mbids: list[str]) -> dict[str, LbRecording]:
        """Kayıt MBID → meta/ISRC (belirteç gerekir). Çağıran en çok `backbone_meta_batch` verir."""
        if not mbids:
            return {}
        data = self._http.post_json(
            f"{self._base}/metadata/recording/",
            {"recording_mbids": mbids, "inc": "artist tag"},
            headers=self._auth(),
        )
        return parse_metadata(data)

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Token {self._token}"}
