from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tek yapılandırma noktası (ortam / .env); algoritma parametreleri de buraya eklenir."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tini:tini@localhost:5432/tini"
    session_ttl_days: int = 30
    # "prod" iken /docs ve /openapi.json kapalıdır (.env: APP_ENV).
    app_env: str = "dev"
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
    # ListenBrainz kullanıcı belirteci (omurga işi); yalnızca ortamdan gelir, loglanmaz.
    listenbrainz_token: str = ""
    # Aşama süreleri: Server-Timing başlığı + istek günlüğünde `stages` (salt ölçüm).
    server_timing_enabled: bool = True
    # Dış servis 429/5xx iken istemciye 503 ile döndürülen varsayılan Retry-After (saniye).
    upstream_retry_after_seconds: int = 30

    @field_validator("spotify_redirect_uri", "spotify_scopes", mode="before")
    @classmethod
    def _empty_means_default(cls, v, info):
        """Şablondan gelen boş satırlar varsayılanı ezmesin."""
        return cls.model_fields[info.field_name].default if v == "" else v


class AuthSettings(BaseSettings):
    """Giriş/kayıt hız sınırı eşikleri; ortamdan AUTH_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AUTH_", extra="ignore")

    login_email_limit: int = 5
    login_ip_limit: int = 20
    login_window_seconds: int = 900
    register_ip_limit: int = 10
    register_window_seconds: int = 3600


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
    # ListenBrainz (sources/listenbrainz.py): sınır 30 istek/10 sn; 0,34 sn aralık güvenli.
    listenbrainz_base_url: str = "https://api.listenbrainz.org/1"
    listenbrainz_min_interval_seconds: float = 0.34
    # Tür omurgası (PR-4): kullanıcıdan bağımsız alt tür → temsilci parça havuzu. Canlıda kapalı.
    backbone_enabled: bool = False
    backbone_top_k: int = 10  # sanatçının en çok dinlenen K kaydından tohumlu örnek
    backbone_artists_per_sub_genre_cap: int = 60
    backbone_pool_count: int = 1000  # lb-radio/tags istek başına kayıt (anonim, üst sınır 1000)
    # Dinlenme yüzdeliği pencereleri (ListenBrainz pop_begin/pop_end; 0 = en çok dinlenen):
    # top [0, top_end), mid [top_end, mid_end), tail [mid_end, 100].
    backbone_top_end: int = 33
    backbone_mid_end: int = 66
    backbone_meta_batch: int = 200  # LB metadata/recording isteği başına MBID
    # Ağır iş yürütücüsü (jobs/worker.py)
    worker_queue_max: int = 50
    # Stale-while-revalidate: eski matris/etiket sunulur, yenisi arka planda kurulur
    swr_enabled: bool = False
    # Tür etiketleri (catalog/tags.py)
    tag_max_per_artist: int = 8
    tag_min_weight: int = 20  # 0–100; altı gürültü sayılır
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
    # Otomatik genişleme (sunucu içi, Render'da ayrı cron yok) ve parça kapsaması (MusicBrainz).
    auto_expand: bool = True
    auto_expand_hours: int = 6  # turlar arası süre
    auto_expand_delay_seconds: int = 120  # açılıştan ilk tura kadar bekleme
    auto_expand_idle_seconds: int = 30  # son kullanıcı isteğinden sonra tur için sessizlik
    auto_expand_idle_max_wait: int = 900  # sessizlik gelmezse en çok bu kadar bekle, sonra çalıştır
    auto_expand_limit: int = 60  # tur başına Last.fm sanatçı çekimi
    auto_tracks_limit: int = 15  # tur başına parça aranacak sanatçı (MusicBrainz, ~1 istek/sn)
    tracks_per_artist: int = 5  # sanatçı başına katalogla eklenen ISRC'li parça üst sınırı
    tracks_browse_limit: int = 25  # MusicBrainz ISRC'li kayıt aramasında istenen kayıt sayısı
    vote_neighbor_tracks: int = 5  # oy sonrası parçası aranacak komşu sanatçı sayısı
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

    profile_algo_version: str = "profile-4"
    # Tür eğilimi (PR-5): Good+/Bad- eşikleri ve Laplace yumuşatma (her türe bu kadar sahte Good).
    genre_good_min_vote: int = 4
    genre_bad_max_vote: int = 2
    genre_smoothing: float = 1.0
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
    # Beğeniler (kalp): oy almamış beğenilen parça zayıf, sönümlü örtük pozitif sayılır (vote=0).
    like_score: float = 0.25
    # Aktif öğrenme kuyruğu (Faz 5 S2)
    queue_algo_version: str = "queue-7"
    # Çeşitlilik (queue-7): son N parçadaki sanatçı/tür tekrar etmez; her `explore_every`'inci
    # yuva tohumlu rastgele keşif yuvasıdır (0 = kapalı).
    queue_artist_gap: int = 4
    queue_genre_gap: int = 2
    queue_explore_every: int = 4
    # Kuyruğa öneri motoru karışımı: kütüphane kalanı eşiğin altına inince öneriler eklenir;
    # her istekte en çok `batch` servis çağrısı; bu kadar yeni oydan sonra profil yenilenir.
    queue_suggest_threshold: int = 20
    queue_suggest_batch: int = 10
    queue_rebuild_after_votes: int = 5
    # Hızlı yol (PR-2): queue() yalnızca hazır olanı okur; pahalı işler arka planda tek uçuşla.
    # Hazır öneri sayısı `buffer_low_watermark` altına inince doldurucu `buffer_target`'a kadar
    # doldurur (partide en çok `refill_batch` servis çağrısı). Meta kaydı TTL'inin
    # `meta_refresh_at` oranına ulaşınca önceden tazelenir (partide en çok `meta_refresh_batch`).
    fast_queue_enabled: bool = False
    buffer_low_watermark: int = 8
    buffer_target: int = 20
    refill_batch: int = 10
    meta_refresh_at: float = 0.8
    meta_refresh_batch: int = 10
    refill_error_backoff_seconds: int = 60  # servis hatasından sonra bu kullanıcı için bekleme
    # Aynı şarkının sürümleri (remaster vb.) kuyrukta tek sayılır; bu sözcükleri içeren
    # parantez/tire eki başlıktan atılır. Canlı/remix/akustik ayrı şarkıdır.
    queue_version_markers: tuple[str, ...] = (
        "remaster", "mono", "stereo", "deluxe", "explicit", "radio edit",
        "single version", "album version", "bonus track", "feat", "ft", "featuring",
    )
    active_unknown_uncertainty: float = 0.75  # sinyali olmayan sanatçı için belirsizlik
    active_pool_bonus: float = 0.5  # Unheard havuzundaki parçanın sıralama bonusu
    # Oylama kuyruğu (Faz 4 S1)
    queue_size: int = 20
    # İstemcinin `recent` parametresi (PR-3): en çok bu kadar parça kimliği, aksi 422.
    queue_recent_max: int = 20
    queue_max_size: int = 100
    # Örnekleyici (PR-6, `queue-8`): kapalıyken queue-7 davranışı aynen korunur. Karışım sırası:
    # (kütüphane, mahalle önerisi, tür sondası, joker); olgunluk oy sayısına göre doğrusal geçiş.
    queue_sampler_enabled: bool = False
    queue_sampler_algo_version: str = "queue-8"
    queue_mix_warm: tuple[float, float, float, float] = (0.4, 0.1, 0.4, 0.1)
    queue_mix_mature: tuple[float, float, float, float] = (0.3, 0.4, 0.2, 0.1)
    queue_mix_warm_votes: int = 50
    queue_mix_mature_votes: int = 200
    queue_genre_epsilon: float = 0.3  # kalibrasyon hedefinde eşit dağılım payı
    queue_gumbel_tau: float = 0.5  # 0 = deterministik sıra
    queue_coverage_kappa: float = 1.0  # az gezilmiş hücre iyimserliği
    queue_sim_window: int = 3  # graf benzerlik penceresi (son N sanatçı)
    queue_sim_max: float = 0.85  # pencere içinde izin verilen en yüksek kosinüs
    queue_history_size: int = 200  # örnekleyicinin okuduğu maruziyet olayı üst sınırı
    # Rerank'e kaynak kotasının kaç katı aday verilir; 1 = yalnız sıralama (eleme yok).
    queue_oversample: int = 3


class RecommendSettings(BaseSettings):
    """Aday skoru (PPR) parametreleri; gömülü sabit yok. Ortamdan RECOMMEND_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RECOMMEND_", extra="ignore")

    recommend_algo_version: str = "recommend-1"
    daily_algo_version: str = "daily-1"  # günün şarkısı seçimi (tarih + kullanıcı tohumlu)
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
    list_algo_version: str = "list-5"
    list_size: int = 20
    mmr_lambda: float = 0.6  # 1 = yalnız alaka, 0 = yalnız çeşitlilik
    # Slot dağılımı (Faz 5 S3): Thompson sampling
    slot_prior_shares: dict[str, float] = {"familiar": 0.4, "unheard": 0.35, "explore": 0.25}
    slot_prior_a: float = 1.0  # Beta öncülü (başarı)
    slot_prior_b: float = 1.0  # Beta öncülü (başarısızlık)
    slot_floor_share: float = 0.1  # her slotun taban payı
    bandit_min_outcomes: int = 10  # bundan az sonuçta pay öncüle eşit
    # Tür bandit'i (PR-5): her ana tür bir kol, Beta(a0 + Good+, b0 + Bad-);
    # taban pay türün sıfırlanmasını önler
    genre_prior_a: float = 1.0
    genre_prior_b: float = 1.0
    genre_floor_share: float = 0.05
    familiar_fraction: float = 0.5  # havuzsuz adayların üst kesri = familiar, kalanı explore
    # Çeşitlilik: "uzak" yuva (bandit dışı sabit pay) ve tek topluluk tavanı
    far_share: float = 0.2
    far_pool_size: int = 1000  # uzak adaylar için geniş skor havuzu
    far_home_exclude: int = 2  # en çok sevilen bu kadar topluluk uzak sayılmaz
    max_cluster_share: float = 0.5
    use_genre_labels: bool = True  # etiketi olan sanatçıda topluluk yerine ana tür kullanılır
    community_count: int = 12
    community_seed: int = 0
    # Taze liste (Faz 5 S5): takip edilen sanatçıların son yayınları, albüm düzeyinde
    fresh_algo_version: str = "fresh-1"
    fresh_share: float = 0.12  # ana listede "Yeni" yuvasının sabit payı (bandit dışı)
    fresh_list_size: int = 15
    fresh_window_days: int = 30  # yalnız bu kadar gün içindeki yayınlar
    fresh_half_life_days: float = 14.0  # yenilik çarpanı yarılanma süresi
    eval_min_sample: int = 10  # değerlendirme raporunda bunun altındaki oranlar "yetersiz veri"


