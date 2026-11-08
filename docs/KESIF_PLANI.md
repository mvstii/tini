# Tını — Keşif Evreni ve Kuyruk Güvenilirliği Planı

7 Kasım 2026 · Onaylı plan. **Tek doğruluk kaynağı bu dosyadır**; ilerleme burada güncellenir. Claude Docs kopyası (https://claude.ai/artifact/Pz3kKb3X45cdHmHx5eJ9KT) PR sonlarında buradan senkronlanır, çakışmada bu dosya geçerlidir.

## Özet ve hedef

Tını, Taste.io'nun müzik hâli olacak: oylama akışı hiç kesilmeyecek, kuyruk müzik uzayının tamamını tarayacak ve her oy profili keskinleştirecek. Bunun için 8 aşamalı (PR-0…PR-7) bir program uygulanır; her aşama ayrı birleştirilir, ölçülür ve bayrakla kapatılabilir.

**Çözülen iki sorun**

- **Takılma:** Art arda oylamadan sonra kuyruk yeni şarkı vermiyor, "Yeniden dene" çıkıyor.
- **Darlık:** Art arda benzer sanatçılar ve türler geliyor; kullanıcı kendi mahallesinin dışına çıkamıyor.

**Hedefin dört özelliği**

1. **Kesintisiz akış:** bekleme, çıkmaz ekran ve hata kartı yok.
2. **Geniş tarama:** tür, alt tür, sanatçı ve şarkı uzayının tamamı örneklenir; ağırlık zevke göre verilir ama hiçbir bölge kapalı kalmaz.
3. **Bilgi taşıyan oy:** gösterilecek kart "bu oy profil hakkında yeni ne öğretir?" sorusuyla seçilir.
4. **Kontrollü sürpriz:** her oturum farklıdır, aynı tohum aynı sonucu verir (CLAUDE.md determinizm kuralı korunur).

**Sıra mantığı:** Keşif payını artırmak sunucuya iş yükler; takılan sistemin üstüne yük eklenmez. Bu yüzden önce sağlam zemin (PR-0…PR-3), sonra geniş evren (PR-4…PR-5), en son akıllı örnekleme (PR-6…PR-7) gelir.

## Alınan kararlar

Aşağıdaki kararlar 7 Kasım 2026'da geliştirici tarafından onaylandı; CLAUDE.md'deki ilgili maddeler PR-4 ile güncellenir.

| # | Karar | Sonuç | Not |
| --- | --- | --- | --- |
| D1 | ListenBrainz canlıda aktif kaynak (tür omurgası ve popülerlik) | Onaylandı | MetaBrainz ticari koşulları yayın öncesi kalemi; bayrakla kapatılabilir |
| D2 | Paylaşılan katalog kullanıcı kütüphanelerinin dışından da büyür | Onaylandı | Yalnızca ISRC, MBID ve türetilmiş veri; Spotify kuralı değişmez |
| D3 | `cast_vote` kullanıcıya **sunulmuş** parçayı da kabul eder | Onaylandı | Kanıt: kullanıcıya özel `UserTrackMeta` kaydı; göç yok |
| D4 | Sonda ve joker kartlarında gerekçe kapsama hesabından gelir | Onaylandı | Kural 7 bu kapsamla genişletilir: gerekçe hesabın kendisinden türetilir (PPR veya örnekleyici) |
| D5 | Yalnızca ekleme yapan göç `0021` (`genre_seed`, parça popülerlik bandı) | Onaylandı | Önce Neon staging dalında prova |
| Doz | ε=0,3; ısınmada sonda %40; τ orta | Onaylandı (Dengeli) | Canlıda önce %10 keşifle açılır, ölçüm temizse hedefe çıkılır |

Tüm yeni davranışlar canlıya **kapalı** girer ve Render ortam değişkenleriyle (`PROFILE_`, `RECOMMEND_`, `GRAPH_` önekleri) tek tek açılır.

## Teşhis

Takılmanın kökü, kuyruğun her isteği o an senkron hesaplaması; darlığın kökü, aday evreninin kullanıcıların graf mahallesiyle sınırlı olması. "Kesin" = koddan doğrulandı, "hipotez" = PR-1 ölçümüyle doğrulanacak.

**Güvenilirlik**

| # | Kök neden | Kanıt | Güven |
| --- | --- | --- | --- |
| G1 | İstemcide kaybolan doldurma: `_filling` sürerken verilen oylar yeni istek tetiklemiyor, bitince yeniden kontrol yok; sunucu bekleyen kartları geri döndürüyor, filtrelenince 0 yeni kart → "Oylanacak şarkı yok" çıkmazı | `mobile/lib/screens/rating_screen.dart` (`_topUp`, `_fill`) | Kesin |
| G2 | `GET /votes/queue` istek yolunda profil yenileme, liste üretimi ve 10–20 sıralı Spotify çağrısı; DB oturumu boyunca açık | `profile/api.py`, `profile/suggest.py` | Kesin (kod); canlıda yavaşlık **gözlenmedi** (bkz. temel çizgi) |
| G3 | `after_vote` her oyda yeni engine açıyor (`make_engine`); MusicBrainz sınırlayıcısı nesne başına; uyanıştan 120 sn sonra graf turu ve yeni snapshot → matris + SVD/KMeans istek içinde | `graph/auto.py`, `db.py`, `sources/http.py`, `graph/scheduler.py` | Kesin (çakışma: hipotez) |
| G4 | Render soğuk açılışı (~1 dk) istemci zaman aşımından (45 sn) uzun | `mobile/lib/api.dart`, `docs/DAGITIM.md` | Kesin |
| G5 | İstek günlüğünde yalnızca toplam süre var | `requestlog.py` | Kesin |
| G6 | **Spotify bağımlılığı:** kütüphane parçalarının meta önbelleği 24 saatte dolunca parçalar kuyruktan düşer; otomatik kütüphane yenilemesi Spotify 503/429 dönerse yakalanmayan `httpx.HTTPStatusError` ile 500 verir; öneri kartları da `find_card` için Spotify'a muhtaç → kuyruk kurur | `library.py`, `adapters/spotify/client.py`, `profile/suggest.py`; canlı log 7 Kasım 02:57/02:58 ve 5 Kasım 02:42 (`/library/import` 500, Spotify `GET /me/tracks` 503) | Kesin (canlıda gözlendi) |
| G7 | Last.fm JSON olmayan yanıt dönünce `sources/http.get_json` `JSONDecodeError`'u kaynak hatasına çevirmiyor; graf turunun tamamı ilk kötü yanıtta iptal olur | `sources/http.py`, `graph/expand.py`; canlı log 7 Kasım 19:40 | Kesin (canlıda gözlendi) |

**Kapsam ve çeşitlilik**

| # | Kök neden | Kanıt |
| --- | --- | --- |
| K1 | Kuyruk kütüphaneden beslenir; öneriler yalnızca kalan < 20 olunca karışır; keşif yuvası da kütüphane içinden | `profile/api.py` (`queue_suggest_threshold`), `profile/active.py` |
| K2 | `queue_genre_gap=2` azınlık türleri önden tüketir, sonu uzun rap serilerine çöker | `profile/active.py` (`diversify`) |
| K3 | Parti dikişinde aralık bilgisi kaybolur (G1 ile aynı kök) | istemci + `queue()` |
| K4 | Benzerlik yalnızca birebir sanatçı + kaba tür; graf kosinüsü yok; etiketsiz (~%24) sanatçı muaf | `profile/active.py`, `catalog/tags.py` |
| K5 | Öneriler `position` sırasıyla alınır, `far` nadiren ulaşır; sona eklenir, aralıklanmaz | `profile/suggest.py` |
| K6 | Oturumlar arası tür hafızası yok | — |
| K7 | Liste: `far` sıfır paylı türlerden başlar, tür tavanı %50, `far` bandit dışı, şarkı = en düşük kimlik | `recommend/diverse.py`, `recommend/service.py` |
| K8 | Aday evreni kullanıcı mahallesiyle sınırlı (Last.fm benzer, derinlik 2); küresel tür omurgası yok | `graph/expand.py`, `config.py` (`expand_depth`) |
| K9 | Sanatçı başına ≤ 5 parça, popülerlik yok, hep aynı ve temsil gücü düşük şarkı | `graph/auto.py`, `_pick_tracks` |
| K10 | Sıralamalar deterministik argmax; tohum yalnızca eşitlik bozar, sürpriz yok | `profile/active.py`, `recommend/select.py` |
| K11 | 14 kovalık tek etiketli taksonomi; alt tür bilgisi veride var ama kullanılmıyor | `recommend/genres.py` |
| K12 | Profil sanatçı düzeyinde; tür maruziyeti ve tür eğilimi öğrenilmiyor | `profile/build.py` |

**Temel çizgi (7 Kasım 2026, canlı Render/Neon panellerinden, salt okunur)**

| Ölçüt | Değer | Sonuç |
| --- | --- | --- |
| Neon CU (1–7 Kasım) | production 3,02 + staging 0,04 CU-saat (≈ 13–14/ay) | Kota riski (C1) şu an düşük |
| Neon hesaplama | 0,25 CU sabit, iki dalda; staging Expires: Never | Hazır |
| Neon depolama | 48,7 MB | 1 GB sınırının çok altında |
| Render OOM (7 gün) | Yok | Bellek (C3) şu an sorun değil |
| `/votes/queue` süreleri (7 Kasım 02:54–02:57 oturumu) | Hepsi 200; 337–1655 ms | G2 yavaşlığı desteklenmedi |
| Takılma anı | `seed` 41173 dört kez tekrarlandı (istemci "Yeniden dene" döngüsü); aynı anda `/library/import` iki kez 500 (Spotify 503) | Kök neden G1 + G6 |
| Diğer 5xx | 3 Kasım `/auth/login` 500'leri (o günkü geçiş, kapalı) | — |

Sonuç: Takılmanın ağırlık merkezi sunucu yavaşlığı değil, **Spotify'a bağımlılık (G6) ve istemcinin boş yanıtı yönetememesi (G1)**. PR-1, PR-2 ve PR-3 buna göre genişletildi.

## Hedef mimari

Sistem dört katmandan oluşur: veri (L1) ve kullanıcı modeli (L2) örnekleyiciyi (L3) besler, teslim katmanı (L4) sonucu bekletmeden sunar.

```
L1 Evren            (PR-0, PR-4)  Tür omurgası (ListenBrainz → MusicBrainz ISRC), iki seviyeli taksonomi,
                                  popülerlik bantları, temsil şarkıları, omurga sanatçılarıyla genişleyen graf
        │  hücreler, bantlar, temsil şarkıları
        ▼
L2 Kullanıcı modeli (PR-5)        Maruziyet haritası (tür × alt tür × bant), tür eğilimi (profile-4),
                                  tür-bandit (Thompson sampling) ve taban keşif oranı
        │  tür hedefleri, bandit örnekleri
        ▼
L3 Örnekleyici      (PR-6, PR-7)  Kaynak karışımı (kütüphane, öneri, sonda, joker), hücre seçimi, Gumbel-top-k,
                                  kalibre rerank: tür hedefi, sanatçı aralığı, benzerlik penceresi, şarkı tekilliği
        │  sıralı ve gerekçeli kartlar
        ▼
L4 Teslim           (PR-1..PR-3)  Hızlı yol + tampon, arka plan doldurucu (tek uçuş, advisory lock),
                                  ağır iş yürütücüsü, istemci kuyruk denetleyicisi (recent, geri çekilme, durum makinesi)
        │  hazır parti, milisaniyeler içinde
        ▼
Kesintisiz oylama akışı (mobil)
```

Pahalı her iş L1–L3'te ve arka planda yapılır; kullanıcının beklediği tek yol L4'ün hızlı yoludur.

## Yol haritası özeti

Sekiz PR üç blok hâlinde, sırayla uygulanır; her PR bittiğinde Claude Code durur, raporlar ve bir sonrakine geliştirici onayıyla geçer.

| PR | Başlık | Blok | Göç | APK | Boyut | Önkoşul | Algoritma sürümü |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PR-0 | Doğrulama spike'ı (salt okunur) | Zemin | — | — | S | — | — |
| PR-1 | Ölçüm ve arka plan hijyeni | Zemin | — | — | M | — | — |
| PR-2 | Hızlı yol ve tampon | Zemin | — | — | M | PR-1 | `queue-7` (davranış aynı) |
| PR-3 | İstemci kuyruk denetleyicisi | Zemin | — | Evet | M | PR-2 | — |
| PR-4 | Evren: tür omurgası | Evren | `0021` | — | L | PR-0 kapısı, PR-1 | — |
| PR-5 | Kullanıcı modeli | Evren | — | — | M | PR-4 | `profile-4` |
| PR-6 | Örnekleyici | Örnekleme | — | — | L | PR-3, PR-5 | `queue-8` |
| PR-7 | Liste tarafı | Örnekleme | — | — | M | PR-6 | `list-6` |

Blok sonu kapıları: Zemin bloğu bitince takılma sorunu canlıda 2–3 gün gözlenir; Evren bloğu bitince `queue_sim` kapsama raporu alınır; Örnekleme bloğu kabul ölçütleriyle kapanır.

## PR-0 — Doğrulama spike'ı

Amaç: omurganın dayandığı ListenBrainz verisinin gerçekte yeterli olup olmadığını, kod yazmadan ölçmek. Uygulama koduna dokunulmaz; çıktı bir rapordur.

**Yapılacaklar**

- [x] `spikes/lb_genre_probe.py` (salt okunur betik): seçilmiş ~20 alt tür (en az 5'i Türkçe: arabesk, Anadolu rock, Türkçe pop, Türkçe rap, Türk halk) için `GET /1/lb-radio/tags` çağrısı, 3 popülerlik bandıyla (`pop_begin`/`pop_end`).
- [x] Yanıt alanlarını kaydet: kayıt MBID, sanatçı MBID, başlık, popülerlik; yanıt süresi, hız sınırı başlıkları, token gerekip gerekmediği.
- [x] `GET /1/popularity/top-recordings-for-artist/{mbid}` için token ihtiyacını ve yanıt biçimini doğrula. — Token zorunlu (401); biçim ARCHITECTURE.md'de.
- [x] Örnek kayıtları MusicBrainz `recording/{mbid}?inc=isrcs` ile ISRC'ye çevir (1 istek/sn); çözülme oranını ölç.
- [x] Düşük popülerlik bandında etiket tutarlılığını elle örnekle (konu dışı kayıt oranı). — Kısmen: 2 tür işaretlendi (Türkçe rap 8/8, shoegaze 6/8 konu dışı, tek sanatçı baskın); sanatçı çeşitliliği kapıya eklendi.
- [x] Sonucu `docs/ARCHITECTURE.md`'ye "Faz 0 tipi doğrulama" olarak yaz.
- [x] Genişletilmiş prob (`spikes/lb_genre_probe2.py`): toplu ISRC çözümü (LB `metadata/recording`), `lb-radio` count=1000, sanatçı yolu (D) ve kardeş ISRC (E); 20 tür için kapı raporu. — Sonuç ARCHITECTURE.md "Genişletilmiş PR-0 probu"; yaklaşık 1340 istek (LB ≈ 890, MB ≈ 450, Deezer 0, Last.fm 0).
- [x] Kapıya ≥ 15 benzersiz sanatçı ve en büyük sanatçı payı ≤ %30 eklendi ve ölçüldü.
- [x] Türkçe 5 tür için elle işaretleme turları (halk, rap, arabesk, rock, pop), ülke/işaret dışlaması, dil düzeltmesi, havuz genişletme ve A_düz (sanatçı oranı x havuz) ile kapı yeniden okundu.
- [x] Kısmi tekrarlanabilirlik: ikinci tohum (kapı kararı değişmedi; Jaccard halk 1,00 bilgisiz, rap 0,92, rock 0,84, arabesk 0,54).

**Kapı**

- Alt tür başına ≥ 20 ISRC'li kayıt ve ≥ %60 MBID→ISRC çözümü → PR-4 planı geçerli.
- Tutmazsa B planı (MusicBrainz etiket araması + Last.fm `tag.getTopArtists`, izin koşuluyla) geliştiriciye sunulur; PR-4 başlamaz.
- **Sonuç (8 Kasım 2026, genişletilmiş prob):** kapı **geçti (nokta ve alt uç, tek tohum + kısmi tekrar), riskler belgede**: Türkçe 5/5, toplam 20/20 (C ≥ 20, A ≥ 15, pay ≤ %30); A_düz halk 21,8 [17,0–24,3], rap 37,0, arabesk 37,7, rock 45,9, pop 25,2. Riskler: seed2'de halk alt ucu 13,6, arabesk Jaccard 0,54, büyük arabesk isimleri ISRC'siz (PR-4b), pop tek örnek. PR-1 geliştirici onayı bekliyor.

**Öğrenilen kavram:** spike / fizibilite kapısı — belirsiz dış bağımlılığa mimari kurmadan önce en ucuz test.

## PR-1 — Ölçüm ve arka plan hijyeni

Amaç: takılmanın aşama sürelerini görünür kılmak ve doğrulanmış sızıntıları kapatmak; APK gerekmez, canlıya ilk giren PR budur.

**Yapılacaklar**

- [ ] **Ölçüm:** `/votes/queue` içinde aşama süreleri (aday, belirsizlik, sıralama, öneri) → `Server-Timing` başlığı + `requestlog` JSON alanları.
- [ ] **Tek engine:** `db.py`'ye süreç geneli `get_engine()` / ortak session factory; `deps.get_db`, `graph/auto.after_vote`, `run_round` bunu kullanır (her oyda yeni engine açılması biter).
- [ ] **Süreç geneli hız sınırlayıcı:** `sources/http.py`'de kaynak adına göre paylaşılan, kilitli `min_interval` (MusicBrainz 1 istek/sn gerçekten korunur).
- [ ] **Ağır iş yürütücüsü:** `app/jobs/worker.py` — tek iş parçacıklı kuyruk, anahtara göre birleştirme (debounce), kuyruk derinliği sınırı (`GraphSettings.worker_queue_max`), günlük.
- [ ] **Birleştirme:** `cast_vote` artık `after_vote`'u doğrudan çağırmaz; sanatçıyı yürütücüye bırakır, toplu işlenir.
- [ ] **Stale-while-revalidate:** `graph/service.get_matrix` ve `recommend/diverse.cached_labels` — önbellek varken yeni snapshot arka planda kurulur, atomik değiştirilir; yalnızca soğuk açılışta senkron.
- [ ] **Turun ertelenmesi:** `graph/scheduler` turu yürütücüye gönderir; son kullanıcı isteğinden `auto_expand_idle_seconds` sonra çalışır.
- [ ] **Bayrak altyapısı:** her yeni davranış için `Settings` alanı, canlı varsayılanı kapalı.
- [ ] **Yerel yeniden üretim:** `docker-compose.limits.yml` (`cpus: 0.1`, `mem_limit: 512m`) + `app/jobs/rapid_vote_bench.py` (100 oy, kart başına ~1 sn; p50/p95/maks, boş yanıt, 5xx, RSS).
- [ ] **Doküman:** `docs/DAGITIM.md`'deki "açılışta alembic çalışmaz" ifadesi düzeltilir (`Dockerfile` her açılışta `alembic upgrade head` çalıştırıyor).
- [ ] **Dış servis hatalarına dayanıklılık (G6):** Spotify 5xx/429 yanıtları (`library.py` içe aktarma, `adapters/spotify`) yakalanır ve istemciye 500 yerine `Retry-After` başlıklı **503** olarak, anlaşılır Türkçe mesajla döner; mevcut `_service_error` kalıbı kullanılır.
- [ ] **Kaynak istemcisi sağlamlığı (G7):** `sources/http.get_json` JSON olmayan/boş yanıtı `SourceError` sayar; `graph/expand` tek sanatçının hatasında `error` sayıp tura devam eder (mevcut `fetch_log` hata TTL'i kullanılır).

**Testler:** sınırlayıcının eşzamanlılık testi (iki thread aynı aralığı paylaşır), birleştiricinin tekilliği, matris değiştirme sırasında eski sürümün korunması, engine tekilliği; sahte Spotify 503 → `/library/import` 503 + `Retry-After`; sahte Last.fm HTML yanıtı → tur devam eder. Mevcut 322 backend testi geçmeli.

**Bitti tanımı:** bench raporunda önce/sonra p95, RSS ve Neon bağlantı sayısı; DURUM.md kaydı.

**Öğrenilen kavramlar:** gözlemlenebilirlik, kaynak sızıntısı, stale-while-revalidate.

## PR-2 — Hızlı yol ve tampon

Amaç: `GET /votes/queue` yalnızca hazır olanı okusun ve sıralasın (hedef p95 < 800 ms); pahalı işler arka planda, kullanıcı başına tek uçuşla yapılsın.

**Kavramlar**

- **Hazır öneri:** son ana listede `track_id`'si olan, oylanmamış ve kullanıcıya özel `UserTrackMeta` kaydı süresi dolmamış öğe. Mevcut tablolardan türetilir; yeni tablo yok.
- **Su seviyeleri:** hazır öneri sayısı `buffer_low_watermark` altına inince doldurucu tetiklenir, `buffer_target`'a kadar doldurur.
- **Tek uçuş:** Postgres advisory lock (`pg_try_advisory_xact_lock`, kullanıcı kimliğinden türetilen anahtar); Neon doğrudan bağlantı olduğu için güvenli.

**Yapılacaklar**

- [ ] `profile/suggest.py` ikiye ayrılır: `ready_suggestions` (salt okuma) ve `refill_buffer` (arka plan: profil/liste yenileme + sıradaki `refill_batch` kart için `find_card`).
- [ ] `profile/refill.py` (yeni): advisory lock, 429/ağ hatasında sessiz kesme, günlük; PR-1 yürütücüsünden çalışır.
- [ ] `profile/api.py` `queue()`: istek yolunda Spotify çağrısı, `ensure_fresh_list` ve `rebuild_profile` yok; yalnızca kütüphane + hazır öneriler. Su seviyesi altındaysa doldurucu tetiklenir.
- [ ] `cast_vote`: oy sonrası tampon kontrolü ve tetik.
- [ ] `config.py` `ProfileSettings`: `buffer_low_watermark`, `buffer_target`, `refill_batch`, `meta_refresh_at`, `meta_refresh_batch`.
- [ ] **Meta önbelleğinin önceden tazelenmesi (G6):** kullanıcının oylanmamış kütüphane parçalarının `UserTrackMeta` kayıtları TTL'in `meta_refresh_at` oranına (başlangıç 0,8) ulaşınca doldurucu tarafından arka planda Spotify'dan tazelenir; parti başına sınırlı (`meta_refresh_batch`), 429/5xx'te sessizce bırakılır. Spotify verisinin 24 saat kuralı değişmez; yalnızca süresi dolmadan yenilenir. Böylece kısa bir Spotify kesintisinde kuyruk kurumaz.
- [ ] Yanıt sözleşmesi değişmez (eski APK çalışır); `algo_version` `queue-7` kalır.

**Testler:** tampon boşken kuyruğun kütüphaneden anında dönmesi; iki eşzamanlı tetik → tek iş; Spotify hatasında tamponun bozulmaması; TTL'in %80'ini geçen meta kaydının tazelenmesi, sahte Spotify 503'te kaydın dokunulmadan kalması; mevcut kuyruk testlerinin geçmesi.

**Bitti tanımı:** `rapid_vote_bench`'te tampon boşken bile p95 < 800 ms, boş yanıt 0; Spotify'ın 10 dakika 503 döndüğü sahte senaryoda kuyruk kurumaz.

**Öğrenilen kavramlar:** hızlı yol / yavaş yol ayrımı, üretici-tüketici ve tampon, dağıtık kilit.

## PR-3 — İstemci kuyruk denetleyicisi

Amaç: `rating_screen` içine dağılmış bayrakları açık durumları olan, test edilebilir bir sınıfa taşımak; çıkmaz ekranı ve kaybolan doldurmayı bitirmek. Yeni APK gerektirir.

**Durumlar**

| Durum | Kullanıcının gördüğü | Geçiş |
| --- | --- | --- |
| Hazır | Kartlar | Kart < `prefetchBelow` → arka planda doldur |
| Dolduruluyor | İskelet kart (kart bittiyse) | Yanıt gelince Hazır; ihtiyaç sürüyorsa yeni istek |
| Sunucu uyanıyor | "Sunucu uyanıyor" + ilerleme | `/health` ısınması başarılı → Dolduruluyor |
| Çevrimdışı | Bağlantı uyarısı | Ağ dönünce Dolduruluyor |
| Tükendi | "Kütüphaneyi yenile" ve "Keşif listesine git" eylemleri | Eylemle Dolduruluyor |
| Hata | Hata kartı | Yalnızca kartlar bitmiş ve denemeler tükenmişse |

**Yapılacaklar**

- [ ] `mobile/lib/queue_controller.dart` (yeni, `ChangeNotifier`): tek uçuş + yeniden kontrol; `recent` üretimi (bekleyen kartlar + son 4 oy, en çok 20); üstel geri çekilme + jitter (1, 2, 4… en çok 30 sn).
- [ ] `mobile/lib/api.dart`: `voteQueue(..., List<int> recent = const [])`; istek başına zaman aşımı (kuyruk kısa, ısınma uzun); `health()`; `ApiException`'da zaman aşımı/çevrimdışı/5xx ayrımı.
- [ ] `rating_screen.dart`: doldurma mantığı denetleyiciye taşınır, ekran durumu çizer; "Yeniden dene" yalnızca doldurmayı çalıştırır; `prefetchBelow` 6 → 8; kaynak rozeti (Kütüphanenden / X'i sevdiğin için / Yeni bir tür / Sürpriz).
- [ ] Sunucu: `queue()` `recent` parametresini kabul eder (en çok `queue_recent_max` kimlik, aksi 422); bu parçalar adaylardan çıkarılır ve aralık geçmişi bunlarla başlatılır. Parametresiz istek bugünkü gibi çalışır.
- [ ] Oylama akışı ve tasarım dili değişmez.

**Testler:** `mobile/test/queue_controller_test.dart` — sahte API ile yavaş yanıt sırasında art arda oy (kart bitmez), çakışan yanıt (yinelenen kart yok), zaman aşımında sessiz deneme, soğuk açılış durumu. Backend: `recent` dışlama, geçersiz `recent` → 422, parametresiz uyumluluk. `flutter analyze` temiz.

**Bitti tanımı:** 100 kartlık hızlı oylamada (emülatör + sınırlı backend) çıkmaz ekran 0.

**Öğrenilen kavramlar:** sonlu durum makinesi, geri çekilme ve jitter, durumu sunucuya taşımak.

## PR-4 — Evren: tür omurgası

Amaç: kullanıcılardan bağımsız, müziğin tamamını alt tür ve popülerlik bandı düzeyinde temsil eden bir omurga kurmak; graf kullanıcı mahallesinin dışına gerçek yollarla uzansın. PR-0 kapısı geçilmeden başlamaz.

**Kavramlar**

- **İki seviyeli taksonomi:** 14 ana tür altında ~60–80 alt tür (ör. rap → trap, drill, boom bap, Türkçe rap; türk → arabesk, Anadolu rock, Türkçe pop, Türk halk). Mevcut `artist_tag` verisinden hesaplanır; `genres.py` eşleme tablosu veri olarak genişler.
- **Popülerlik bantları:** `known` (tanınır), `mid` (orta), `niche` (niş) — ListenBrainz `pop_begin`/`pop_end` pencereleriyle.
- **Temsil şarkısı:** sanatçının en çok dinlenen ilk K kaydından tohumlu örnek ("en düşük kimlik" yerine).

**Yapılacaklar**

- [ ] `sources/listenbrainz.py` (yeni): `lb_radio_tags`, `top_recordings_for_artist`; ortak `SourceClient`, süreç geneli hız sınırlayıcı, 429 geri çekilme. Token gerekiyorsa `.env`'de `LISTENBRAINZ_TOKEN`.
- [ ] `sources/musicbrainz.py`: `recording_isrcs(mbid)`.
- [ ] Göç `0021` (yalnızca ekleme): `genre_seed` (alt tür, ana tür, `artist_id`, `track_id`, bant, kaynak, `fetched_at`) ve parça popülerlik bandı (`track_popularity` veya `track` üstünde nullable sütun — PR başında karar, raporda gerekçe). Kişisel veri yok.
- [ ] `recommend/genres.py`: iki seviyeli tablo + saf `sub_genre(tags)`; `main_genre` davranışı geriye uyumlu.
- [ ] `app/jobs/build_genre_backbone.py`: ListenBrainz → MusicBrainz ISRC → `Track` + `genre_seed`; devam ettirilebilir (denenen bir daha sorulmaz, `fetch_tags` kalıbı), `--limit`, `--genre`; **bilgisayardan Neon'a** çalışır, canlı sunucuda koşmaz.
- [ ] Omurga sanatçıları için Last.fm 1 adım genişleme (mevcut `expand`/`fetch_one`); Last.fm 100 MB sınırı izlenir.
- [ ] `recommend/service._pick_tracks` → temsil şarkısı (popülerlik + tohum); veri yoksa eski davranış.
- [ ] D3: `cast_vote` — kütüphane veya liste öğesi değilse, kullanıcıya özel `UserTrackMeta` kaydı varsa kabul.
- [ ] CLAUDE.md: kural 7 (D4) ve yeni kaynak (D1) notları; `docs/ARCHITECTURE.md` omurga bölümü.
- [ ] Bayrak: `GRAPH_BACKBONE_ENABLED` (varsayılan kapalı).

**Testler:** taksonomi eşlemesi (Türkçe alt türler dahil), bant normalizasyonu, temsil şarkısı determinizmi (aynı tohum → aynı şarkı), `cast_vote` D3 (sunulmamış parça → 404), göç ileri/geri, omurga işinin devam ettirilebilirliği (sahte istemci).

**Bitti tanımı:** staging dalında omurga raporu (alt tür başına kayıt, ISRC oranı, graf boyutu, DB boyutu < 1 GB), ardından canlıda bayrak kapalı deploy.

**Öğrenilen kavramlar:** soğuk başlangıç, popülerlik yanlılığı, expand-only migration.

## PR-5 — Kullanıcı modeli

Amaç: sistemin kullanıcının müzik uzayında nerede gezdiğini ve hangi türe nasıl tepki verdiğini bilmesi. Hepsi saf fonksiyon, göç yok.

**Kavramlar**

- **Maruziyet haritası:** ana tür × alt tür × bant hücrelerinde gösterim ve tepki sayıları; oy, Unheard ve "sonra dinle" olaylarından türetilir.
- **Tür eğilimi:** oylardan yumuşatılmış (Laplace/Dirichlet öncüllü) tür ve alt tür dağılımı; kalibrasyondaki `p_kullanıcı(g)` buradan gelir.
- **Tür-bandit (Thompson sampling):** her tür bir kol; tohumlu örnek alınır. Awful alan tür küçülür, ama `genre_floor_share` ile sıfırlanmaz.

```
θ_g ~ Beta(a0 + Good+_g, b0 + Bad-_g)
```

**Yapılacaklar**

- [ ] `profile/exposure.py` (yeni, saf): `exposure_map(events, genre_of, band_of)`.
- [ ] `profile/build.py`: profil gövdesine `genres` bloğu (yumuşatılmış eğilim); `profile_algo_version` → `profile-4`.
- [ ] `recommend/genre_bandit.py` (yeni, saf): `genre_outcomes`, `sample_genre_scores(outcomes, seed, cfg)`.
- [ ] `config.py`: `genre_prior_a`, `genre_prior_b`, `genre_floor_share`, yumuşatma parametresi.

**Testler:** sentetik kullanıcılar — cazı sürekli kötü oylayan kullanıcıda caz payı düşer ama sıfır olmaz; hiç denenmemiş tür iyimser puan alır; determinizm (aynı olaylar + tohum → aynı skor).

**Öğrenilen kavramlar:** keşif-sömürü ikilemi, çok kollu bandit, Bayesçi güncelleme.

## PR-6 — Örnekleyici (`queue-8`)

Amaç: her partiyi dört kaynaktan, hedeflenmiş oranlarla ve kontrollü rastgelelikle doldurmak; azınlık türleri önden tüketip tek türe çöken bugünkü kuralın yerine kalibre bir sıralayıcı koymak.

**1. Kaynak karışımı** (`ProfileSettings`, olgunluğa göre doğrusal geçiş)

| Kaynak | Rol | Isınma (< 50 oy) | Olgun (> 200 oy) |
| --- | --- | --- | --- |
| Kütüphane | Tanıdık parçalarla zevki etiketlemek | %40 | %30 |
| Mahalle önerisi | PPR familiar/explore/far, gerekçeli | %10 | %40 |
| Tür sondası | Az gezilmiş hücre, tanınır bant ağırlıklı | %40 | %20 |
| Joker | Tamamen rastgele hücre, niş bant dahil | %10 | %10 |

Kütüphanesiz kullanıcıda kütüphane payı diğerlerine dağıtılır. Kaynak boşsa pay kütüphaneyle doldurulur; parti asla küçülmez.

**2. Hücre seçimi** (sonda ve joker): puan(hücre) = κ / √(1 + o hücrede gösterilen kart) + θ(tür), θ = PR-5 tür-bandit örneği. İlk terim az gezilmiş hücreye iyimserlik, ikincisi tutma olasılığı.

**3. Kontrollü rastgelelik (Gumbel-top-k):** argmax yerine sıra = argsort(skor + τ · G), G = −ln(−ln U), U tohumdan üretilir. Skorların softmax'ıyla orantılı, yerine koymadan örneklemeye eşdeğer; τ=0 bugünkü davranış; aynı tohum aynı sıra.

**4. Son sıralama (rerank)**

- Kalibrasyon: hedef(g) = (1 − ε) · p_kullanıcı(g) + ε · eşit(g); her yuvada açığı en büyük ana tür.
- Sanatçı aralığı 4; art arda aynı alt tür yok.
- Graf benzerlik penceresi: son `queue_sim_window` (3) parçaya kosinüsü `queue_sim_max` üstünde olan aday ertelenir.
- Şarkı tekilliği (`song_key`); etiketsiz sanatçıya topluluk etiketi (`blend_labels`).
- Uygun aday yoksa kademeli gevşeme: önce alt tür, sonra benzerlik, sonra ana tür, en son sanatçı.

**Yapılacaklar**

- [ ] `profile/sampler.py` (yeni, saf): `source_mix`, `cell_scores`, `gumbel_order`, `rerank`.
- [ ] `profile/active.py`: `diversify` kaldırılır (rerank devralır); `order_active` korunur.
- [ ] `profile/api.py` `queue()`: dört kaynak birleşik havuzda; öğeye `source` ve gerekçe (PPR veya kapsama, D4).
- [ ] `profile/refill.py`: tampon tür açığına ve kaynak payına göre doldurulur (sonda/joker kartları da önceden çözülür).
- [ ] `config.py`: `queue_mix_warm`, `queue_mix_mature`, `queue_genre_epsilon`, `queue_gumbel_tau`, `queue_coverage_kappa`, `queue_sim_window`, `queue_sim_max`, `queue_history_size`; `queue_algo_version` = `queue-8`; canlıda kapalı/sıfır başlar.
- [ ] `app/jobs/queue_sim.py` (salt okunur): 100 kartlık simülasyon → en uzun aynı tür serisi, 20'lik pencerede tür sayısı, sanatçı tekrarı, keşif payı, iki oturum örtüşmesi.

**Testler:** determinizm (aynı tohum → aynı sıra, farklı tohum → farklı sıra), seri üst sınırı, azınlık türün önden tükenmemesi, gevşeme sırası, ε=0 ve τ=0'da eski davranışa yakınsama, kaynak boşken parti boyutu.

**Öğrenilen kavramlar:** calibrated recommendations (Steck, 2018), Gumbel-max hilesi, UCB tarzı iyimserlik, çok amaçlı yeniden sıralama.

## PR-7 — Liste tarafı (`list-6`)

Amaç: aynı ilkeleri Keşfet ekranındaki öneri listesine indirmek; uzak öneriler "bitişik olası"dan başlasın, "Yeniden üret" gerçekten taze liste versin.

**Yapılacaklar**

- [ ] `recommend/diverse.pick_far`: iki kademe — önce eğilimi düşük ama sıfır olmayan türler (bitişik olası), sonra tek bir gerçekten uzak yuva.
- [ ] `recommend/bandit.py` / `service.generate_list`: `far` payı tür-bandit sonuçlarına bağlanır (sabit %20 yerine taban + öğrenilen pay).
- [ ] `max_cluster_share` 0,5 → 0,35.
- [ ] Temsil şarkıları (PR-4) liste öğelerinde de kullanılır.
- [ ] "Yeniden üret": Gumbel-top-k ile tohumlu tazelik; `list_algo_version` → `list-6`; parametreler `generated_list.params`'a yazılır.
- [ ] `generate_list` için far/tür uçtan uca testi (DURUM S1-25'teki açık).

**Testler:** bitişik olası sırası, tavan, bandit bağlantısı, determinizm, uçtan uca liste testi; `evaluate` raporunda slot başına Good+ oranı.

**Öğrenilen kavram:** bitişik olası (adjacent possible) — keşif bilinen sınırın hemen ötesinde en verimlidir.

## Canlı geçiş protokolü ve bütçe

Mağaza yayınına kadar kullanıcı sayısı artmayacağı için ücretsiz Render + Neon yeterli; şartı aşağıdaki korumalar. Yayında Render Starter (7 USD/ay, 0,5 CPU, uykusuz) ve gerekirse Neon Launch gerekir; ikisi de yalnızca plan değişikliği, göç yok.

**Sınırlar (Kasım 2026)**

| Kaynak | Sınır | Bizim için anlamı |
| --- | --- | --- |
| Render ücretsiz | 512 MB RAM, 0,1 CPU; 15 dk boşta uyur, ~1 dk uyanır; ayda 750 instance saati | Ağır iş istek yolunda olamaz; soğuk açılış istemcide yönetilir |
| Neon ücretsiz | Proje başına ayda 100 CU-saat, 1 GB depolama; kota dolarsa hesaplama dönem sonuna kadar askıya alınır | Azami CU 0,25'e sabitlenir; arka plan işleri toplu ve yalnızca aktif kullanımda |

**Her PR için protokol**

1. Göç varsa önce `pg_dump` yedeği.
2. Göç ve ağır işler önce Neon **staging dalında** prova edilir.
3. Yeni davranış canlıya **bayrak kapalı** girer; Render ortam değişkeniyle açılır (ör. `PROFILE_QUEUE_DISCOVERY_SHARE=0.1` → ölçüm temizse 0.3).
4. İzleme: Render günlüklerinde `Server-Timing`, 5xx, yeniden başlatma/OOM; Neon panelinde günlük CU-saat.
5. Geri alma: bayrağı kapat veya Render'da önceki deploy'a dön; göçler yalnızca ekleme yaptığı için şema geri alınmaz.

**Bilinçli olarak yapılmayan:** Render'ı uyanık tutan dış pinger. Uygulama uyanık kalınca periyodik turlar Neon kotasını tüketir.

**Sıra:** PR-1 canlıya ilk girer; PR-2, ardından PR-3 (yeni APK). Keşif PR'ları (4–7) zemin bloğu 2–3 gün sorunsuz çalıştıktan sonra girer. Omurga inşası canlı sunucuda değil, bilgisayardan Neon'a koşar.

Kaynaklar: [Render](https://render.com/articles/from-side-project-to-production-scaling-your-first-app) · [Neon ücretsiz plan](https://neon.com/faqs/free-plan-limits-and-quotas)

## Kabul ölçütleri

Program, aşağıdaki ölçütler sınırlı yerel ortamda (`rapid_vote_bench`, `queue_sim`) ve ardından canlıda karşılandığında tamamlanmış sayılır.

| Alan | Ölçüt | Ölçüm aracı | İlgili PR |
| --- | --- | --- | --- |
| Güvenilirlik | 100 hızlı oyda çıkmaz ekran 0, 5xx 0 | `rapid_vote_bench`, emülatör | PR-1–3 |
| Hız | Sıcak sunucuda `/votes/queue` p95 < 800 ms (tampon boşken de) | `Server-Timing`, bench | PR-2 |
| Soğuk açılış | Hata yerine "Sunucu uyanıyor", kuyruk kendiliğinden gelir | Emülatör | PR-3 |
| Kapsama | İlk 50 oyda ≥ 10 ana tür; ilk 200 oyda ≥ 30 alt tür (sert kaçınılanlar hariç) | `queue_sim` | PR-4–6 |
| Çeşitlilik | 20 kartta ≥ 5 ana tür; aynı sanatçı 20 kartta ≤ 2, son 4'te 0; aynı şarkı sürümü 0; en uzun aynı alt tür serisi 1 | `queue_sim` | PR-6 |
| Tazelik | İki ardışık oturumun ilk 20 kartı örtüşmesi < %20; aynı tohumla %100 | `queue_sim`, birim test | PR-6 |
| Kalite koruması | Sonda/joker kartlarında Good+ oranı genel ortalamanın ≥ %60'ı; "Dinlemedim" < %50 | `evaluate` | PR-6–7 |
| Bütçe | Neon CU < 60/ay, OOM 0, Last.fm verisi < 100 MB, DB < 1 GB | Neon/Render panelleri, `graph_stats` | Tümü |

Kalite koruması altına düşülürse ε, τ ve sonda payı otomatik değil, geliştirici onayıyla düşürülür.

## Riskler ve edge-case'ler

En yüksek iki risk Neon kotasının dolması ve keşfin kullanıcıyı sıkması; ikisi de ölçümle ve bayraklarla kontrol altında.

| Risk | Etki | Önlem |
| --- | --- | --- |
| Spotify kesintisi / 503 (canlıda gözlendi) | Yüksek: kuyruk kurur, "Yeniden dene" döngüsü | PR-1 503 + `Retry-After`; PR-2 meta önceden tazeleme ve tampon; PR-3 istemci geri çekilmesi ve anlaşılır durum |
| Neon CU kotası dolar | Yüksek: uygulama dönem sonuna kadar durur | Azami CU 0,25; engine sızıntısı kapanır; arka plan işleri toplu; haftalık CU kontrolü |
| 0,1 CPU'da arka plan/istek yarışı | Yüksek: takılma sürer | Tek iş parçacıklı yürütücü; istek yolu Spotify ve liste üretiminden bağımsız |
| 512 MB'da OOM | Orta | Bench'te RSS ölçümü; gerekirse KMeans `n_init` düşürülür (onayla) veya etiketler bilgisayarda hesaplanır |
| Açılışta göç hata verir | Orta: servis açılmaz | Yalnızca ekleme yapan göç; staging dalında prova; `pg_dump` yedeği |
| ListenBrainz alt tür kapsaması zayıf (özellikle Türkçe) | Orta | PR-0 kapısı; B planı hazır |
| Lisans (MetaBrainz, Last.fm) | Yayını engeller | Yayın öncesi kalemi; omurga bayrakla kapatılabilir |
| Tanınmayan şarkı seli | Orta: "Dinlemedim" artar | Sonda tanınır bant ağırlıklı; niş bant yalnız joker ve olgun kullanıcıda; önizlemesi olmayan kart sondada sunulmaz |
| Önizleme kaynağı (Deezer yalnızca kapalı test) | Yayını etkiler | Mağaza öncesi Apple Music önizlemesi (Faz 7 kalemi) |
| Popülerlik yanlılığı | Düşük–orta | Bant karışımı + kapsama iyimserliği; sanatçı maruziyet Gini katsayısı izlenir |
| Tek tür seven kullanıcı | Düşük | Kalibrasyon zevki baskın tutar (1 − ε); bandit Awful alan türü küçültür; taban oran rahatsız etmez |
| Eski APK | Düşük | Tüm yeni parametreler isteğe bağlı, yanıt alanları yalnızca eklenir |
| Spotify çağrı bütçesi / 429 | Düşük–orta | Çözümleme arka planda, partiler hâlinde, geri çekilmeli; önbellek tekrar çözümü önler |
| Determinizm kaybı | Orta | Tüm rastgelelik tohumdan; birim testlerle sabitlenir |
| Program karmaşıklığı | Orta | Her PR bağımsız değer üretir ve kapatılabilir; ölçüm beklentiyi karşılamazsa sonraki PR'ın kapsamı yeniden sunulur |

## Geliştiricinin işleri ve açık sorular

Bu işler geliştiricinin hesaplarında ve elindedir; Claude Code bunları yapamaz.

**Başlamadan önce**

- [x] Neon panelinde azami CU'yu 0,25'e sabitle (otomatik ölçeklemeyi kapat). — 7 Kasım 2026
- [x] Neon'da `staging` dalı aç (canlı verinin kopyası, Expires: Never). — 7 Kasım 2026
- [x] Güncel `pg_dump` yedeği al: `backups/tini-2026-11-07.dump` (1,3 MB). — 7 Kasım 2026
- [x] Temel çizgi (Neon CU, Render Events/Logs) — bkz. Teşhis → Temel çizgi. — 7 Kasım 2026
- [x] Sızan production parolası sıfırlandı, Render `DATABASE_URL` güncellendi, PowerShell geçmişi temizlendi. — 7 Kasım 2026

**Program sırasında**

- [ ] **PR-4'ten önce:** `staging` dalının `neondb_owner` parolasını sıfırla (dal, sızan eski parolayla kopyalandı) ve `backend/.env.staging` dosyasını `DATABASE_URL=postgresql+psycopg://...?sslmode=require` ile oluştur.
- [x] PR-0 için gerekirse ücretsiz ListenBrainz hesabı aç ve token'ı `.env`'e `LISTENBRAINZ_TOKEN` olarak ekle.
- [ ] Her PR sonunda Render ortam değişkenleriyle bayrakları aç ve sonucu gözle.
- [ ] PR-3 sonrası yeni APK'yı testçilere dağıt.
- [ ] Omurga işini (PR-4) staging'de, ardından canlı Neon'a bilgisayardan koştur; CU kullanımını izle.

**Yayın öncesi (Faz 7'ye eklenir)**

- [ ] MetaBrainz ticari kullanım koşullarını oku (ListenBrainz/MusicBrainz).
- [ ] Last.fm ticari izin e-postası (mevcut açık kalem).
- [ ] Render Starter + gerekirse Neon Launch bütçesi.

**Açık sorular**

- Yanıtlandı (7 Kasım 2026): OOM yok; takılma sunucu yavaşlığından değil Spotify 503 + istemci boş yanıt döngüsünden (Teşhis → Temel çizgi).

## Claude Code çalışma kuralları ve ilerleme takibi

Claude Code her PR'ı aynı dört aşamayla yürütür ve geliştiricinin açık "Onaylıyorum" / "Uygulamaya geç" komutu olmadan dosya değiştirmez.

**Her PR için akış**

1. **Keşif (salt okuma):** ilgili dosyaları oku, varsayım yapma; planın o PR bölümünü kod tabanıyla karşılaştır.
2. **Analiz:** teşhis, en fazla 2 yaklaşım, etki haritası (dosya/fonksiyon), riskler; plandan sapma varsa gerekçesiyle belirt.
3. **Onay kapısı:** dur, onay iste.
4. **Uygulama ve doğrulama:** yalnızca onaylanan kapsam; testleri çalıştır; DURUM.md'yi ve bu dosyadaki görev kutularını/İlerleme tablosunu güncelle; özet + komutlar + sonuçlar.

**Kurallar**

- CLAUDE.md'deki değişmez kararlar geçerlidir; D1–D5 bu planla onaylıdır, başka bir sapma için sor.
- Algoritma kodu saf fonksiyon; rastgelelik yalnızca tohum parametresiyle; parametreler `*Settings`'te; her profil/liste/kuyruk yanıtına algoritma sürümü.
- Dış çağrılar yalnızca `sources/` ve `adapters/` içinde; Spotify verisi kalıcı saklanmaz.
- Yeni davranış bayrakla gelir, canlı varsayılanı kapalı.
- Göçler yalnızca ekleme yapar; önce staging dalında.
- İlgisiz refaktör yok; mevcut adlandırma, hata yönetimi ve tasarım diline sadık kal.
- Dal: `feat/<pr-no>-<kısa-ad>` (ör. `feat/pr1-observability`); commit mesajları İngilizce, dokümanlar Türkçe.

**Doğrulama komutları**

```bash
docker compose up -d db
cd backend && alembic upgrade head && pytest && ruff check .
C:/dev/flutter/bin/flutter analyze   # mobile/ içinde
C:/dev/flutter/bin/flutter test
docker compose -f docker-compose.yml -f docker-compose.limits.yml up -d   # PR-1 sonrası
python -m app.jobs.rapid_vote_bench   # PR-1 sonrası
python -m app.jobs.queue_sim --email <e-posta>   # PR-6 sonrası
```

**İlerleme**

| PR | Başlık | Durum | Dal / PR | Not |
| --- | --- | --- | --- | --- |
| PR-0 | Doğrulama spike'ı | Tamamlandı, onay bekliyor | `feat/pr0-lb-spike` | İlk ölçüm kapıyı geçmedi (8/20); genişletilmiş probda **geçti** (A_düz nokta ve alt uç; tek tohum + kısmi tekrar): Türkçe 5/5, toplam 20/20, ≈ 1340 istek; riskler ARCHITECTURE.md'de; commit/PR-1 onayı bekliyor |
| PR-1 | Ölçüm ve arka plan hijyeni | Başlamadı | | |
| PR-2 | Hızlı yol ve tampon | Başlamadı | | |
| PR-3 | İstemci kuyruk denetleyicisi | Başlamadı | | |
| PR-4 | Evren: tür omurgası | Başlamadı | | |
| PR-5 | Kullanıcı modeli | Başlamadı | | |
| PR-6 | Örnekleyici `queue-8` | Başlamadı | | |
| PR-7 | Liste tarafı `list-6` | Başlamadı | | |

Durum değerleri: Başlamadı · Analiz/onay bekliyor · Uygulanıyor · Canlıda (bayrak kapalı) · Tamamlandı
