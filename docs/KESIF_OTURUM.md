# Keşif programı — oturum durumu (devir notu)

Bu dosya Claude Code oturumları arasında köprüdür. **Her oturumun başında okunur; her aşama bitiminde ve oturum kapanmadan önce güncellenir.** Program planı ve kapsam: `docs/KESIF_PLANI.md`. Kalıcı proje kayıtları: `docs/DURUM.md`.

Son güncelleme: 2026-11-09 (PR-1 doğrulaması tamamlandı)

## Aktif durum

- **Aktif PR:** PR-1 — Ölçüm ve arka plan hijyeni (doğrulandı, birleştirme bekliyor)
- **Dal:** `feat/pr1-measure-hygiene` (origin'e itilmemiş doküman commit'i hariç `c42d999` itildi). `main`'e birleşmedi.
- **Aşama:** 4 tamam. Sıradaki PR'a geçmeden birleştirme kararı bekleniyor.
- **Onay kaydı:** 8 Kasım 2026 — geliştirici "önerilerin üzerinden ilerleyelim" dedi: (A) PR-1'i yerelde doğrula (test, `ruff`, bench), (B) PR-0'ı `main`'e birleştir, PR-1'i üstüne rebase et (birleştirmeyi geliştirici yapar), (C) PR-2 Aşama 1–2 PR-1 birleşince. Bench için production dump'ı yerele alındı (onaylı).
- **Biten adımlar:**
  - Tam backend paketi yerel Postgres'e karşı: 339 geçti, 5 atlandı, 0 hata; `ruff` temiz.
  - `rapid_vote_bench` önce/sonra (100 oy, 0,1 CPU / 512 MB): `main` p50 4349 / p95 12298 / maks 104539 ms, boş 76; PR-1 p50 3519 / p95 18401 / maks 84911 ms, boş 76; 5xx 0; RSS ~149 → 175–178 MB. Ayrıntı ve yorum DURUM.md'de.
  - Teşhis: yavaşlığın %81'i `suggest` aşamasında (istek yolundaki Spotify/profil işi) → PR-2 hedefi.
- **Kalan adımlar:**
  1. Geliştirici: PR-0 → `main`, PR-1'i rebase et ve birleştir (bkz. "Dal durumu").
  2. Neon bağlantı sayısını staging'den ölç (yerelde ölçülemedi); `swr_enabled` açık koşusu yapılmadı.
  3. 5 atlanan testin nedenini incele (zorunlu değil).
  4. PR-1 birleşince: PR-2 Aşama 1–2 (keşif + analiz raporu).
- **Commit'lenmemiş değişiklik:** bu oturumun doküman değişiklikleri (`DURUM.md`, `KESIF_PLANI.md`, `CLAUDE.md`, `KESIF_OTURUM.md`) commit'lenir. İzlenmeyen Aegis dosyaları (`.claude/`, `MEMORY.md`, `SPEC.md`, vb.), `.pytest_full.log`, `Claude outputs/` commit'lenmez.
- **Açık sorular / bekleyen kararlar:**
  - `backend/.env` Neon'a gidiyor (büyük olasılıkla staging, `ep-noisy-scene…`; production `ep-patient-star…`). Testler/alembic önce yanlışlıkla bu uzak DB'ye koştu. Testleri her zaman `DATABASE_URL=postgresql+psycopg://tini:tini@localhost:5432/tini` ile koş. Branches sayfasında endpoint-dal eşleşmesini teyit et.
  - Production `neondb_owner` parolası bu oturumda ifşa oldu; geliştirici sıfırlayıp Render `DATABASE_URL`'ni güncelledi (panelden teyit edilmedi). Staging parolası ayrı madde (PLAN satır 417).
  - Bench dosyaları repo dışında: `C:\dev\tini_bench\` (`neon.dump` = production verisi, `docker-compose.bench.yml`, `new_db.sh`, `main_wt` worktree). İş bitince silinmeli.
- **Sıradaki adım:** Geliştiricinin birleştirme kararı, sonra PR-2 Aşama 1.

## Dal durumu

| PR | Dal | Durum | `main`'de mi |
| --- | --- | --- | --- |
| PR-0 | `feat/pr0-lb-spike` (4 commit, `784ba6a`) | Tamamlandı — kapı genişletilmiş probla GEÇTİ | Hayır |
| PR-1 | `feat/pr1-measure-hygiene` | Doğrulandı (test + bench), birleştirme bekliyor | Hayır |

## PR-0'dan PR-4'e taşınacak bulgular (ayrıntı: PR-0 dalındaki `docs/ARCHITECTURE.md`)

- ISRC için birincil kaynak ListenBrainz `POST /1/metadata/recording/` (token; 200 MBID/istek). MusicBrainz yedek.
- `pop_begin/pop_end` yönü ters: 0–33 en çok dinlenen. Bant adları `top/mid/tail`.
- Türkçe türlerde kapı yalnızca sanatçı yolu (D) + genişletilmiş havuzla geçti; `lb-radio/tags` tek başına yetmez.
- Kapıya "alt tür başına ≥ 15 benzersiz sanatçı" eklendi; sanatçı başına üst sınır gerekli.
- Büyük arabesk sanatçılarında ISRC boşluğu (PR-4b olarak not edildi).
- `top-recordings-for-artist` token ister (`LISTENBRAINZ_TOKEN`).

## Güncelleme kuralı

Her aşama bitiminde ve oturum kapanmadan önce "Aktif durum" bölümü baştan yazılır (geçmiş tutulmaz; geçmiş `DURUM.md`'dedir). Yarım kalan uygulama işi anlamlı bir WIP commit'iyle dala kaydedilir. Bir PR tamamlandığında "Dal durumu" tablosu güncellenir ve sıradaki PR "Aktif durum"a yazılır.
