# Keşif programı — oturum durumu (devir notu)

Bu dosya Claude Code oturumları arasında köprüdür. **Her oturumun başında okunur; her aşama bitiminde ve oturum kapanmadan önce güncellenir.** Program planı ve kapsam: `docs/KESIF_PLANI.md`. Kalıcı proje kayıtları: `docs/DURUM.md`.

Son güncelleme: 2026-11-09 (PR-3 uygulandı ve commitlendi; birleştirme/push kararı bekliyor)

## Aktif durum

- **Aktif PR:** PR-3 — İstemci kuyruk denetleyicisi (Aşama 4 bitti; emülatör ölçümü geliştiricide)
- **Dal:** `feat/pr3-queue-controller` (`main` = `b3a186b` üzerinden). Commit var, push/birleştirme yok.
- **Onay kaydı:** 9 Kasım 2026 — Aşama 2 raporu sunuldu; geliştirici "A" (planın `QueueController`'ı) ve rozet için seçenek (a) (yalnız `source` taşıyan kartta rozet; kütüphane parçaları için sunucu değişikliği yok) dedi, "Onay veriyorum".
- **Yazılanlar:** backend `profile/api.py` (`queue(recent)`), `profile/active.py` (`diversify(prior_artists)`), `config.py` (`queue_recent_max`), `tests/test_queue_recent.py`; mobil `api.dart`, `queue_controller.dart` (yeni), `screens/rating_screen.dart`, `test/queue_controller_test.dart` (yeni).
- **Sonuçlar:** Flutter 62/62, analyze temiz; backend 348 geçti / 10 atlandı / 0 hata, ruff temiz. **Ölçülmedi:** "100 kartlık hızlı oylamada çıkmaz ekran 0" (emülatör + sınırlı backend).
- **Geliştiricide kalanlar:** yeni APK derle; emülatörde 100 kartlık hızlı oylama kontrolü; Neon staging uç noktası (ep-noisy-scene) teyidi ve staging parolası döndürme; işi bitince `C:/dev/tini_bench` (production dump `neon.dump`) sil; mağaza öncesi Last.fm ticari izin borcu.
- **Açık sorular / borçlar:** PR-2 borçları (`uncertainty` maliyeti, Spotify 429 `Retry-After`); rozet etiketlerinden "Kütüphanenden / Yeni bir tür / Sürpriz" yapılmadı.
- **Sıradaki adım:** geliştirici PR-3 birleştirme/push kararını verir; ardından PR-4 Aşama 1 (yalnızca onayla).

## Dal durumu

| PR | Dal | Durum | `main`'de mi |
| --- | --- | --- | --- |
| PR-0 | `feat/pr0-lb-spike` (4 commit, `784ba6a`) | Tamamlandı — kapı GEÇTİ | Evet (yerel, `7e5fc64`) |
| PR-1 | `feat/pr1-measure-hygiene` | Doğrulandı (test + bench) | Evet (`origin/main` `38a36a2`) |
| PR-2 | `feat/pr2-fast-queue` | Uygulandı, hedef kısmen (borçlar DURUM.md'de) | Evet (`origin/main` `b3a186b`) |
| PR-3 | `feat/pr3-queue-controller` | Uygulandı, emülatör ölçümü bekliyor | Hayır |

## PR-0'dan PR-4'e taşınacak bulgular (ayrıntı: PR-0 dalındaki `docs/ARCHITECTURE.md`)

- ISRC için birincil kaynak ListenBrainz `POST /1/metadata/recording/` (token; 200 MBID/istek). MusicBrainz yedek.
- `pop_begin/pop_end` yönü ters: 0–33 en çok dinlenen. Bant adları `top/mid/tail`.
- Türkçe türlerde kapı yalnızca sanatçı yolu (D) + genişletilmiş havuzla geçti; `lb-radio/tags` tek başına yetmez.
- Kapıya "alt tür başına ≥ 15 benzersiz sanatçı" eklendi; sanatçı başına üst sınır gerekli.
- Büyük arabesk sanatçılarında ISRC boşluğu (PR-4b olarak not edildi).
- `top-recordings-for-artist` token ister (`LISTENBRAINZ_TOKEN`).

## Güncelleme kuralı

Her aşama bitiminde ve oturum kapanmadan önce "Aktif durum" bölümü baştan yazılır (geçmiş tutulmaz; geçmiş `DURUM.md`'dedir). Yarım kalan uygulama işi anlamlı bir WIP commit'iyle dala kaydedilir. Bir PR tamamlandığında "Dal durumu" tablosu güncellenir ve sıradaki PR "Aktif durum"a yazılır.
