"""Servis bağımsız adaptör arayüzü. Çekirdek yalnızca bu tipleri bilir; servis adı geçmez."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LibraryTrack:
    external_id: str
    isrc: str
    title: str
    artist_names: tuple[str, ...]
    duration_ms: int | None = None
    image_url: str | None = None  # kapak görseli; yalnızca kullanıcıya özel TTL önbelleğine girer


@dataclass
class Library:
    tracks: list[LibraryTrack] = field(default_factory=list)
    # Boş metadata veya ISRC'siz kayıtlar atlanır ve burada sayılır (işaretlenir).
    skipped: int = 0


class MusicServiceAdapter(Protocol):
    service: str

    def read_library(self, max_tracks: int = 500) -> Library:
        """Kaydedilen şarkılar ve en çok dinlenenler; tekilleştirilmiş."""

    def create_playlist(self, name: str, external_ids: list[str]) -> str:
        """Özel liste oluşturur, şarkıları ekler, liste kimliğini döndürür."""

    def find_track(self, isrc: str) -> str | None:
        """ISRC'den servis parça kimliği (create_playlist girdisi); bulunamazsa None."""

    def find_artist_track(self, artist_name: str) -> str | None:
        """Sanatçının servisteki bir parçasının kimliği (ISRC'siz öğeler için); bulunamazsa None."""

    def open_url(self, isrc: str | None, artist_name: str) -> tuple[str, str]:
        """Servis uygulamasında açılacak bağlantı: ("track", url) ya da ("search", url) yedeği.

        Hiçbir kimlik saklanmaz; çağıran yalnızca sonucu istemciye iletir."""
