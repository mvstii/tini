# Keşif programı — oturum durumu (devir notu)

Bu dosya Claude Code oturumları arasında köprüdür. **Her oturumun başında okunur; her aşama bitiminde ve oturum kapanmadan önce güncellenir.** Program planı ve kapsam: `docs/KESIF_PLANI.md`. Kalıcı proje kayıtları: `docs/DURUM.md`.

Son güncelleme: 2026-11-10 (PR-6 Aşama 4 tamam; commitlendi, push/birleştirme onayı bekliyor)

## Aktif durum

- **Aktif PR:** PR-6 (Örnekleyici `queue-8`), dal `feat/pr6-sampler`. Kod, testler (392 geçti/15 atlandı/0 hata, ruff temiz) ve dokümanlar bitti; push ve birleştirme geliştirici onayında.
- **Onay kaydı:** 10 Kasım 2026 — Aşama 2 raporu sunuldu; geliştirici "Onaylıyorum. Önerin üzerinden ilerleyelim" dedi ve find_card riski için "adaptöre `isrc_only`" seçti.
- **Sapmalar (DURUM.md'de):** `diversify` kaldırılmadı; graf benzerlik penceresi bağlanmadı; sonda/joker hızlı yol bayrağına bağlı; omurga verisi 32/77 alt tür.
- **Ölçülmeyenler:** `queue_sim` (yerelde süresi dolmamış kart yok → 0 kart; Neon/canlıda `python -m app.jobs.queue_sim --email <e-posta>`), kalite koruması (`evaluate`), Spotify istemcisinde `isrc_only` için ayrı test.
- **Canlıya çıkış:** bayrak kapalı gider. Açmak için önce `fast_queue_enabled`; ardından `queue_sampler_enabled` ile %10 keşif (ortamda `queue_mix_*` ayarı), kalite koruması tutarsa artır (sonda/joker Good+ oranı ≥ genel ortalamanın %60'ı, "Dinlemedim" < %50). Göç yok.
- **Geliştiricide kalanlar:** push/birleştirme onayı; omurga koşusu bitince `--report` ve 77 alt tür kapısı; Neon depolama sınırı teyidi; canlıya (Render) bayrak kapalı dağıtım ve göç 0021'in üretim Neon'unda doğrulanması; PR-3 için yeni APK + emülatörde 100 kartlık hızlı oylama; staging parolası döndürme; `C:/dev/tini_bench` silme; Last.fm ticari izni.
- **Açık sorular / borçlar:** PR-4b (ISRC'siz sanatçı), PR-2 borçları, graf benzerlik penceresinin bağlanması.
- **Sıradaki adım:** PR-6 birleştirildikten sonra PR-7 (Liste tarafı `list-6`) Aşama 1.

## Dal durumu

| PR | Dal | Durum | `main`'de mi |
| --- | --- | --- | --- |
| PR-0 | `feat/pr0-lb-spike` (4 commit, `784ba6a`) | Tamamlandı — kapı GEÇTİ | Evet (yerel, `7e5fc64`) |
| PR-1 | `feat/pr1-measure-hygiene` | Doğrulandı (test + bench) | Evet (`origin/main` `38a36a2`) |
| PR-2 | `feat/pr2-fast-queue` | Uygulandı, hedef kısmen (borçlar DURUM.md'de) | Evet (`origin/main` `b3a186b`) |
| PR-3 | `feat/pr3-queue-controller` | Uygulandı, emülatör ölçümü bekliyor | Evet (`origin/main` `33e9d96`) |
| PR-4 | `feat/pr4-genre-spine` | Birleşti (#84, #85); tam omurga koşusu sürüyor | Evet |
| PR-5 | `feat/pr5-user-model` | Birleşti (#86, `866b9f1`) | Evet |
| PR-6 | `feat/pr6-sampler` | Uygulandı, birleştirme onayı bekliyor | Hayır |

## PR-0'dan PR-4'e taşınacak bulgular (ayrıntı: PR-0 dalındaki `docs/ARCHITECTURE.md`)

- ISRC için birincil kaynak ListenBrainz `POST /1/metadata/recording/` (token; 200 MBID/istek). MusicBrainz yedek.
- `pop_begin/pop_end` yönü ters: 0–33 en çok dinlenen. Bant adları `top/mid/tail`.
- Türkçe türlerde kapı yalnızca sanatçı yolu (D) + genişletilmiş havuzla geçti; `lb-radio/tags` tek başına yetmez.
- Kapıya "alt tür başına ≥ 15 benzersiz sanatçı" eklendi; sanatçı başına üst sınır gerekli.
- Büyük arabesk sanatçılarında ISRC boşluğu (PR-4b olarak not edildi).
- `top-recordings-for-artist` token ister (`LISTENBRAINZ_TOKEN`).

## Güncelleme kuralı

Her aşama bitiminde ve oturum kapanmadan önce "Aktif durum" bölümü baştan yazılır (geçmiş tutulmaz; geçmiş `DURUM.md`'dedir). Yarım kalan uygulama işi anlamlı bir WIP commit'iyle dala kaydedilir. Bir PR tamamlandığında "Dal durumu" tablosu güncellenir ve sıradaki PR "Aktif durum"a yazılır.
