from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tek yapılandırma noktası (ortam / .env); algoritma parametreleri de buraya eklenir."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tini:tini@localhost:5432/tini"
    session_ttl_days: int = 30
    # Fernet anahtarı (servis kimlik bilgilerini şifreler); .env'den gelir.
    credential_key: str = ""
    spotify_client_id: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8000/connect/spotify/callback"
    spotify_scopes: str = (
        "user-library-read user-top-read user-read-recently-played "
        "playlist-modify-private playlist-read-private"
    )
    # Spotify yanıtlarının kullanıcıya özel önbellek ömrü (saniye); başlangıç 24 saat.
    spotify_cache_ttl_seconds: int = 86400

    # MusicBrainz User-Agent'ı iletişim bilgisi ister (.env: MUSICBRAINZ_CONTACT).
    musicbrainz_contact: str = ""
    # Last.fm API anahtarı; yalnızca .env'den gelir, loglanmaz.
    lastfm_api_key: str = ""

    @field_validator("spotify_redirect_uri", "spotify_scopes", mode="before")
    @classmethod
    def _empty_means_default(cls, v, info):
        """Şablondan gelen boş satırlar varsayılanı ezmesin."""
        return cls.model_fields[info.field_name].default if v == "" else v


class GraphSettings(BaseSettings):
    """Katalog/grafik parametreleri; gömülü sabit yok. Ortamdan GRAPH_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="GRAPH_", extra="ignore")

    # Kaynak istemcisi (sources/http.py)
    musicbrainz_base_url: str = "https://musicbrainz.org/ws/2"
    musicbrainz_min_interval_seconds: float = 1.0
    http_max_retries: int = 4
    http_backoff_base_seconds: float = 2.0
    http_backoff_max_seconds: float = 60.0
    lastfm_base_url: str = "https://ws.audioscrobbler.com/2.0/"
    lastfm_min_interval_seconds: float = 0.25
    # Kademe B güveni: ad eşitliği, bulanık benzerlik ağırlığı, MBID bonusu; eşik altı bağlanmaz.
    tier_b_exact_confidence: float = 0.8
    tier_b_fuzzy_weight: float = 0.7
    tier_b_mbid_bonus: float = 0.1
    tier_b_min_confidence: float = 0.6
    # Kademe A eşleme güveni ve negatif önbellek ömürleri (saniye)
    tier_a_confidence: float = 0.95
    fetch_ok_ttl_seconds: int = 30 * 86400
    fetch_empty_ttl_seconds: int = 7 * 86400
    fetch_error_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_graph_settings() -> GraphSettings:
    return GraphSettings()
