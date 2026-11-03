# Kapalı test dağıtımı (Faz 6 / S1)

Güncel yöntem (3 Kasım 2026): **Render (ücretsiz web servisi) + Neon (PostgreSQL)**, kart gerekmez, bilgisayar kapalıyken de çalışır. Aşağıdaki Oracle VM ve ngrok bölümleri yedek yöntemlerdir (Oracle ve Google Cloud kayıtları kart doğrulamasında reddedildi).

## Render + Neon (güncel)

Adres: `https://tini-74he.onrender.com`. Uygulama GitHub `mvstii/tini` `main` dalından, Root Directory `backend`, `backend/Dockerfile` ile Frankfurt'ta derlenir.

- **Veritabanı:** Neon (Frankfurt, PG16, pgvector 0.8.0). `DATABASE_URL` biçimi: `postgresql+psycopg://...?sslmode=require` (direct bağlantı).
- **Render ortam değişkenleri:** `PORT=8000`, `APP_ENV=prod`, `DATABASE_URL`, `CREDENTIAL_KEY` (eski yığınla aynı olmalı), `SPOTIFY_CLIENT_ID`, `SPOTIFY_REDIRECT_URI=https://tini-74he.onrender.com/connect/spotify/callback` (Spotify panelinde de ekli), `MUSICBRAINZ_CONTACT`, `LASTFM_API_KEY`, `OPENBLAS_NUM_THREADS=1`, `FORWARDED_ALLOW_IPS=*`.
- **Docker Command alanı boş bırakılır.** Orada `sh -c "..."` kullanmak açılışta `Exited with status 127` hatası verdi; Dockerfile `CMD`'si yeterli.
- **Göç:** açılışta alembic çalışmaz. Şema değişince bilgisayardan, `DATABASE_URL` Neon'a çevrilerek `alembic upgrade head` çalıştırılır. Ücretsiz planda SSH ve one-off job yoktur; `app.jobs.*` betikleri de aynı şekilde bilgisayardan Neon'a bağlanarak çalışır.
- **Güncelleme:** `main`'e push Render'da otomatik deploy tetikler.
- **Sınırlar:** 15 dk boşta kalınca servis uyur, ilk istek ~1 dk sürer. 512 MB RAM'de SciPy/scikit-learn işleri OOM riski taşır. Neon verisi `backups/tini.sql` olarak yedeklendi (git'e girmez); düzenli yedek için `pg_dump` bilgisayardan Neon'a çalıştırılır.
- **Doğrulama:** `curl https://tini-74he.onrender.com/health` → `{"status":"ok"}`.
- **APK:** `flutter build apk --release --dart-define=API_BASE=https://tini-74he.onrender.com` (Flutter SDK `C:/dev/flutter`; `C:/src/flutter` pubspec'in istediği Dart sürümünden eski).
- **Eski yığın:** bilgisayardaki `tini-prod` Docker yığını ve ngrok artık gereksiz; kapatılabilir.

## Bir kerelik kurulum (geliştirici)

1. ngrok hesabı aç (ücretsiz), panelden **authtoken**'ı ve **statik alan adını** (Domains bölümü, `xxxx.ngrok-free.app`) al.
2. `.env` dosyasına ekle (depoya girmez):
   - `POSTGRES_PASSWORD`: güçlü, rastgele bir parola
   - `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`
   - `SPOTIFY_REDIRECT_URI=https://<NGROK_DOMAIN>/connect/spotify/callback`
3. Spotify geliştirici panelinde bu redirect URI'yi ekle (Add, sonra Save). Gerçek cihazlarda `adb reverse` gerekmez.
4. Test kullanıcılarının e-postalarını panelde User Management'a ekle (en çok 5 kişi).

Not: `POSTGRES_PASSWORD` yalnızca **boş** bir veritabanı hacmiyle işler; geliştirme hacmi (`tini` parolası) ayrı tutulur, prod için `-p tini-prod` proje adı kullanılır.

## Oracle Cloud VM (7/24, ücretsiz)

Bilgisayar kapalıyken de erişim için aynı yığın Oracle Always Free VM'inde çalışır; ngrok yerine Caddy (otomatik HTTPS) kullanılır. Ücretsiz kota koşulları değişebilir; kayıtta güncel şartları kontrol et.

1. **Hesap ve VM (geliştirici):** cloud.oracle.com'da hesap aç (kart doğrulaması ister). Compute → Instance: imaj **Ubuntu 22.04/24.04**, şekil **VM.Standard.A1.Flex** (ARM; 2 OCPU / 12 GB yeterli), SSH anahtarı ekle. "Out of capacity" dönerse başka availability domain veya bir süre sonra tekrar dene. Boot volume 50 GB+.
2. **Ağ:** VCN → Security List → Ingress kuralları: TCP **80** ve **443**, kaynak `0.0.0.0/0`. 22 zaten açıktır (mümkünse kaynağı kendi IP'nle sınırla). VM içinde Ubuntu'nun iptables'ı da açılmalı:
   ```bash
   sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save   # yoksa: sudo apt install iptables-persistent
   ```
3. **Docker:** `curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER` (oturumu yeniden aç). Depoyu klonla.
4. **Alan adı:** kendi alan adın yoksa VM'in genel IP'siyle `A-B-C-D.sslip.io` (örn. `203-0-113-7.sslip.io`, noktalar tireli) ücretsiz çalışır; kalıcı ad için DuckDNS de olur. Ayrıca VM'e **rezerve (sabit) genel IP** ata, yoksa yeniden başlatmada adres değişebilir.
5. **`.env`** (VM'de, depoya girmez): `POSTGRES_PASSWORD`, `CREDENTIAL_KEY` (eskisiyle aynı!), `SITE_ADDRESS=<alan-adı>`, `SPOTIFY_REDIRECT_URI=https://<alan-adı>/connect/spotify/callback` ve bilgisayardaki `.env`'deki diğer değerler. Spotify panelinde yeni redirect URI'yi ekle.
6. **Veriyi taşı** (bilgisayarda yedek al, VM'e kopyala):
   ```bash
   COMPOSE_PROJECT_NAME=tini-prod ./scripts/backup.sh          # bilgisayarda
   scp backups/tini-*.sql.gz ubuntu@<vm-ip>:~/                  # en yenisini seç
   ```
   VM'de, yalnızca DB'yi kaldırıp yükle, sonra tüm yığını başlat:
   ```bash
   docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml up -d db
   gunzip -c ~/tini-YYYYMMDD-HHMMSS.sql.gz | docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U tini tini
   docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml --profile caddy up -d --build
   curl https://<alan-adı>/health
   ```
7. **Yedek:** `crontab -e` → `0 4 * * * cd ~/tini && COMPOSE_PROJECT_NAME=tini-prod ./scripts/backup.sh`. Yedekleri ara sıra bilgisayarına da çek (`scp`); VM kaybolursa tek kopya olmasın.
8. **Eski yığını kapat:** bilgisayardaki `tini-prod` yığınını `down` et, böylece iki ayrı veritabanı oluşmaz. Mobil APK'yı yeni adresle derle (aşağıda, `API_BASE=https://<alan-adı>`).

Güncelleme: VM'de `git pull`, sonra aynı `--profile caddy up -d --build` komutu. Sistem güncellemesi (`apt upgrade`) senin sorumluluğunda.

## Başlatma / durdurma (bilgisayar + ngrok)

```bash
docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml --profile tunnel up -d --build
docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml --profile tunnel down
```

Açılışta `alembic upgrade head` çalışır. Doğrulama: `curl https://<NGROK_DOMAIN>/health` → `{"status":"ok"}`.

## Yedek

```bash
COMPOSE_PROJECT_NAME=tini-prod ./scripts/backup.sh
```

`backups/` altına gzip'li `pg_dump` yazar, son 14 yedeği tutar (depoya girmez). Test süresince günde bir kez, ya da Windows Görev Zamanlayıcı'yla.

## Günlük ve geri bildirim (S3)

- İstek günlüğü: `docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml logs -f backend`. Her istek tek satır JSON (`request_id`, `path`, `status`, `ms`, `user`); 5xx satırları ERROR düzeyinde ve yığın izi ile. Kullanıcı bir hata bildirirse saatine bakıp `status >= 500` satırlarını ara.
- Geri bildirimler: `docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.jobs.feedback --kind bug`.
- İlerleme (oy sayıları): `docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.jobs.evaluate`.

## Hesap silme (S4)

Uygulamada silme uç noktası yok (v1); kullanıcı isterse geliştirici siler. Önce neyin silineceğine bak, sonra `--yes` ile sil. Kişisel tablolar `ON DELETE CASCADE` ile birlikte gider, paylaşılan katalog kalır:

```bash
docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.jobs.delete_user kisi@example.com
docker compose -p tini-prod -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.jobs.delete_user kisi@example.com --yes
```

## Sınırlar

- ngrok yönteminde makine ve Docker test saatlerinde açık olmalı; kapalıyken testçiler bağlanamaz (Oracle VM yönteminde bu sınır yok).
- Veritabanı portu dışarı açılmaz; backend yalnızca `127.0.0.1:8000`'e bağlanır, dışarıya yalnızca tünel çıkar.
- Token'lar veritabanında şifreli (`CREDENTIAL_KEY`); anahtarı kaybetmek bağlantıları çözülemez yapar, `.env`'i yedekle.

## Android APK (Faz 6 / S2)

Bir kerelik imza anahtarı (depo dışına `%USERPROFILE%/tini-gizli/`, `mobile/android/key.properties`, ikisi de ignore'lu):

```bash
powershell -ExecutionPolicy Bypass -File scripts/android-imza.ps1
```

Anahtar dosyasını yedekle; kaybolursa testçiler güncelleme yapamaz, uygulamayı kaldırıp yeniden kurmak zorunda kalır. `key.properties` yoksa release debug anahtarıyla imzalanır (CI için).

APK derleme (tünel adresiyle):

```bash
cd mobile
flutter build apk --release --dart-define=API_BASE=https://<NGROK_DOMAIN>
```

Çıktı: `mobile/build/app/outputs/flutter-apk/app-release.apk` (~49 MB). Testçilere dosya olarak gönder; telefonda "bilinmeyen kaynaklardan yükleme" izni gerekir. Release yapıda düz http kapalıdır (yalnızca debug yapıda açık).
