# Kapalı test dağıtımı (Faz 6 / S1)

Ücretsiz çözüm: geliştirici makinesinde Docker Compose + ngrok'un ücretsiz statik alan adı. Ücretli barındırma yayın sonrasına kalır.

## Bir kerelik kurulum (geliştirici)

1. ngrok hesabı aç (ücretsiz), panelden **authtoken**'ı ve **statik alan adını** (Domains bölümü, `xxxx.ngrok-free.app`) al.
2. `.env` dosyasına ekle (depoya girmez):
   - `POSTGRES_PASSWORD`: güçlü, rastgele bir parola
   - `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`
   - `SPOTIFY_REDIRECT_URI=https://<NGROK_DOMAIN>/connect/spotify/callback`
3. Spotify geliştirici panelinde bu redirect URI'yi ekle (Add, sonra Save). Gerçek cihazlarda `adb reverse` gerekmez.
4. Test kullanıcılarının e-postalarını panelde User Management'a ekle (en çok 5 kişi).

Not: `POSTGRES_PASSWORD` yalnızca **boş** bir veritabanı hacmiyle işler; geliştirme hacmi (`tini` parolası) ayrı tutulur, prod için `-p tini-prod` proje adı kullanılır.

## Başlatma / durdurma

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

## Sınırlar

- Makine ve Docker test saatlerinde açık olmalı; kapalıyken testçiler bağlanamaz.
- Veritabanı portu dışarı açılmaz; backend yalnızca `127.0.0.1:8000`'e bağlanır, dışarıya yalnızca tünel çıkar.
- Token'lar veritabanında şifreli (`CREDENTIAL_KEY`); anahtarı kaybetmek bağlantıları çözülemez yapar, `.env`'i yedekle.
