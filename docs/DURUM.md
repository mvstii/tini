# Tını — Güncel Durum

Son güncelleme: 31 Ekim 2026 · Her aşama (PR) sonrasında güncellenir.

## Özet

- **Faz:** Faz 1, 2 ve 3 tamamlandı (Faz 3: S1–S5 ve işbirliği düğümü düzeltmesi birleşti, kapı geçildi, 30 Ekim 2026; plan `docs/FAZ3_PLAN.md`). Güncel faz: Faz 4 — Mobil deneyim ve çıktı (plan `docs/FAZ4_PLAN.md`, onaylandı). Açık kalemler: sanatçı etiketleri, Last.fm izin e-postası (senin işin), Deezer/Apple MusicKit doğrulaması (Faz 6 öncesi).
- **Faz 1 kapısı geçildi (30 Ekim 2026):** emülatörde hesap açıldı, Spotify bağlandı, kütüphane aktarıldı (531 bağlantı, 524 parça veritabanında).
- **Faz 0:** tamamlandı. Kalan kullanıcı işleri: partners@last.fm'e izin e-postası, `.env.example` şablonunu geri koymak, Spotify'daki "tini-spike" ve "tini-spike-2" çalma listelerini silmek.

## Faz 1 aşamaları

| # | Aşama | Durum | PR |
|---|---|---|---|
| 1 | Backend iskeleti, Docker Compose (Postgres + pgvector), CI | Bitti | #2 |
| 2 | Veri modeli ve ilk Alembic göçü | Bitti | #3 |
| 3 | Hesap sistemi (e-posta + parola, oturum) | Bitti | #4 |
| 4 | Spotify OAuth (PKCE), şifreli servis bağlantısı | Bitti; gerçek Spotify ile doğrulandı (30 Ekim 2026), token'lar veritabanında şifreli | #5 |
| 5 | Servis adaptörü arayüzü + Spotify adaptörü (kütüphane okuma, token yenileme) | Bitti; gerçek hesapla doğrulandı (531 parça, 1 atlandı) | #6 |
| 6 | Kütüphane içe aktarma (`POST /library/import`; kaydedilenler + top items) | Bitti; gerçek hesapla doğrulandı (524 parça, 531 bağlantı, 1 atlandı; meta TTL 24 sa) | #7 |
| 7 | Flutter iskeleti (giriş, servis bağlama, boş oylama ekranı) | Bitti; analyze + 4 test geçti, Android emülatöründe uçtan uca doğrulandı | #8 |

## Faz 2 aşamaları

| # | Aşama | Durum | PR |
|---|---|---|---|
| S1 | Kaynak altyapısı + MusicBrainz + kademe A (göç 0004 sanatçı tabloları, `catalog.resolve`, `python -m app.jobs.enrich`) | Kod ve birim testler hazır (46 testten 45 geçiyor); gerçek MusicBrainz ile doğrulandı (30 Ekim 2026, 20 parça: 10 eşleşti, 10 boş, 0 hata → %50) | #12 |

| S2 | Last.fm + kademe B/C + güven (`sources/lastfm.py`, `catalog/resolve_b.py`, `catalog/confidence.py`) | Kod ve birim testler hazır (59 test geçiyor, 1 eski hata); gerçek Last.fm ile ölçüldü (30 Ekim 2026) | #13 |

**S2 ölçümü (524 parça, tek kişinin sahnesi):** A (ISRC→MusicBrainz) 252 (%48) · B (Last.fm, ad) 271 (%52) · C (eşleşmedi) 1 (%0,2). 246 sanatçı, 63'ü MBID'siz (yalnızca Last.fm kimliği). Düşük güvenli (<0,8) B eşleşmeleri incelendi; hepsi doğru (Türkçe `ı`/`i` farkı). Bu yüzden `normalize_name` `ı`'yı `i`'ye katlıyor (kaydedilmiş `name_norm` yeniden hesaplandı). Çok yüksek B oranı Last.fm'in ad aramasının cömertliğini gösterir; B bağları adın doğruluğuna dayanır ve ISRC'ye göre daha zayıftır (güven 0,6–0,9). Genellenmez.

| S3 | Kenar deposu + tembel genişleme (göç 0005 `artist_edge`/`graph_snapshot`, saf `graph.expansion.plan_expansion`, `python -m app.jobs.expand`) | Kod ve testler hazır (73 test geçiyor, 1 eski hata); gerçek Last.fm ile ölçüldü (30 Ekim 2026) | #14 |

