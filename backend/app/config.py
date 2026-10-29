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

    @field_validator("spotify_redirect_uri", "spotify_scopes", mode="before")
    @classmethod
    def _empty_means_default(cls, v, info):
        """Şablondan gelen boş satırlar varsayılanı ezmesin."""
        return cls.model_fields[info.field_name].default if v == "" else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