class ReleasesSettings(BaseSettings):
    """Yayın tespiti parametreleri. Ortamdan RELEASES_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RELEASES_", extra="ignore")

    window_days: int = 120  # tespit penceresi: bugünden geriye
    refetch_days: int = 7  # aynı sanatçı için yeniden sorgu aralığı
    search_limit: int = 25  # sanatçı başına en çok yayın
    types: tuple[str, ...] = ("album", "ep", "single")
    new_tracks_days: int = 7  # "Bu hafta çıkanlar" penceresi
    new_tracks_max_releases: int = 12  # tek istekte parça listesi çözülecek en çok yayın
    tracks_cache_hours: int = 6  # yayın parça listesi bellek önbelleği (kalıcı saklanmaz)
    cover_base_url: str = "https://coverartarchive.org"  # kapak URL'si üretimi (saklanmaz)
    auto_detect: bool = True # sunucu içinde periyodik yayın tespiti (Render'da ayrı cron yok)
    auto_detect_hours: int = 12  # tespit turları arası süre
    auto_detect_delay_seconds: int = 60  # açılıştan ilk tura kadar bekleme


class ArtworkSettings(BaseSettings):
    """Sanatçı fotoğrafı parametreleri. Ortamdan ARTWORK_ önekiyle ezilir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ARTWORK_", extra="ignore")

    enabled: bool = True  # kapalıysa fotoğraf çözülmez; istemci yer tutucu gösterir
    deezer_base_url: str = "https://api.deezer.com"
    deezer_min_interval_seconds: float = 0.25
    ttl_days: int = 14  # bulunan fotoğraf URL'sinin tazelik süresi
    miss_ttl_days: int = 3  # bulunamayanı yeniden deneme aralığı
    fill_limit: int = 8  # tek istekte en çok kaç sanatçı sorgulanır
    preview_enabled: bool = True  # kapalıysa /preview boş döner; istemci dinle düğmesini gizler


@lru_cache
def get_artwork_settings() -> ArtworkSettings:
    return ArtworkSettings()


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
