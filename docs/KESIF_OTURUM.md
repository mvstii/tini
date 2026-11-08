# Keşif programı — oturum durumu (devir notu)

Bu dosya Claude Code oturumları arasında köprüdür. **Her oturumun başında okunur; her aşama bitiminde ve oturum kapanmadan önce güncellenir.** Program planı ve kapsam: `docs/KESIF_PLANI.md`. Kalıcı proje kayıtları: `docs/DURUM.md`.

Son güncelleme: 2026-11-09 (PR-2 kapatıldı; birleştirme/push kararı bekliyor)

## Aktif durum

- **Aktif PR:** PR-2 — Hızlı yol ve tampon (Aşama 4 bitti; hedef kısmen karşılandı, geliştirici "olduğu gibi kapat" dedi)
- **Dal:** `feat/pr2-fast-queue` (`main` = `38a36a2` üzerinden açıldı). Commit var, push/birleştirme yok.
- **Onay kaydı:** 9 Kasım 2026 — Aşama 2 raporu sunuldu; geliştirici "Olur" dedi: yaklaşım A (arka plan doldurucu, PR-1 yürütücüsü) + yeni `fast_queue_enabled` bayrağı (canlı varsayılanı kapalı). PR-0/PR-1 `origin/main`'e itildi (`38a36a2`).
- **Plandan sapma (gerekçeli):** plan işlem kapsamlı `pg_try_advisory_xact_lock` der; doldurucu işin ortasında commit ettiği için kilit ayrı autocommit bağlantıda oturum kilidi (`pg_try_advisory_lock` + `unlock`) olarak tutulur. Etki: doldurma sırasında +1 Neon bağlantısı (yürütücü tek iş parçacıklı → en çok +1).
- **Yazılanlar:** `config.py` (`fast_queue_enabled`, `buffer_low_watermark` 8, `buffer_target` 20, `refill_batch` 10, `meta_refresh_at` 0,8, `meta_refresh_batch` 10, `refill_error_backoff_seconds` 60); `profile/suggest.py` (`ready_suggestions`, `refill_buffer`, `_refresh_metas`, ortak yardımcılar; `suggest_items` davranışı aynı); `profile/refill.py` (yeni); `profile/api.py` (`queue()` hızlı yol + `maybe_refill`, `cast_vote` tetik); `tests/test_fast_queue.py` (10 test).
- **Sonuçlar:** test 346 geçti / 8 atlandı (fixture bağlantı sızıntısı, 102 > 100) / 0 hata, ruff temiz. Bench (bayrak açık, tek koşu): p50 1331, p95 2613, boş 83/100, 5xx 0, RSS 175,5 MB. `suggest` 50 ms. **Bitti tanımı tutmadı:** p95<800 (kalan: `uncertainty` ort. 1321 ms) ve boş 0 (Spotify 429, probla doğrulandı). Karar (9 Kasım): PR-2 olduğu gibi kapatılır; borçlar DURUM.md PR-2 kaydında.
- **Açık sorular / borçlar:** `uncertainty` maliyeti için ayrı iş; Spotify 429 `Retry-After` geri çekilmesi; 503 sahte senaryo, bayrak kapalı bench, `swr_enabled` bench, Neon bağlantı sayısı doğrulanmadı. Bench kalıntısı `C:/dev/tini_bench/` (production dump) silinecek.
- **Sıradaki adım:** geliştirici PR-2 birleştirme/push kararını verir; ardından PR-3 Aşama 1 (yalnızca onayla).

## Dal durumu

| PR | Dal | Durum | `main`'de mi |
| --- | --- | --- | --- |
| PR-0 | `feat/pr0-lb-spike` (4 commit, `784ba6a`) | Tamamlandı — kapı GEÇTİ | Evet (yerel, `7e5fc64`) |
| PR-1 | `feat/pr1-measure-hygiene` | Doğrulandı (test + bench) | Evet (`origin/main` `38a36a2`) |
| PR-2 | `feat/pr2-fast-queue` | Uygulandı, hedef kısmen | Hayır |

## PR-0'dan PR-4'e taşınacak bulgular (ayrıntı: PR-0 dalındaki `docs/ARCHITECTURE.md`)

- ISRC için birincil kaynak ListenBrainz `POST /1/metadata/recording/` (token; 200 MBID/istek). MusicBrainz yedek.
- `pop_begin/pop_end` yönü ters: 0–33 en çok dinlenen. Bant adları `top/mid/tail`.
- Türkçe türlerde kapı yalnızca sanatçı yolu (D) + genişletilmiş havuzla geçti; `lb-radio/tags` tek başına yetmez.
- Kapıya "alt tür başına ≥ 15 benzersiz sanatçı" eklendi; sanatçı başına üst sınır gerekli.
- Büyük arabesk sanatçılarında ISRC boşluğu (PR-4b olarak not edildi).
- `top-recordings-for-artist` token ister (`LISTENBRAINZ_TOKEN`).

## Güncelleme kuralı

Her aşama bitiminde ve oturum kapanmadan önce "Aktif durum" bölümü baştan yazılır (geçmiş tutulmaz; geçmiş `DURUM.md`'dedir). Yarım kalan uygulama işi anlamlı bir WIP commit'iyle dala kaydedilir. Bir PR tamamlandığında "Dal durumu" tablosu güncellenir ve sıradaki PR "Aktif durum"a yazılır.
