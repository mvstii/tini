# Keşif programı — oturum durumu (devir notu)

Bu dosya Claude Code oturumları arasında köprüdür. **Her oturumun başında okunur; her aşama bitiminde ve oturum kapanmadan önce güncellenir.** Program planı ve kapsam: `docs/KESIF_PLANI.md`. Kalıcı proje kayıtları: `docs/DURUM.md`.

Son güncelleme: 2026-11-09 (PR-4 Aşama 4 tamam; commitlendi, birleştirme onayı bekliyor)

## Aktif durum

- **Aktif PR:** PR-4 — Evren: tür omurgası (uygulandı, staging raporu ve birleştirme bekliyor)
- **Dal:** `feat/pr4-genre-spine` (`main` = `33e9d96` üzerinden).
- **Onay kaydı:** 9 Kasım 2026 — Aşama 2 raporu sunuldu; geliştirici yaklaşım A'yı (ayrı `genre_seed` + `track_popularity` tabloları, `track` değişmez) seçti ve "Önerilerin üzerinden ilerleyebiliriz" dedi.
- **Biten adımlar:** 1–7 (kaynak istemcisi, göç 0021, 77 alt tür, omurga işi, temsilci parça, D3, testler, dokümanlar). Backend 370 geçti/11 atlandı/0 hata, ruff temiz.
- **Geliştiricide kalanlar:** LISTENBRAINZ_TOKEN ve MUSICBRAINZ_CONTACT'ı ortam dosyasına koy; omurga işini Neon staging'e çalıştırıp raporu üret (alt tür başına kayıt, ISRC oranı, graf/DB boyutu, ≥15 benzersiz sanatçı); Neon depolama sınırını panelden teyit et; canlıya bayrak kapalı çık. Önceki borçlar: PR-3 için yeni APK + emülatörde 100 kartlık hızlı oylama, ep-noisy-scene teyidi, staging parolası döndürme, `C:/dev/tini_bench` silme, Last.fm ticari izni.
- **Açık sorular / borçlar:** PR-4b (ISRC'siz sanatçı her koşuda yeniden denenir; büyük arabesk boşluğu); PR-2 borçları; `mark_unheard` D3 eklemesi plan metnini hafifçe aşıyor (raporlandı).
- **Sıradaki adım:** geliştirici onayıyla push/birleştirme; ardından PR-5 Aşama 1 (Keşif).


## Dal durumu

| PR | Dal | Durum | `main`'de mi |
| --- | --- | --- | --- |
| PR-0 | `feat/pr0-lb-spike` (4 commit, `784ba6a`) | Tamamlandı — kapı GEÇTİ | Evet (yerel, `7e5fc64`) |
| PR-1 | `feat/pr1-measure-hygiene` | Doğrulandı (test + bench) | Evet (`origin/main` `38a36a2`) |
| PR-2 | `feat/pr2-fast-queue` | Uygulandı, hedef kısmen (borçlar DURUM.md'de) | Evet (`origin/main` `b3a186b`) |
| PR-3 | `feat/pr3-queue-controller` | Uygulandı, emülatör ölçümü bekliyor | Evet (`origin/main` `33e9d96`) |
| PR-4 | `feat/pr4-genre-spine` | Uygulandı, staging raporu bekliyor | Hayır |

## PR-0'dan PR-4'e taşınacak bulgular (ayrıntı: PR-0 dalındaki `docs/ARCHITECTURE.md`)

- ISRC için birincil kaynak ListenBrainz `POST /1/metadata/recording/` (token; 200 MBID/istek). MusicBrainz yedek.
- `pop_begin/pop_end` yönü ters: 0–33 en çok dinlenen. Bant adları `top/mid/tail`.
- Türkçe türlerde kapı yalnızca sanatçı yolu (D) + genişletilmiş havuzla geçti; `lb-radio/tags` tek başına yetmez.
- Kapıya "alt tür başına ≥ 15 benzersiz sanatçı" eklendi; sanatçı başına üst sınır gerekli.
- Büyük arabesk sanatçılarında ISRC boşluğu (PR-4b olarak not edildi).
- `top-recordings-for-artist` token ister (`LISTENBRAINZ_TOKEN`).

## Güncelleme kuralı

Her aşama bitiminde ve oturum kapanmadan önce "Aktif durum" bölümü baştan yazılır (geçmiş tutulmaz; geçmiş `DURUM.md`'dedir). Yarım kalan uygulama işi anlamlı bir WIP commit'iyle dala kaydedilir. Bir PR tamamlandığında "Dal durumu" tablosu güncellenir ve sıradaki PR "Aktif durum"a yazılır.