**S3 ölçümü (246 çapa sanatçı, derinlik 1):** 224 sanatçının kenarı var, 22'si Last.fm'de boş; 4376 kenar, 2210 farklı komşu, ortalama ağırlık 0,565, tablo 776 kB (100 MB sınırının çok altında). Tekrar çalıştırmada önbellek isabeti %100, 0 çağrı. Derinlik 2 tahmini: ~2200 yeni sanatçı çağrısı (≈20 dk, 0,25 sn aralık), ~40–50 bin kenar, ~4 MB. Derinlik 2 henüz tam çalıştırılmadı; S4 öncesinde çalıştırılacak.

| S4 | Matris kurucu + komşuluk (`graph/matrix.py`, `graph/neighborhood.py`, `GET /graph/neighborhood`, SciPy/NumPy eklendi) | Kod ve testler hazır (94 test, 93 geçiyor + 1 eski hata); **Faz 2 kapısı geçildi** (30 Ekim 2026) | #15 |

**Kapı ölçümü (gerçek veri, derinlik 2 genişletme sonrası):** 2291 sanatçının kenarı var (22 sanatçı Last.fm'de boş), 45.148 kenar, 10.930 farklı komşu, tablo 7 MB. Uç nokta: soğuk (matris kurulumu dahil) 195 ms, sıcak p50 10 ms / p95 13 ms / en kötü 21 ms (200 parça). Hedef < 3 sn. 200 parçadan 30'u 404 döndü (sanatçısı grafikte kenarsız, yani Last.fm'de boş olan 22 sanatçıdan). Sentetik ölçek testi: 1 milyon kenarda kurulum 0,46 sn, sorgu 1,6 ms; 4 milyon kenarda 2,8 sn ve 3 ms.

S4 notları: Varsayılanlar: simetrikleştirme `max`, normalizasyon `sym` (D^-1/2 A D^-1/2), derinlik 2'de en güçlü 10 komşu genişler, listeler 20 ile sınırlı (hepsi `GraphSettings`). Matris süreç içinde, son `graph_snapshot` sürümüne bağlı önbellekte; çok işçili dağıtımda her işçi kendi kopyasını kurar (Faz 3'te paylaşılan önbellek gerekebilir). Süresi dolan kenarlar yeni snapshot üretilmeden matrise yansımaz. Last.fm ağırlıkları popüler sanatçıya yanlıdır; normalizasyon kısmen azaltır, asıl çözüm Faz 3'te. Ölçüm tek kişinin sahnesine ait.

S3 notları: Kenar kaynağı `artist_edge.source` (şimdilik `lastfm`). Komşu başına üst sınır 20 (`GraphSettings.edge_max_neighbors`). Genişleme `fetch_log` kaynağı `lastfm_similar`, anahtar `artist:<id>` (kademe B'nin `lastfm`/`track:` anahtarlarından ayrı). Boyut: 80 MB uyarı, 100 MB üstünde en eski kenarlar atılır (silme boyutu hemen küçültmez, bu yüzden atılacak satır sayısı orantılanır). Bilinen sınır: önbellek durumu belleğe yüklenir; yüzbinlerce kenarda Faz 3'te sayfalanmalı. Adı olan ama MBID'si olmayan komşu, başka yoldan gelen aynı sanatçıyla ayrı satır olabilir (MBID çelişkisi riskine karşı bilerek birleştirilmiyor).

S2 notları: Kademe B bağı yalnızca `user_track_artist`'te; `track.artist_id` değişmez. Güven eşiği 0.6 (`GraphSettings`). `fetch_log` Last.fm anahtarı `track:<id>` (Spotify dizesi içermez). Last.fm API anahtarı URL'de gittiği için enrich işi httpx INFO loglarını susturur.

S2 notları: Net eğilim = Σ skor·ağırlık (sanatçı başına). Pozitif sanatçılar grafik matrisindeki satırlarına göre (L2 normalize) KMeans ile kümelenir; k = min(`cluster_count`=8, sanatçı // `cluster_min_artists`=3), tohum `cluster_seed`; küme kimlikleri ağırlığa göre yeniden sıralanır (deterministik). Grafikte olmayan sanatçılar `unclustered`. Çapa = net pozitif ve Amazing'li sanatçı; kaçınma = net negatif sanatçı, Awful içerense `hard`. Çözülmemiş sanatçılı oylar sayılır ama profile girmez (`unresolved_votes`). Gerçek grafikte duman testi (508 parça, hepsi Great varsayımıyla, yalnız kademe A sanatçıları): 114 sanatçı, 8 küme (5–45 üye), 13 kümesiz, 0,10 sn. Sanatçı başına tek vektör; küme merkezleri saklanmaz (S3'te PPR başlangıç vektörleri çapalardan kurulur).

S1 notları: `fetch_log` anahtarı `(source, key)` (ör. `isrc:…`), plandaki `(artist_id, source)` yerine; ISRC aramasında henüz sanatçı yok. Çok sanatçılı kayıtta ilk kredi alınır. Ortam dosyasına `MUSICBRAINZ_CONTACT` gerekir; yoksa içe aktarma sonrası arka plan işi çalışmaz.
Gerçek doğrulama: göç 0004 uygulandı; hesapsız, yalnızca `User-Agent` ile çalıştı, 429 görülmedi. Tüm kütüphane çalıştırıldı (30 Ekim 2026): 524 parçadan 252'si MusicBrainz'de eşleşti (%48, 114 sanatçı), 272'si boş (kademe B/C adayı), 0 hata, 429 yok. Plandaki ~%28 beklentisinden yüksek; ölçüm tek kişinin sahnesine ait, genellenmez.
Not: `test_models::test_account_delete_removes_personal_data_only` S1 sırasında düzeltildi (Faz 3 / S1 notlarına bak).

## Faz 3 aşamaları

| # | Aşama | Durum | PR |
|---|---|---|---|
| S1 | Oy olayı + güncel oy (`POST /votes`, `GET /votes/current`, saf `profile/scoring.py`, `ProfileSettings`) | Kod ve testler hazır (107 test geçiyor) | #16 |
| S2 | Profil anlık görüntüsü (göç 0006 `taste_profile`, saf `profile/build.py`, `POST /profile/rebuild`, `GET /profile`, scikit-learn eklendi) | Kod ve testler hazır (119 test geçiyor); gerçek grafikte duman testi yapıldı | #17 |
| S3 | PPR aday skoru + gerekçe (saf `recommend/ppr.py`, `RecommendSettings`, `GET /recommend/candidates`) | Kod ve testler hazır (132 test geçiyor); gerçek grafikte duman testi yapılmadı | #18 |
| S4 | Liste üretimi (göç 0007 `generated_list`+`list_item`, saf `recommend/select.py` MMR, `POST /lists/generate`, `GET /lists/{id}`) | Kod ve testler hazır (141 test geçiyor) | #19 |
| S5 | Sentetik uçtan uca testler (`tests/test_synthetic.py`) + elle bakış işi (`python -m app.jobs.preview_list EPOSTA`) | Kod ve testler hazır (147 test geçiyor); **Faz 3 kapısı geçildi** (30 Ekim 2026) | #20 |

S5 notları: Kapı gerçek oylarla (79 oy, 48'i Amazing, 26 çapa) elle bakıldı (`python -m app.jobs.votes_csv` ile CSV'den oy girişi, `preview_list` ile liste). Gerekçeler gerçek çapalara bağlanıyor ve mantıklı; Drake baskınlığı nedeniyle varsayılanlar ayarlandı: `anchor_boost` 2,0→1,5, `novelty_gamma` 0,3→0,4, `mmr_lambda` 0,7→0,6 (liste çeşitlendi: metal ve East Coast rap çıktı). Bilinen kusur: işbirliği/ekip düğümleri ("Drake & 21 Savage", "Young Money", "JACKBOYS") ayrı sanatçı sayılıyor; sanatçı etiketleri/kanonikleştirme kalemiyle birlikte ele alınacak. Oy CSV'si `local/` altında, git dışı.

**İşbirliği düğümleri (Faz 3 sonrası, PR'ı):** göç `0008` `artist_member`; `app/catalog/collab.py` adı `&`, `and`, `x`, `,`, `feat.` ile parçalar ve her parça katalogda kenarı olan ayrı bir sanatçıysa düğümü işbirliği sayar ("Tyler, The Creator", "Captain & Tennille" yakalanmaz). `python -m app.jobs.detect_collabs` tabloyu yeniden yazar (harici çağrı yok; geliştirme veritabanında 259 düğüm). Öneri, işbirliği düğümlerini kendi başına listelemez. Kapsam dışı: ekip/etiket düğümleri (Young Money, JACKBOYS, A$AP Mob) gerçek grup sayıldı; işbirliği kenarlarının üyelere aktarılması yapılmadı. Yeni çıkan sanatçılar için işi grafik genişletmesinden sonra çalıştır.

S4 notları: Liste öğeleri sanatçı düzeyindedir, bu yüzden sanatçı başına en çok bir öğe (üst sınır) doğal olarak sağlanır. MMR benzerliği grafik matrisi satırlarının kosinüsüdür (λ=0,7, boyut 20). Sanatçı içi şarkı: paylaşılan katalogdaki, oylanmamış en düşük kimlikli parça; yoksa `track_id` boş. Başlık yalnızca kullanıcıya özel önbellekte olduğundan listede yoktur. Adaylar henüz katalogda parçası olmayan sanatçılar için çalma Faz 4/5 adaptörlerine kalır.

S3 notları: Skor tohum vektörlerine göre doğrusaldır; gerekçe katkı paylarından okunur (ilk 3 pozitif tohum). Awful düğümleri her adımda maskelenir; Bad/Meh kaçınma sanatçıları negatif tohumdur (β=0,5); yenilik çarpanı 1+γ·(1−derece persentili), γ=0,3. Oy verilmiş tüm sanatçılar adaylardan çıkarılır. Yalnızca pozitif skorlu adaylar döner.

S1 notları: Güncel oy = parçanın son olayı (id sırası). Persentil normalizasyonu ≥30 güncel oyda, işaret grubu başına mid-rank persentil, soğuk skorla harmanlanır (`normalize_blend` 0,5). Zaman sönümü yarı ömür 365 gün, taban 0,25; Awful sönmez. Oy yalnızca kullanıcının kütüphanesindeki parçaya verilir (Faz 4'te Unheard havuzu gelince gevşer). İki eski test (`test_models::test_account_delete_removes_personal_data_only`, `test_catalog_b::test_low_confidence_is_tier_c`) geliştirme verisinden bağımsız hâle getirildi (sorgular kendi satırlarına daraltıldı; 31 Ekim 2026).

## Ortam

- Windows 11, Python 3.12, Docker Desktop 4.97, Flutter 3.47.9 (`C:\dev\flutter`, PATH'te değil).
- Yerel çalıştırma: `docker compose up -d db`, ardından `backend` içinde `alembic upgrade head` ve `pytest`.
- Android toolchain (`flutter doctor`) henüz denetlenmedi; Aşama 7'den önce yapılacak.

## Alınan kararlar (Faz 1)

- Spotify'dan gelen başlık/sanatçı/süre yalnızca kullanıcıya özel TTL'li önbellekte (`user_track_meta`); paylaşılan katalogda yalnızca ISRC/MBID ve türetilmiş veri (29 Ekim 2026, onaylı).
- Oturumlar rastgele değerdir; veritabanında yalnızca SHA-256 özeti saklanır. Parolalar argon2.
- `vote_event` tablosunda UPDATE veritabanı tetikleyicisiyle engelli.
- Hibrit grafik modeli: PPR sanatçı düğümlerinde; Last.fm izni gelmeden üretim bağımlılığı sayılmaz (ayrıntı `docs/ARCHITECTURE.md`).

## Yerel kurulum notları

- Spotify dashboard'da redirect URI'ler: `http://127.0.0.1:8000/connect/spotify/callback` (backend) ve `http://127.0.0.1:8888/callback` (Faz 0 betikleri). Eklerken Add ve ardından Save gerekir.
- `.env` içinde `SPOTIFY_CLIENT_ID` ve `CREDENTIAL_KEY` (Fernet anahtarı) tanımlı olmalı; anahtar kaybolursa kayıtlı token'lar çözülemez.
- Boş `.env` satırları (ör. `SPOTIFY_REDIRECT_URI=`) varsayılana düşer.

## Faz 4 aşamaları (plan: `docs/FAZ4_PLAN.md`)

| # | Aşama | Durum | PR |
|---|---|---|---|
| S1 | Backend: `GET /votes/queue` (oy almamış sanatçılar önde, sanatçı başına sırayla, tohumlu deterministik; süresi dolmuş önbellekli parçalar atlanır, `stale` ile sayılır), `GET /votes/history` (parça başına güncel oy), liste öğesine `title`. Göç yok. | Kod ve testler hazır (157 test geçiyor) | #25 |
| S2 | Mobil: kaydırmalı oylama kartları (`RatingScreen`: 6 oy düğmesi, sağa kaydır = Great, sola kaydır veya düğme = Unheard, geri al, 30 oyluk başlangıç turu ve "Profili kur", eskiyen önbellek için "Kütüphaneyi yenile"). `Api`: `voteQueue`, `castVote`, `voteTotal`, `rebuildProfile`. | Kod ve widget testleri yazıldı; yerelde çalıştırılamadı (yerel Dart 3.13.5 < gereken 3.13.7), CI doğruladı | #26 |
| S3 | Keşif listesi: göç 0009 `list_feedback` (kişisel olay kaydı), `POST /lists/{id}/items/{pos}/feedback` (`wrong_reason`, isteğe bağlı `seed_id` öğenin gerekçesinde olmalı), mobil `ListScreen` (sanatçı kartı, "keşif" slot etiketi, yüzdeli gerekçe cümlesi, çapa ★, "Bu gerekçe yanlış"). | Backend 159 test geçiyor, ruff temiz; mobil testler CI'da | S3 PR'ı |
| S4 | "Spotify'da aç": adaptöre `open_url` (ISRC → `spotify:track:` araması, bulunamazsa `spotify:search:<sanatçı>`), `GET /lists/{id}/items/{pos}/open`, mobil `ListScreen` düğmesi (`url_launcher`, SDK yok). Göç yok. | Backend 164 test geçiyor, ruff temiz; mobil 13 test + analyze yerelde geçti | #28 |
| S5 | Spotify'a yazma + geçmiş: `POST /lists/{id}/export/{service}` (ISRC → parça kimliği, atlananlar raporlanır; adaptöre `find_track`), mobil "Spotify'a kaydet", `HistoryScreen` (oy geçmişi + oy değiştirme). Göç yok. | Backend 167 test geçiyor, ruff temiz; mobil 15 test + analyze yerelde geçti | S5 PR'ı |

S1 notu: `stale > 0` ise istemci `POST /library/import` ile önbelleği yeniler (Spotify'dan canlı yenileme S1'de yok). Liste öğesinin `title` alanı yalnızca parça kullanıcının kütüphanesindeyse dolar; önerilen parçalar çoğunlukla kütüphanede olmadığı için başlık S4'te ISRC→Spotify çözümüyle gelir.
S2 notu: Unheard backend'e yazılmaz (oy 1–6); oturum içinde atlanır, parça sonraki oturumda kuyruğa yeniden gelebilir. Geri al, kartı yeniden gösterir; verilen yeni oy yeni bir olaydır (eski olay silinmez).
S4 notu: ISRC çözümü tıklama anında yapılır ve saklanmaz (Spotify kimliği hiçbir yerde kalıcı değil); plandaki "kullanıcıya özel önbellek" bu yüzden gerekmedi, her tıklama bir arama çağrısıdır (429 geri çekilme adaptörde). Spotify hata verirse veya parça katalogda yoksa sanatçı araması açılır. App Remote spike'ı yapılmadı: uygulama içi dinleme Faz 5+'a ertelendi (Development Mode ve Premium doğrulanmadı). Canlı doğrulama (telefon/emülatörde Spotify uygulaması) henüz yapılmadı.
S5 notu: Dışa aktarma yalnızca katalogda parçası olan öğeleri yazar; sanatçı düzeyindeki (parçasız) öğeler atlanır ve konumlarıyla raporlanır, hiçbiri çözülemezse çalma listesi oluşturulmaz. Önerilen sanatçıların çoğunun parçası olmadığından çalma listesi kısa çıkabilir; canlı ölçümden sonra `/search?q=artist:` ile sanatçı başına parça çözümü ayrıca onaya sunulacak. 403 (kapsam yok) 409 olarak döner; istemci yeniden bağlamayı söyler. Oy geçmişi ekranında oy değiştirme yeni bir `POST /votes` olayıdır. **Faz 4 kapısı** (emülatörde oyla, listeyi Spotify'a kaydet) canlı doğrulamayla kapanacak.

**Canlı test bulguları (31 Ekim 2026, emülatör):**
- Bağlama, kütüphane aktarma, oylama, profil, liste üretimi, oy geçmişi çalışıyor.
- Spotify `POST /users/{id}/playlists` 403 veriyor; `POST /me/playlists` çalışıyor (istemci buna geçirildi).
- İlk dışa aktarma 20 öğenin yalnızca 3'ünü yazdı (sanatçı düzeyindeki öğelerin ISRC'li parçası yok). Onaylanan çözüm: `find_artist_track` (`/search?q=artist:"<ad>"`, sonuçta sanatçı adı eşleşmeli; ISRC yoksa/çözülmezse yedek; hem `export` hem `open` yolunda). 169 backend testi geçiyor, ruff temiz. **Canlı denendi (31 Ekim 2026): 20 öğenin 17'si yazıldı, 3'ü atlandı** (önceki 3/20). **Faz 4 kapısı geçildi.**
- Atlanan 3 öğe teşhis edildi (31 Ekim 2026): "Travi$ Scott" (ad farkı), "NAV" (kısa ad, doğru sanatçı arama 2. sayfasında; sayfa limitten kısa dönebilir), "Child Rebel Soldier" (Spotify'da yok, doğru atlama). `find_artist_track` artık adı `$`/aksan/noktalama toleranslı karşılaştırır ve en çok 3 sayfa tarar (boş sayfada durur). Canlıda yalnızca Spotify'da olmayan sanatçı atlanıyor (18/20 bekleniyor; çalma listesi yeniden yazımıyla doğrulanmadı, çözümleme canlı kontrol edildi). Dışa aktarma yanıtı `skipped_names` döner ve liste ekranı atlanan sanatçı adlarını gösterir.
- Emülatörde Spotify uygulaması kurulu olmadığı için "Spotify'da aç" açılmaz (mesaj düzeltildi); gerçek telefonda denenmeli.
- `backend/.env` içinde `CREDENTIAL_KEY` ve `SPOTIFY_CLIENT_ID` boştu, dolduruldu. Anahtar değişince eski `service_connection` satırları çözülemez (InvalidToken → 500); satırlar silindi, yeniden bağlandı. Emülatörde OAuth dönüşü için `adb reverse tcp:8000 tcp:8000` gerekir (adb: `C:\src\android-sdk\platform-tools\adb.exe`).

**Yapılacaklar (sırayla):**
1. ~~Artist-track canlı denemesi, commit + PR #29, kapı~~ Yapıldı (17/20). Kalan: #28 ardından #29'u birleştir (#29 tabanını `main` yap). Auto-fix #29'da reddedilmişti.
2. ~~Sağlamlaştırma: `InvalidToken` → 409~~ Yapıldı: `connections._decrypt` `InvalidToken`'ı `PermissionError`'a çevirir, çağıranlar 409 döner (testli).
3. Faz 5 (sistemsel): Unheard durum makinesi + aktif öğrenme kuyruğu, Thompson sampling slot dağılımı, takip listesi/yayın tespiti/haftalık Taze listesi, "Yeni" akışı, değerlendirme betikleri. Önce plan sunulup onay alınır (`docs/FAZ5_PLAN.md`).
4. En sonda: UI yenileme ve şarkı kapakları. Plan: kapak URL'si `user_track_meta.image_url` (Spotify, TTL'li, kullanıcıya özel; dosya saklanmaz); liste/kuyruk/geçmiş yanıtlarına `image_url`; kapak yoksa yer tutucu; koyu temalı, kapak ağırlıklı kart tasarımı. Şema değişikliği olduğundan başlamadan onay alınır.
S3 notu: Gerekçe itirazı yalnızca kayıttır; profile/algoritmaya etkisi Faz 5'te. Liste öğeleri parça başlığı taşımaz (önerilen parçalar kütüphanede olmadığından); başlık/çalma S4'te.


## Faz 5 aşamaları (plan: `docs/FAZ5_PLAN.md`, onaylandı)

| # | Aşama | Durum | PR |
|---|---|---|---|
| S1 | Unheard durum makinesi (göç 0010 `unheard_event`, saf `profile/unheard.py`, `POST /votes/unheard`, mobil sola kaydırma, N=3 sunumda −0,05 sönümlü örtük negatif, `profile-2`) | Kod ve testler hazır (187 backend testi, Flutter 15 test, analyze temiz); emülatörde doğrulandı | #32 (birleşti) |
| S2 | Aktif öğrenme kuyruğu (göç yok; saf `profile/active.py`, `profile/active_service.py`, `ppr.artist_scores`, `GET /votes/queue` → `queue-2`: belirsizlik = PPR skorunun persentil yakınlığı, havuz bonusu, süresi dolanlar dışarıda, sunulan havuz parçası `awaiting`) | Kod ve testler hazır (196 backend testi, ruff temiz) | #33 (birleşti) |
| S3 | Slot dağılımı (göç 0011 `list_item.slot`, saf `recommend/bandit.py` Thompson sampling, `recommend/outcomes.py` türetilen sonuçlar, `generate_list` slot başına MMR, `list-2`) | Kod ve testler hazır (203 backend testi, ruff temiz) | #34 (birleşti) |
| S4 | Yayın kaynağı spike'ı + takip listesi (göç 0012 `release`, `release_artist`, `followed_artist`; `releases/follow.py`, `releases/service.py`, `python -m app.jobs.detect_releases`, `GET/PUT/DELETE /releases/following`) | Kod ve testler hazır (210 backend testi, ruff temiz); gerçek MusicBrainz ile çalıştırıldı (1 Kasım 2026: 47 takip sanatçısı, 47 sorgu, 0 hata, 50 yeni yayın) | #35 (birleşti) |
| S5a | Taze liste + "Yeni" akışı (göç 0013 `generated_list.kind`, `list_item.release_id`, slot `fresh`; `recommend/fresh.py`, `POST /lists/generate-fresh`, `GET /releases/new`, mobil "Yeni çıkanlar" ekranı) | Kod ve testler hazır (217 backend + 17 Flutter testi, ruff/analyze temiz) | #36 (birleşti) |
| S5b | Ana listede "Yeni" yuvası (`list-3`, `fresh_share` 0.12, albüm kartı; mobil rozet) | Kod ve testler hazır (219 backend + 18 Flutter testi, ruff/analyze temiz) | #37 (birleşti) |
| S6 | Değerlendirme betiği (`recommend/metrics.py` saf ölçütler, `python -m app.jobs.evaluate EPOSTA`, salt okur; `eval_min_sample` 10) | Kod ve testler hazır (226 backend testi, ruff temiz); gerçek hesapta çalıştı. **Faz 5 kapısı geçildi** (1 Kasım 2026, emülatör; ayrıntı aşağıda) | #38 (birleşti) |

S1 notu: Sola kaydırma geri alınamaz olay yazar (olay kaydı silinmez); mobildeki "geri al" yalnızca kartı oturumda geri getirir. S2'de kuyruk, havuzdaki parçaları sunar.

## Açık riskler

- Last.fm ticari izni gelmeyebilir (Faz 5 S4'te MBID'siz sanatçılar için ikincil yayın kaynağı olarak denenecek; mağaza yayını öncesi izin hatırlatılacak); yedek: ListenBrainz + kendi birlikte-oluşum matrisi.
- Apple Music Android SDK ve Flutter bağlayıcısı doğrulanmadı (Faz 7 öncesi kontrol).
- Spotify Şubat 2026 duyurusu okunmadı.
- Faz 0 örneği tek kişinin müzik sahnesi; kapsam sayıları genellenmeyebilir.

S2 notu: Belirsizlik = 1 − |2p − 1|; p = sanatçının PPR skorunun, sinyalli sanatçıların skor dağılımındaki mid-rank persentili. Sinyali olmayan sanatçı `active_unknown_uncertainty` (0,75) alır; havuzdaki parça `active_pool_bonus` (0,5) kazanır. Profil/graf yoksa herkes 'bilinmiyor' sayılır. Oy almamış sanatçılar ve sanatçı başına tur sırası korunur.

S3 notu: Slotlar: `unheard` (havuz sanatçısı, öğenin parçası havuz parçası), `familiar` (kalan adayların üst yarısı, PPR), `explore` (alt yarısı). Havuz sanatçısı aday listesinde (PPR üst-N, bilinen sanatçılar hariç) değilse unheard'e giremez; gerekçe zorunluluğu bunu gerektirir. Toplam sonuç < 10 iken pay öncüldür (0,40/0,35/0,25); sonra Beta(1+başarı, 1+başarısızlık) örneği, %10 taban payla harmanlanır; tohum = profil sürümü. Başarı = liste sonrası sanatçıya son oy ≥ 4; başarısızlık = itiraz veya son oy ≤ 2. Eski listelerin öğeleri `explore` sayılır. Slotun adayı yetmezse taşan kontenjan diğerlerine gider. Paylar ve sonuçlar `generated_list.params` içinde.

S4 notu: Spike sonucu `ARCHITECTURE.md`'de (MusicBrainz arama ucu + tarih aralığı birincil; ListenBrainz ve `release-group` listeleme kullanılmadı; MBID'siz sanatçılar kapsam dışı). Otomatik takip türetilir (profildeki çapa, küme ve kümesiz sanatçılar); `followed_artist` yalnızca elle takip (`manual`) ve otomatiğin bırakılması (`muted`) tutar, sanatçı başına tek kayıt. Tespit penceresi 120 gün, yeniden sorgu aralığı 7 gün (`RELEASES_` ayarları); `fetch_log` anahtarı `mb_release / artist:<id>`. Hatalı sorgu önbelleğe yazılmaz. Yeniden yayınlar (`first-release-date` yeni görünenler) S5'te sıralamada ele alınır.

S5a notu: Taze liste albüm düzeyindedir (öğe = release-group, parça yok; ISRC eşlemesi sonraya). Skor = sanatçı PPR skoru x 0.5^(yaş/14 gün); gerekçe `explain()` ile PPR doğrusal ayrışımından gelir. Pencere 30 gün, boyut 15, sanatçı ve yayın başına bir kez; önceki Taze listelerde çıkan yayın tekrarlanmaz. Yayın yoksa 409. Slot sonuçları (bandit) yalnızca `kind='main'` listelerden türetilir. Ana listede %10–15 "Yeni" payı S5b'de (yayın -> oylanabilir parça eşlemesi gerekir); ROADMAP satırı o zamana kadar işaretsiz.

S6 notu: Ölçütler FAZ5_PLAN'dakiyle aynı, tek fark: "tahmin hatası" yerine skor ↔ sonraki oy Spearman sıra korelasyonu (PPR skoru oy ölçeğinde olmadığından ortalama mutlak hata anlamsız). Oran paydası "liste sonrası oylanan" öğedir; oylanmayanlar paydada değil, bu yüzden "sunulan" da raporlanır. Taze albüm kartı oylanamaz: yalnızca sunulan sayısı ve sanatçıya sonradan Good+ gösterilir, korelasyona girmez. `eval_min_sample` (10) altında "yetersiz veri" yazar. İlk gerçek çalıştırma: 100 öğe sunulmuş, 0 oylanmış, 1 havuz parçası; yani kapı için oylama + canlı deneme gerekir.

**Faz 5 kapı denemesi (1 Kasım 2026, emülatör + gerçek backend):** sola kaydırma Unheard olayı yazdı (havuz 4 parça), Taze liste üretildi ve "Yeni çıkanlar" ekranında albüm kartları gerekçeleriyle göründü (örn. The Game 'Unreleased Lost Files', Snoop Dogg 'The Hollow'); ana listelerde 9 "fresh" öğe. `evaluate` raporu: 127 sunulan öğe, 0 liste sonrası oylanan (oylanan parçalar önerilen sanatçılardan değildi), itiraz %0; oranlar anlamlı olmak için gerçek oylama gerektirir (Faz 6'da 5 kullanıcıyla). Canlıda bulunan hata: sola/sağa kaydırınca debug'da kırmızı ekran ("dismissed Dismissible is still part of the tree"): `_answer` kartı sunucu yanıtından sonra siliyordu. Düzeltildi: kart hemen çıkar, kayıt başarısızsa geri gelir; regresyon testi (yavaş sunucu) eklendi.

S5b notu: Ana listede "Yeni" yuvası bandit dışı sabit paydır (`round(list_size x fresh_share)`, uygun yayın kadar); kalan kontenjan üç yuvaya dağıtılır, yeni yuva listenin sonuna eklenir. Yuvadaki sanatçı diğer yuvalardan çıkarılır. Öğe albüm kartıdır (parça yok, oylama yok; "Spotify'da aç" sanatçı aramasına gider); yayın -> parça eşlemesi ve oylama sonraya. Ana veya Taze listede çıkan yayın bir daha önerilmez. Yeni yuva slot sonuçlarına (bandit) girmez.
