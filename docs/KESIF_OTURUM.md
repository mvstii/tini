# Keşif programı — oturum durumu (devir notu)

Bu dosya Claude Code oturumları arasında köprüdür. **Her oturumun başında okunur; her aşama bitiminde ve oturum kapanmadan önce güncellenir.** Program planı ve kapsam: `docs/KESIF_PLANI.md`. Kalıcı proje kayıtları: `docs/DURUM.md`.

Son güncelleme: 2026-11-09 (PR-4 Aşama 4 tamam; commitlendi, birleştirme onayı bekliyor)

## Aktif durum

- **Aktif PR:** PR-4 birleşti (#84, #85); tam omurga koşusu geliştiricinin bilgisayarında sürüyor (10 Kasım 01:20: 77 alt türden 28'i veride, kapı 4 bilinen Türkçe alt tür dışında geçiyor). Rapor için `python -m app.jobs.build_genre_backbone --report`; nihai sayılar gelince DURUM.md güncellenir.
- **PR-5 uygulandı (10 Kasım 2026), commitlendi, push/birleştirme onayı bekliyor:** onay yaklaşım A + `unknown` bant sapması + varsayılanlar (prior 1/1, floor 0,05, smoothing 1,0) + "uygulamaya geç". Backend 381 geçti/11 atlandı/0 hata, ruff temiz. Kayıt DURUM.md'de.
- **Dal:** `feat/pr5-user-model` (`fix/pr4-backbone-tags` = `main` içeriği üzerinden; `origin/main` = `40869d3`).
- **Sıradaki adım:** PR-5 push + birleştirme onayı; ardından PR-6 (Örnekleyici `queue-8`) Aşama 1. Omurga koşusu bitince `--report` ile nihai sayılar DURUM.md'ye.
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
| PR-4 | `feat/pr4-genre-spine` | Birleşti (#84, #85); tam omurga koşusu sürüyor | Evet |
| PR-5 | `feat/pr5-user-model` | Uygulandı, birleştirme bekliyor | Hayır |

## PR-0'dan PR-4'e taşınacak bulgular (ayrıntı: PR-0 dalındaki `docs/ARCHITECTURE.md`)

- ISRC için birincil kaynak ListenBrainz `POST /1/metadata/recording/` (token; 200 MBID/istek). MusicBrainz yedek.
- `pop_begin/pop_end` yönü ters: 0–33 en çok dinlenen. Bant adları `top/mid/tail`.
- Türkçe türlerde kapı yalnızca sanatçı yolu (D) + genişletilmiş havuzla geçti; `lb-radio/tags` tek başına yetmez.
- Kapıya "alt tür başına ≥ 15 benzersiz sanatçı" eklendi; sanatçı başına üst sınır gerekli.
- Büyük arabesk sanatçılarında ISRC boşluğu (PR-4b olarak not edildi).
- `top-recordings-for-artist` token ister (`LISTENBRAINZ_TOKEN`).

## Güncelleme kuralı

Her aşama bitiminde ve oturum kapanmadan önce "Aktif durum" bölümü baştan yazılır (geçmiş tutulmaz; geçmiş `DURUM.md`'dedir). Yarım kalan uygulama işi anlamlı bir WIP commit'iyle dala kaydedilir. Bir PR tamamlandığında "Dal durumu" tablosu güncellenir ve sıradaki PR "Aktif durum"a yazılır.
