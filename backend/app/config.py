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
    # Kenar deposu (S3): komşu üst sınırı, genişleme derinliği, boyut uyarısı/üst sınırı (bayt).
    # Last.fm kullanım sınırı: 100 MB altı (CLAUDE.md); 80 MB'ta uyarılır.
    edge_max_neighbors: int = 20
    expand_depth: int = 2
    edge_source: str = "lastfm"
    edge_warn_bytes: int = 80 * 1024 * 1024
    edge_max_bytes: int = 100 * 1024 * 1024
    # Matris ve komşuluk (S4). Simetrikleştirme: max | mean; normalizasyon: sym | row | none.
    graph_algo_version: str = "graph-1"
    edge_min_weight: float = 0.0
    matrix_symmetrize: str = "max"
    matrix_normalization: str = "sym"
    neighborhood_max_depth: int = 2
    neighborhood_top_k: int = 20
    neighborhood_fanout: int = 10  # derinlik 2'de genişletilen en güçlü derinlik-1 komşu sayısı


class ProfileSettings(BaseSettings):
    """Oy skoru / profil parametreleri; gömülü sabit yok. Ortamdan PROFILE_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PROFILE_", extra="ignore")

    profile_algo_version: str = "profile-1"
    # Soğuk başlangıç skorları (CLAUDE.md oylama ölçeği)
    vote_scores: dict[int, float] = {1: -1.0, 2: -0.6, 3: -0.15, 4: 0.35, 5: 0.7, 6: 1.0}
    # Persentil normalizasyonu: en az bu kadar güncel oydan sonra devreye girer; işaret korunur,
    # her işaret grubunda mid-rank persentil, soğuk başlangıç aralığına yayılır ve harmanlanır.
    normalize_min_votes: int = 30
    normalize_blend: float = 0.5  # 0 = yalnız soğuk skor, 1 = yalnız persentil
    # Zaman sönümü: ağırlık = 0.5 ** (yaş_gün / yarı_ömür), tabanın altına inmez.
    decay_half_life_days: float = 365.0
    decay_floor: float = 0.25
    decay_exempt_votes: tuple[int, ...] = (1,)  # Awful sönmez (sert filtre)
    # Profil anlık görüntüsü (S2): çapa oyu, kaçınma, kümeleme (tohum sabit -> deterministik).
    anchor_vote: int = 6  # Amazing
    hard_avoid_votes: tuple[int, ...] = (1,)  # Awful: kaçınma bölgesinde "sert" işaretlenir
    # k = min(cluster_count, sanatçı sayısı // cluster_min_artists)
    cluster_count: int = 8
    cluster_min_artists: int = 3
    cluster_seed: int = 0
    cluster_n_init: int = 10


@lru_cache
def get_profile_settings() -> ProfileSettings:
    return ProfileSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_graph_settings() -> GraphSettings:
    return GraphSettings()
