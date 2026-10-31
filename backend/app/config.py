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

    profile_algo_version: str = "profile-2"
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
    # Unheard (Faz 5 S1): bu kadar sunumda oy gelmezse süresi dolar ve zayıf örtük negatif sayılır.
    unheard_expire_after: int = 3
    unheard_expired_score: float = -0.05
    # Aktif öğrenme kuyruğu (Faz 5 S2)
    queue_algo_version: str = "queue-2"
    active_unknown_uncertainty: float = 0.75  # sinyali olmayan sanatçı için belirsizlik
    active_pool_bonus: float = 0.5  # Unheard havuzundaki parçanın sıralama bonusu
    # Oylama kuyruğu (Faz 4 S1)
    queue_size: int = 20
    queue_max_size: int = 100


class RecommendSettings(BaseSettings):
    """Aday skoru (PPR) parametreleri; gömülü sabit yok. Ortamdan RECOMMEND_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RECOMMEND_", extra="ignore")

    recommend_algo_version: str = "recommend-1"
    # PPR: r = (1 - alpha) * Σ_k alpha^k S^k e (kesik kuvvet serisi; çapa başına doğrusal)
    ppr_alpha: float = 0.7
    ppr_iterations: int = 8
    max_seeds: int = 200  # pozitif tohum üst sınırı (en yüksek ağırlık)
    max_negative_seeds: int = 100  # Bad cezası için negatif tohum üst sınırı
    anchor_boost: float = 1.5  # çapa (Amazing) tohum ağırlığı çarpanı
    bad_penalty_beta: float = 0.5  # negatif tohum ağırlığı = -beta * kaçınma gücü
    # nihai skor = ham * (1 + gamma * yenilik); yenilik = 1 - derece persentili
    novelty_gamma: float = 0.4
    candidate_top_n: int = 100
    reason_count: int = 3
    list_algo_version: str = "list-2"
    list_size: int = 20
    mmr_lambda: float = 0.6  # 1 = yalnız alaka, 0 = yalnız çeşitlilik
    # Slot dağılımı (Faz 5 S3): Thompson sampling
    slot_prior_shares: dict[str, float] = {"familiar": 0.4, "unheard": 0.35, "explore": 0.25}
    slot_prior_a: float = 1.0  # Beta öncülü (başarı)
    slot_prior_b: float = 1.0  # Beta öncülü (başarısızlık)
    slot_floor_share: float = 0.1  # her slotun taban payı
    bandit_min_outcomes: int = 10  # bundan az sonuçta pay öncüle eşit
    familiar_fraction: float = 0.5  # havuzsuz adayların üst kesri = familiar, kalanı explore


class ReleasesSettings(BaseSettings):
    """Yayın tespiti parametreleri. Ortamdan RELEASES_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RELEASES_", extra="ignore")

    window_days: int = 120  # tespit penceresi: bugünden geriye
    refetch_days: int = 7  # aynı sanatçı için yeniden sorgu aralığı
    search_limit: int = 25  # sanatçı başına en çok yayın
    types: tuple[str, ...] = ("album", "ep", "single")


@lru_cache
def get_releases_settings() -> ReleasesSettings:
    return ReleasesSettings()


@lru_cache
def get_recommend_settings() -> RecommendSettings:
    return RecommendSettings()


@lru_cache
def get_profile_settings() -> ProfileSettings:
    return ProfileSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_graph_settings() -> GraphSettings:
    return GraphSettings()
