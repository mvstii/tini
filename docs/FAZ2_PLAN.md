# Faz 2 Planı — Katalog ve benzerlik grafiği

Taslak: 30 Ekim 2026 · Durum: **onay bekliyor** · Süre: 23 Kasım–6 Aralık (erken başlanabilir; Faz 1 kapısı geçildi)

Kapı: bir çapa şarkıdan 2 adımlık komşuluk önbellekten saniyeler içinde gelir.

## Karar özeti (geliştirici onaylı, 30 Ekim 2026)

1. **Kimlik katmanları.** ISRC birincil; MBID isteğe bağlı. Sanatçı için kendi tablomuz var (normalize ad + sağlayıcı kimlikleri).
2. **Eşleme kademeleri** (güven azalan):
   - **A:** ISRC → MusicBrainz kaydı → sanatçı MBID. Spotify metni kullanılmaz; sonuç paylaşılır (`track.artist_id`).
   - **B:** MusicBrainz'de yoksa, kullanıcıya özel önbellekteki ad Last.fm'e **geçici sorgu anahtarı** olarak verilir. Dönen kanonik sanatçı paylaşılan `artist`'e yazılır; "bu şarkı bu sanatçıdır" bağı kullanıcıya özel `user_track_artist`'te kalır. Güven düşük.
   - **C:** Bulunamazsa şarkı oylanabilir kalır, grafikte çapa olmaz; TTL dolunca veya katalog büyüyünce yeniden denenir.
3. **Paylaşılan tablolara yalnızca MusicBrainz/Last.fm'in kendi kanonik adı ve kimliği girer.** Spotify'dan gelen hiçbir dize paylaşılan tabloya yazılmaz.
4. **Aynı normalize ad, çelişen MBID → birleştirme yok**, yeni satır açılır (ör. UZI vakası).
5. **Kenarlar depoda yönlü ve ham** kalır. Matris kurulurken `symmetrize = mean` (`w = (w_ij + w_ji)/2`, eksik yön 0) + derece normalizasyonu uygulanır; ikisi de yapılandırmadan gelir (`none | mean | max`). Varsayılan Faz 3'te kütüphane verisiyle çevrimdışı doğrulanır.
6. **Grafik anlık görüntüsü sürümlüdür.** Profil/liste hangi grafik sürümüyle üretildiğini kaydeder (determinizm).
7. Last.fm iznine bağımlılık sürüyor (e-posta henüz gitmedi). Yedek: oylardan türetilen kendi eşzamanlılık matrisi (Faz 3+).

## Modül yerleşimi

