# Tını — Güncel Durum

Son güncelleme: 30 Ekim 2026 · Her aşama (PR) sonrasında güncellenir.

## Özet

- **Faz:** Faz 1 tamamlandı; güncel faz Faz 2 — Katalog ve benzerlik grafiği (plan: `docs/FAZ2_PLAN.md`; S1, S2 birleşti, S3 PR'da, sırada S4).
- **Faz 1 kapısı geçildi (30 Ekim 2026):** emülatörde hesap açıldı, Spotify bağlandı, kütüphane aktarıldı (531 bağlantı, 524 parça veritabanında).
- **Faz 0:** tamamlandı. Kalan kullanıcı işleri: partners@last.fm'e izin e-postası, `.env.example` şablonunu geri koymak, Spotify'daki "tini-spike" ve "tini-spike-2" çalma listelerini silmek.

## Faz 1 aşamaları

| # | Aşama | Durum | PR |
|---|---|---|---|
| 1 | Backend iskeleti, Docker Compose (Postgres + pgvector), CI | Bitti | #2 |
| 2 | Veri modeli ve ilk Alembic göçü | Bitti | #3 |
| 3 | Hesap sistemi (e-posta + parola, oturum) | Bitti | #4 |
| 4 | Spotify OAuth (PKCE), şifreli servis bağlantısı | Bitti; gerçek Spotify ile doğrulandı (30 Ekim 2026), token'lar veritabanında şifreli | #5 |
| 5 | Servis adaptörü arayüzü + Spotify adaptörü (kütüphane okuma, token yenileme) | Bitti; gerçek hesapla doğrulandı (531 parça, 1 atlandı) | #6 |
| 6 | Kütüphane içe aktarma (`POST /library/import`; kaydedilenler + top items) | Bitti; gerçek hesapla doğrulandı (524 parça, 531 bağlantı, 1 atlandı; meta TTL 24 sa) | #7 |
| 7 | Flutter iskeleti (giriş, servis bağlama, boş oylama ekranı) | Bitti; analyze + 4 test geçti, Android emülatöründe uçtan uca doğrulandı | #8 |

## Faz 2 aşamaları

| # | Aşama | Durum | PR |
|---|---|---|---|
| S1 | Kaynak altyapısı + MusicBrainz + kademe A (göç 0004 sanatçı tabloları, `catalog.resolve`, `python -m app.jobs.enrich`) | Kod ve birim testler hazır (46 testten 45 geçiyor); gerçek MusicBrainz ile doğrulandı (30 Ekim 2026, 20 parça: 10 eşleşti, 10 boş, 0 hata → %50) | #12 |

| S2 | Last.fm + kademe B/C + güven (`sources/lastfm.py`, `catalog/resolve_b.py`, `catalog/confidence.py`) | Kod ve birim testler hazır (59 test geçiyor, 1 eski hata); gerçek Last.fm ile ölçüldü (30 Ekim 2026) | #13 |

**S2 ölçümü (524 parça, tek kişinin sahnesi):** A (ISRC→MusicBrainz) 252 (%48) · B (Last.fm, ad) 271 (%52) · C (eşleşmedi) 1 (%0,2). 246 sanatçı, 63'ü MBID'siz (yalnızca Last.fm kimliği). Düşük güvenli (<0,8) B eşleşmeleri incelendi; hepsi doğru (Türkçe `ı`/`i` farkı). Bu yüzden `normalize_name` `ı`'yı `i`'ye katlıyor (kaydedilmiş `name_norm` yeniden hesaplandı). Çok yüksek B oranı Last.fm'in ad aramasının cömertliğini gösterir; B bağları adın doğruluğuna dayanır ve ISRC'ye göre daha zayıftır (güven 0,6–0,9). Genellenmez.

| S3 | Kenar deposu + tembel genişleme (göç 0005 `artist_edge`/`graph_snapshot`, saf `graph.expansion.plan_expansion`, `python -m app.jobs.expand`) | Kod ve testler hazır (73 test geçiyor, 1 eski hata); gerçek Last.fm ile ölçüldü (30 Ekim 2026) | S3 PR'ı |

**S3 ölçümü (246 çapa sanatçı, derinlik 1):** 224 sanatçının kenarı var, 22'si Last.fm'de boş; 4376 kenar, 2210 farklı komşu, ortalama ağırlık 0,565, tablo 776 kB (100 MB sınırının çok altında). Tekrar çalıştırmada önbellek isabeti %100, 0 çağrı. Derinlik 2 tahmini: ~2200 yeni sanatçı çağrısı (≈20 dk, 0,25 sn aralık), ~40–50 bin kenar, ~4 MB. Derinlik 2 henüz tam çalıştırılmadı; S4 öncesinde çalıştırılacak.

S3 notları: Kenar kaynağı `artist_edge.source` (şimdilik `lastfm`). Komşu başına üst sınır 20 (`GraphSettings.edge_max_neighbors`). Genişleme `fetch_log` kaynağı `lastfm_similar`, anahtar `artist:<id>` (kademe B'nin `lastfm`/`track:` anahtarlarından ayrı). Boyut: 80 MB uyarı, 100 MB üstünde en eski kenarlar atılır (silme boyutu hemen küçültmez, bu yüzden atılacak satır sayısı orantılanır). Bilinen sınır: önbellek durumu belleğe yüklenir; yüzbinlerce kenarda Faz 3'te sayfalanmalı. Adı olan ama MBID'si olmayan komşu, başka yoldan gelen aynı sanatçıyla ayrı satır olabilir (MBID çelişkisi riskine karşı bilerek birleştirilmiyor).

S2 notları: Kademe B bağı yalnızca `user_track_artist`'te; `track.artist_id` değişmez. Güven eşiği 0.6 (`GraphSettings`). `fetch_log` Last.fm anahtarı `track:<id>` (Spotify dizesi içermez). Last.fm API anahtarı URL'de gittiği için enrich işi httpx INFO loglarını susturur.

S1 notları: `fetch_log` anahtarı `(source, key)` (ör. `isrc:…`), plandaki `(artist_id, source)` yerine; ISRC aramasında henüz sanatçı yok. Çok sanatçılı kayıtta ilk kredi alınır. Ortam dosyasına `MUSICBRAINZ_CONTACT` gerekir; yoksa içe aktarma sonrası arka plan işi çalışmaz.
Gerçek doğrulama: göç 0004 uygulandı; hesapsız, yalnızca `User-Agent` ile çalıştı, 429 görülmedi. Tüm kütüphane çalıştırıldı (30 Ekim 2026): 524 parçadan 252'si MusicBrainz'de eşleşti (%48, 114 sanatçı), 272'si boş (kademe B/C adayı), 0 hata, 429 yok. Plandaki ~%28 beklentisinden yüksek; ölçüm tek kişinin sahnesine ait, genellenmez.
`tests/test_models.py::test_account_delete_removes_personal_data_only` geliştirme veritabanındaki gerçek verilerle (tüm `user_track_link` satırlarını sayar) başarısız; S1'den önce de böyle, ayrı düzeltilecek.

## Ortam

- Windows 11, Python 3.12, Docker Desktop 4.97, Flutter 3.47.9 (`C:\dev\flutter`, PATH'te değil).
- Yerel çalıştırma: `docker compose up -d db`, ardından `backend` içinde `alembic upgrade head` ve `pytest`.
- Android toolchain (`flutter doctor`) henüz denetlenmedi; Aşama 7'den önce yapılacak.

## Alınan kararlar (Faz 1)

- Spotify'dan gelen başlık/sanatçı/süre yalnızca kullanıcıya özel TTL'li önbellekte (`user_track_meta`); paylaşılan katalogda yalnızca ISRC/MBID ve türetilmiş veri (29 Ekim 2026, onaylı).
- Oturumlar rastgele değerdir; veritabanında yalnızca SHA-256 özeti saklanır. Parolalar argon2.
- `vote_event` tablosunda UPDATE veritabanı tetikleyicisiyle engelli.
- Hibrit grafik modeli: PPR sanatçı düğümlerinde; Last.fm izni gelmeden üretim bağımlılığı sayılmaz (ayrıntı `docs/ARCHITECTURE.md`).

## Yerel kurulum notları

- Spotify dashboard'da redirect URI'ler: `http://127.0.0.1:8000/connect/spotify/callback` (backend) ve `http://127.0.0.1:8888/callback` (Faz 0 betikleri). Eklerken Add ve ardından Save gerekir.
- `.env` içinde `SPOTIFY_CLIENT_ID` ve `CREDENTIAL_KEY` (Fernet anahtarı) tanımlı olmalı; anahtar kaybolursa kayıtlı token'lar çözülemez.
- Boş `.env` satırları (ör. `SPOTIFY_REDIRECT_URI=`) varsayılana düşer.

## Açık riskler

- Last.fm ticari izni gelmeyebilir; yedek: ListenBrainz + kendi birlikte-oluşum matrisi.
- Apple Music Android SDK ve Flutter bağlayıcısı doğrulanmadı (Faz 7 öncesi kontrol).
- Spotify Şubat 2026 duyurusu okunmadı.
- Faz 0 örneği tek kişinin müzik sahnesi; kapsam sayıları genellenmeyebilir.
