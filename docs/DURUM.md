# Tını — Güncel Durum

Son güncelleme: 30 Ekim 2026 · Her aşama (PR) sonrasında güncellenir.

## Özet

- **Faz:** 1 — Temel altyapı (9–22 Kasım). Kapı: kullanıcı hesap açıp Spotify'ı bağlayabilir, kütüphanesi veritabanına iner.
- **Faz 0:** tamamlandı. Kalan kullanıcı işleri: partners@last.fm'e izin e-postası, `.env.example` şablonunu geri koymak, Spotify'daki "tini-spike" ve "tini-spike-2" çalma listelerini silmek.

## Faz 1 aşamaları

| # | Aşama | Durum | PR |
|---|---|---|---|
| 1 | Backend iskeleti, Docker Compose (Postgres + pgvector), CI | Bitti | #2 |
| 2 | Veri modeli ve ilk Alembic göçü | Bitti | #3 |
| 3 | Hesap sistemi (e-posta + parola, oturum) | Bitti | #4 |
| 4 | Spotify OAuth (PKCE), şifreli servis bağlantısı | Kodlandı, PR bekliyor; gerçek Spotify ile denenmedi | — |
| 5 | Servis adaptörü arayüzü + Spotify adaptörü (kütüphane okuma) | Bekliyor | — |
| 6 | Kütüphane içe aktarma (kaydedilenler + top items) | Bekliyor | — |
| 7 | Flutter iskeleti (giriş, servis bağlama, boş oylama ekranı) | Bekliyor | — |

## Ortam

- Windows 11, Python 3.12, Docker Desktop 4.97, Flutter 3.47.9 (`C:\dev\flutter`, PATH'te değil).
- Yerel çalıştırma: `docker compose up -d db`, ardından `backend` içinde `alembic upgrade head` ve `pytest`.
- Android toolchain (`flutter doctor`) henüz denetlenmedi; Aşama 7'den önce yapılacak.

## Alınan kararlar (Faz 1)

- Spotify'dan gelen başlık/sanatçı/süre yalnızca kullanıcıya özel TTL'li önbellekte (`user_track_meta`); paylaşılan katalogda yalnızca ISRC/MBID ve türetilmiş veri (29 Ekim 2026, onaylı).
- Oturumlar rastgele değerdir; veritabanında yalnızca SHA-256 özeti saklanır. Parolalar argon2.
- `vote_event` tablosunda UPDATE veritabanı tetikleyicisiyle engelli.
- Hibrit grafik modeli: PPR sanatçı düğümlerinde; Last.fm izni gelmeden üretim bağımlılığı sayılmaz (ayrıntı `docs/ARCHITECTURE.md`).

## Kullanıcıdan beklenenler (Aşama 4)

- Spotify dashboard'da redirect URI olarak `http://127.0.0.1:8000/connect/spotify/callback` ekle.
- `.env` içine `SPOTIFY_CLIENT_ID` ve `CREDENTIAL_KEY` (Fernet anahtarı) yaz.
  Anahtar üretimi: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Açık riskler

- Last.fm ticari izni gelmeyebilir; yedek: ListenBrainz + kendi birlikte-oluşum matrisi.
- Apple Music Android SDK ve Flutter bağlayıcısı doğrulanmadı (Faz 7 öncesi kontrol).
- Spotify Şubat 2026 duyurusu okunmadı.
- Faz 0 örneği tek kişinin müzik sahnesi; kapsam sayıları genellenmeyebilir.