- `backend/app/sources/` — **kaynak istemcileri** (dış API yalnızca burada): `http.py` (ortak: hız sınırı, 429/Retry-After geri çekilme, zorunlu `User-Agent`, deneme sınırı), `musicbrainz.py`, `lastfm.py`.
- `backend/app/catalog/` — sanatçı/parça eşleme (kademeli çözümleyici, güven skoru, normalize ad).
- `backend/app/graph/` — kenar deposu, tembel genişleme, **saf** matris kurucu ve komşuluk sorgusu.
- Algoritma parametreleri `config.py` içinde tek `GraphSettings` bloğunda (simetrikleştirme modu, derece normalizasyonu, genişleme derinliği, komşu üst sınırı, TTL'ler, güven eşiği, boyut sınırı). Gömülü sabit yok.
- Kod servis adı bilmez; Spotify'a özgü hiçbir şey `catalog`/`graph` içine girmez (kullanıcı adı bilgisi adaptör katmanından soyut tiplerle gelir).

## Şema (göç 0004)

| Tablo | Kapsam | Alanlar (özet) |
|---|---|---|
| `artist` (genişler) | paylaşılan | `name` (kanonik, MB/Last.fm), `name_norm`, `mbid` (null olabilir) |
| `artist_ref` | paylaşılan | `artist_id`, `provider`, `provider_id`, `match_method`, `confidence`; `(provider, provider_id)` benzersiz |
| `user_track_artist` | **kullanıcıya özel** | `user_id`, `track_id`, `artist_id`, `confidence`, `method`; kullanıcı silinince cascade |
| `artist_edge` | paylaşılan | `src`, `dst`, `weight` (0–1, kaynak ham), `source`, `fetched_at`, `expires_at`; komşu başına üst sınır ~20; tamsayı kimlik |
| `fetch_log` | paylaşılan | `(artist_id, source)` için son çekim, durum (ok/boş/hata), `expires_at` — negatif önbellek, tekrar çağrıyı önler |
| `graph_snapshot` | paylaşılan | `version`, `created_at`, kenar sayısı, parametre özeti |

Last.fm boyutu: ham yanıt saklanmaz; `pg_total_relation_size('artist_edge')` izlenir, sınıra (yapılandırmada, varsayılan 80 MB uyarı / 100 MB üst) yaklaşınca en eski kenarlar atılır.

## Dilimler (her biri ayrı PR; her PR sonrası `docs/DURUM.md` + ROADMAP)

**S1 — Kaynak altyapısı + MusicBrainz + kademe A**
- `sources/http.py`, `sources/musicbrainz.py` (ISRC → kayıt → sanatçı MBID/ad; ≤1 istek/sn, `User-Agent` ile).
- Göç 0004'ün sanatçı kısımları (`artist`, `artist_ref`, `user_track_artist`, `fetch_log`).
- `catalog.resolve`: kademe A + `normalize_name`; `POST /library/import` sonrası arka planda çalıştırılabilir (CLI: `python -m app.jobs.enrich`).
- Testler: MockTransport ile MB yanıtları, 429 geri çekilme, normalize ad, çelişen MBID'de birleştirmeme.

**S2 — Last.fm + kademe B/C + güven**
- `sources/lastfm.py` (`artist.getSimilar` MBID ile, yoksa adla; API anahtarı `.env`'de `LASTFM_API_KEY`).
- Kademe B/C, güven skoru, yeniden deneme zamanlaması (`fetch_log`).
- Spotify adı yalnızca kullanıcıya özel önbellekten okunur, paylaşılan tabloya yazılmaz (test: paylaşılan tablolarda Spotify dizesi yok).

**S3 — Kenar deposu + tembel genişleme**
- `artist_edge` yazımı (üst sınır, boyut izleme), `graph_snapshot`.
- Saf `plan_expansion(anchors, depth, cache_state, config)` → çekilecek sanatçı listesi (birim test); iş: CLI/yönetim komutu, çapalardan 2–3 adım, TTL'ye saygılı.
- Önbellek isabet metriği (`fetch_log` üzerinden sayaçlar, `GET /admin/metrics` değil; şimdilik log + test).

**S4 — Matris kurucu + komşuluk sorgusu (kapı)**
- Saf `build_matrix(edges, config)` (simetrikleştirme, derece normalizasyonu; seyrek matris) — **SciPy bağımlılığı eklenir** (aşağıda).
- `GET /graph/neighborhood?track=…&depth=2` (çapa şarkı → sanatçı → 2 adım komşular).
- Kapı testi: önbellek ısınmışken yanıt süresi ölçümü (hedef < 3 sn), `docs/DURUM.md`'ye sonuç.

## Onay gereken bağımlılıklar ve işler

- **SciPy / NumPy** (S4): CLAUDE.md'de zaten yığın olarak listeli; yeni bağımlılık onayı olarak burada istenir.
- **Last.fm API anahtarı** `.env`'de (`LASTFM_API_KEY`): Faz 0'da kullandığın anahtar yeterli; yoksa yenisini alman gerekir. Anahtarı sohbete yazma.
- **MusicBrainz `User-Agent`** (iletişim e-postası içerir): `.env`'de `MUSICBRAINZ_CONTACT`.
- İş çalıştırma: şimdilik CLI + `BackgroundTasks`; kalıcı kuyruk/işçi Faz 3'e bırakılır (kapıyı etkilemez).

## Riskler

- **Last.fm izni gelmezse** üretimde kaynak kalmaz; S2–S3 yine de yazılır, kaynak soyut tutulur (`sources` arayüzü), yedek matris Faz 3+.
- **Kademe B hukuki yorum:** Spotify adını sorgu anahtarı olarak kullanmanın koşullara uyduğu bir yorumdur; yayın öncesi koşullar yeniden okunur (Faz 7 kontrol listesine eklenecek).
- **MusicBrainz oranı düşük** (ISRC→MBID %28): çoğu çapa kademe B/C'ye düşer; güven eşiği ve C oranı S2 sonunda ölçülür, DURUM.md'ye yazılır.
- **Örnek yanlılığı:** ölçümler tek kişinin sahnesine ait; genelleme yapılmaz.
- **Önbellek doluluğuna bağlı sonuç:** sürümlü anlık görüntü ile giderilir; S3'te testle doğrulanır.

## Kapsam dışı (bu fazda yapılmayacak)

PPR hesabı, profil, öneri listesi, gerekçe (Faz 3); oylama arayüzü (Faz 3–4); Apple Music (Faz 7); Discogs/Deezer (kullanılmaz).
