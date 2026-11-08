# Tını — Mimari Özeti

Bu dosya mimari dokümanın depo içindeki özetidir. Güncel ve ayrıntılı sürüm Claude Docs'taki **"Tını — Mimari Doküman ve Proje Planı"** dokümanıdır.

Son güncelleme: 29 Ekim 2026

## Alınan kararlar

| Konu | Karar |
|---|---|
| Yayın stratejisi | Bağımsız çekirdek; Apple Music tam entegre; Spotify kapalı test (en fazla 5 kullanıcı) |
| Öneri motoru | Ana motor: geniş müzik evreninden benzerlik grafiği. Yan modül: yeni çıkanlar takibi |
| Dinleme | Uygulama içi dinleme veya servisinde açma; ek olarak 30 sn kesit |
| Yeni çıkanlar | Haftalık Taze listesi + ana listede %10–15 pay + uygulama içi "Yeni" akışı |
| Akustik analiz | v1'de yok; v2'de ölçülerek eklenir |
| Oy değiştirme | Serbest; olay kaydı, son oy geçerli |
| Gerekçeler | Her öneride zorunlu; hesaptan türetilir |

## Oy skorları (soğuk başlangıç)

| Oy | Skor | Rol |
|---|---|---|
| Awful | −1.0 | Sert filtre, kaçınma bölgesi |
| Bad | −0.6 | Yumuşak ceza |
| Meh | −0.15 | Zayıf negatif |
| Good | +0.35 | Profili besler |
| Great | +0.7 | Profili güçlü besler |
| Amazing | +1.0 | Çapa |
| Unheard | — | Keşif havuzu adayı |

En az 30 oydan sonra kullanıcının kendi dağılımına göre persentil normalizasyonu ve zaman sönümü uygulanır.

## Öneri hattı

1. **Profil:** pozitif oylar zevk modlarına kümelenir, Amazing şarkılar çapadır; negatif oylar ayrı kaçınma bölgesidir.
2. **Grafik:** Last.fm, ListenBrainz, MusicBrainz ve etiket ortaklığından oluşan, çapaların 2–3 adım çevresine tembel genişleyen benzerlik grafiği.
3. **Aday skoru:** kişiselleştirilmiş PageRank − kaçınma bölgesine benzerlik cezası + yenilik bonusu. Awful düğümleri budanır.
4. **Gerekçe:** PPR başlangıç vektörüne göre doğrusal olduğu için her adayın skoru çapa katkılarının toplamıdır; en çok katkı veren 1–3 çapa gerekçe olarak saklanır.
5. **Liste:** MMR ile çeşitlilik, sanatçı başına üst sınır, Thompson sampling ile slot dağılımı (bilinen / Unheard / keşif).

## Unheard durum makinesi

Havuzda → Sunuldu → Oylama bekliyor → Oylandı. N kez sunulup oylanmayan şarkı "Süresi doldu" durumuna geçer ve çok zayıf örtük negatif sayılır. Oylama kuyruğu aktif öğrenmeyle (en belirsiz tahmin önce) sıralanır.

## Veri modeli (varlıklar)

Kullanıcı · Servis bağlantısı · Parça · Sanatçı · Kimlik eşleme · Eşleme kaydı · Grafik kenarı · Etiket · Parça özellikleri · Oy olayı · Güncel oy · Unheard havuzu · Zevk profili · Üretilen liste · Liste öğesi · Gerekçe itirazı · Takip listesi · Yayın · İş kaydı

İlke: oylar silinmeyen olay kaydıdır, profiller sürümlü anlık görüntülerdir.

## Spotify kısıtları (Ekim 2026)

- Kasım 2024: recommendations, audio-features, audio-analysis, related-artists kapandı; preview_url boş.
- Şubat 2026: Development Mode için Premium gerekli, uygulama başına en fazla 5 kullanıcı; new releases ve artist top tracks kaldırıldı, popularity alanı silindi, arama sayfa başına 10 sonuç.
- Korunan: ISRC (external_ids), account_id.
- Genişletilmiş erişim: kayıtlı kuruluş ve 250 bin aylık aktif kullanıcı.

## Faz 0 bulguları: kullanım koşulları ve kaynak durumu (29 Ekim 2026, sayfalardan okundu)

Betik ölçümleri (Spotify uç noktaları, %80 kapısı) henüz çalıştırılmadı; aşağısı yalnızca belge/sayfa okumasıdır.

**Spotify Developer Terms, sürüm 10 (15 Mayıs 2025):**
- Spotify içeriğiyle ML/AI modeli eğitmek veya içeriği bir modele almak yasak (karar 5 doğrulandı).
- Yerel önbellek yalnızca performans için gerekli olduğu ölçüde ve geçici; yalnızca metadata/kapak görseli (veya koşullu indirmeler). "Spotify içeriğini süresiz saklama" yasak.
- Risk: Faz 1 kapısı "kütüphane veritabanına iner" ve Faz 2 ISRC/ID tabloları bu kurala çarpabilir. Spotify'dan gelen veri kalıcı katalogun parçası yapılmamalı; kalıcı kimlik kaynağı MusicBrainz/ISRC olmalı. Geliştirici kararı gerekir.

**Last.fm API ToS:**
- Ticari veya araştırma amaçlı kullanım için önceden partners@last.fm'e yazmak gerekiyor.
- Lisans geçici ve "Reasonable Usage Cap" ile sınırlı: toplam en fazla 100 MB Last.fm verisi; fazlası için yazılı izin gerekir. Paylaşılan benzerlik grafiği önbelleği (Faz 2) bu sınırı aşabilir.
- HTTP başlıklarına uygun önbellekleme, alt lisans verilemez, Last.fm'e atıf gerekir, gelecekte gelir paylaşımı hakkı saklı.

**Deezer:**
- `api.deezer.com/chart/0/tracks` kimlik doğrulamasız çalışıyor ve süreli imzalı `preview` URL'si veriyor.
- `editorial/0/releases` ve `editorial/132/releases` boş döndü (`total: 0`); yeni çıkanlar kaynağı olarak güvenilmez. Doküman sayfası girişe yönlendirdi, yeni uygulama kaydının açık olup olmadığı doğrulanamadı.

**Apple Music:**
- Apple MusicKit sayfası: MusicKit for Android (giriş + çalma kütüphaneleri) var; Apple Music API Apple platformları, Android ve web için; kullanıcı izniyle playlist oluşturma/değiştirme ve kütüphaneye ekleme destekleniyor. Aktif Apple Music aboneliği çalma için kontrol ediliyor.
- Doğrulanmadı: Android SDK'nın olgunluk durumu, Developer Program ücreti, API'de 30 sn kesit alanı.

**Alınan kararlar (29 Ekim 2026):**
- Spotify: parçanın kalıcı kimliği ISRC/MBID; Spotify yanıtları yalnızca TTL'li önbellekte (başlangıç 24 saat, yapılandırmadan); Spotify ID yalnızca kullanıcıya özel eşleme. Oy kayıtları kendi kimliğimize bağlanır.
- Last.fm: ham yanıt saklanmaz, kompakt kenar yazımı (≤~20 komşu/düğüm), 100 MB üst sınırı izlenir; ticari kullanım ve gerekirse daha büyük kota için partners@last.fm'e başvurulur.
- Kaynak ağırlığı: çekirdek ListenBrainz + MusicBrainz ilişkileri (+ Discogs stilleri, koşulları okunduktan sonra); Deezer related ve Last.fm ikincil. Son karar Faz 0 kapsam ölçümüne (yaygın/niş katman) göre verilir.
- MusicBrainz kullanıcı etiketleri ve oyları CC BY-NC-SA'dır (bilgi birikimine dayanır, doğrulanmadı); ticari kullanımda etiket yerine ilişkiler ve resmî türler kullanılır.
- Niş kapsam yetersiz çıkarsa Faz 2'de ListenBrainz dökümlerinden kendi eşzamanlı dinleme matrisimiz hesaplanır.

**Kısa önizleme (3 Kasım 2026, geliştirici kararı):** şarkılar 30 sn'lik kesit olarak çalınır (telif için tam parça yok). Kaynak Deezer `track/isrc:` ve `search` yanıtlarındaki imzalı, süreli `preview` URL'si; `GET /preview` bunu istek anında çözer, hiçbir yere yazmaz, ses dosyası indirilmez (istemci yayın olarak çalar, `just_audio`). Deezer ToS'u ticari kullanıma kapalı olduğundan **yalnızca kapalı test**; mağaza öncesi Apple Music önizlemesine geçilir (borç).

**Sanatçı fotoğrafları (3 Kasım 2026, geliştirici kararı):**
- Kaynak Deezer sanatçı arama API'sidir (`/search/artist`, anahtarsız). Yalnızca URL saklanır (`artist_image` tablosu, TTL 14 gün, bulunamayan 3 gün); görsel dosyası saklanmaz, fotoğrafı olmayan sanatçıda baş harfli yer tutucu çıkar.
- Deezer koşulları görsel saklamayı yasaklar ve ticari kullanım için anlaşma ister (canlı koşullar tam doğrulanmadı). Bu yüzden kaynak **yalnızca kapalı testte** kullanılır; mağaza yayını öncesi Apple Music veya Wikimedia ile değiştirilir (borç, Last.fm ticari izni gibi).
- Çağrılar yalnızca `app/sources/deezer.py` istemcisinde; istek başına en çok `fill_limit` (8) sorgu, hata/429'da durur ve hata kaydedilmez.

**Betik ölçümleri (29 Ekim 2026, geliştirici hesabı, Development Mode):**

Spotify uç noktaları (`spikes/spotify_probe.py`):
- 200: `/me`, `/me/tracks`, `/me/top/tracks`, `/me/top/artists`, `/me/player/recently-played`, `/search` (limit 10), `/artists/{id}/albums`, `/search?q=isrc:`; `POST /me/playlists` 201 (playlist oluşturma çalışıyor).
- Kapalı (beklendiği gibi): `/recommendations` 404; `/audio-features`, `/artists/{id}/top-tracks`, `/artists/{id}/related-artists`, `/browse/new-releases` 403.
- `POST /playlists/{id}/tracks` 403 verir (gövde veya sorgu `uris`, ayrıca `PUT` da); playlist kullanıcıya ait ve kapsam doğru. **`POST /playlists/{id}/items` 201 verir:** şarkı ekleme uç noktası `/items` olarak değişmiş (`spikes/playlist_probe.py` ile ölçüldü). Adaptör `/items` kullanmalı; eski `/tracks` yoluna dayanma.
- Örnek: 100 şarkı, 99'unda ISRC.

Kaynak kapsamı (`spikes/coverage_probe.py`, n=102; 100 kütüphane + 2 niş liste; 97'sinde Last.fm dinleyici sayısı var ve çoğu `<50000`, yani örnek ağırlıklı olarak niş; "yaygın" katman yalnızca 3 şarkı, o katman için sonuç anlamsız):

| Ölçüt | Oran |
|---|---|
| ISRC | %98 |
| MBID (ISRC 15 + metin 14) | %28 |
| Last.fm benzer şarkı | %8 |
| ListenBrainz benzer kayıt | %2 (niş katmanda %0) |
| Deezer related artists | %89 (sanatçı düzeyinde, 20 komşu) |
| MusicBrainz ilişki / tür | %7 / %9 |
| Last.fm etiket | %2 |

Yorum:
- %80 kapısı sayısal olarak geçildi (%89), ama yalnızca Deezer'ın **sanatçı düzeyindeki** related verisi sayesinde. Şarkı düzeyinde benzerlik niş içerikte neredeyse yok (Last.fm %8, ListenBrainz %2). Kapı, tasarımın şarkı düzeyinde grafik varsayımını doğrulamıyor.
- MBID eşlemesi %28: ISRC'den MusicBrainz'e geçiş niş katalogda zayıf. "Kalıcı kimlik = ISRC/MBID" kararında MBID tek başına yetmez; ISRC birincil, MBID isteğe bağlı olmalı.
- ListenBrainz algoritma adı labs.api.listenbrainz.org/similar-recordings sayfasında doğrulandı (kullanılan ad listede var): %2 gerçek veri seyrekliği, adlandırma hatası değil. `similar-artists` ucu ayrı algoritma listesiyle mevcut.
- Açık karar: grafiği sanatçı düzeyinde mi kuracağız (Deezer related, 20 komşu/sanatçı) yoksa şarkı düzeyinde kendi eşzamanlı dinleme matrisimizi mi hesaplayacağız. Deezer koşulları henüz okunmadı.

**Deezer for Developers Terms of Use (developers.deezer.com/termsofuse, 29 Ekim 2026 okundu):**
- Bölüm IV: hizmet "kesinlikle ticari olmayan amaç ve ortamla" sınırlı; geliştirici hizmetten veya içerikten doğrudan/dolaylı gelir, veri veya başka karşılık elde edemez, marka/logoyla ilişkilendirilemez.
- Bölüm IX: sayılanlar dışındaki kullanım Deezer'ın önceden incelemesine ve onayına bağlı. Bölüm II(c): Deezer erişimi istediği zaman, gerekçesiz kısıtlayabilir veya kaldırabilir.
- Sonuç: Deezer verisi Faz 0 ölçümü için uygundur ama mağazada yayınlanacak ticari bir uygulamanın çekirdek bağımlılığı olamaz; yazılı onay alınmadıkça üretimde kullanılmaz. Rate limit bu sayfada yok.
- Etki: "sanatçı grafiği = Deezer related" varsayımı tek başına yeterli değil; Deezer'a yazılı izin başvurusu veya ikinci bir sanatçı benzerliği kaynağı (ListenBrainz sanatçı benzerliği, MusicBrainz ilişkileri, kendi matrisimiz) gerekir.

**Sanatçı grafiği ölçümü (`spikes/graph_probe.py`, 25 farklı sanatçı, 29 Ekim 2026):**
- Deezer sanatçı eşlemesi 25/25 (hepsi ISRC ile). Ortalama 18,9 komşu/sanatçı; 2 adımda ortalama 78 benzersiz sanatçı.
- Kenarlar yönlü: ilk 5 komşuda karşılıklılık %55. PPR'dan önce simetrikleştirme veya yönlü kullanım kararı gerekir.
- Elle bakılan 8 sanatçıda komşular mantıklı ve türce tutarlı (niş Türk rap kümesi ve rock kümesi ayrı çıkıyor). Kütüphanedeki sanatçılara 1 adımda 19/25, 2 adımda 23/25 ulaşıldı. Uyarı: örnek tek kişinin, tek bir sahneye yoğun zevki; bu oran başka zevklere genellenmez.
- **Deezer ↔ MusicBrainz sanatçı eşlemesi zayıf:** 25'ten 6'sı doğrulanmış bağlantıyla eşleşti, 11'i yalnızca ad benzerliğiyle (doğrulanamadı), 7'si MusicBrainz'de yok, 1'inde bağlantı çelişiyor. Niş sanatçılarda MBID'ye güvenilemez; sanatçı kimliği için kendi tablomuz (normalize ad + sağlayıcı kimlikleri, MBID isteğe bağlı) gerekir.
- Deezer ticari kullanıma kapalı olduğu için üretimde alternatif kaynak ölçüldü (`spikes/artist_sources_probe.py`, aynı 25 sanatçı):

| Kaynak | ≥10 komşu | Not |
|---|---|---|
| Last.fm artist.getSimilar | %96 | Komşular mantıklı (Murda/Ezhel kümesi tutarlı) |
| ListenBrainz similar-artists | %12 | MBID bulunan %40'ın yalnızca 3 sanatçısında dolu; niş için yetersiz |
| Last.fm veya ListenBrainz (Deezer'siz) | %100 | Last.fm'den geliyor |

  Last.fm–Deezer ilk-20 örtüşmesi ortalama 0,27 (24 sanatçı); iki bağımsız kaynak farklı listeler veriyor, biri diğerini doğrulamıyor. Last.fm'i ad ile sorgulamak belirsiz adlarda yanlış sanatçıya çözülebilir (UZI için Fransız rapçiler çıktı); mümkünse MBID ile sorgula. Örnek 25 sanatçı, tek kişinin sahnesi.
- **Karar (29 Ekim 2026): hibrit model.** PPR sanatçı düğümlerinde çalışır; sanatçı içinde şarkı seçimi kullanıcı oyları ve etiketlerle yapılır; şarkı düzeyinde kenarlar (Last.fm, ListenBrainz) varsa ek sinyal olur. Üretim sanatçı benzerliği kaynağı: Last.fm (ikincil kaynak kuralı, 100 MB sınırı ve partners@last.fm izni koşuluyla). Deezer yalnızca ölçüm/geliştirme, üretimde yazılı izin olmadan kullanılmaz. Yedek: kullanıcı oylarından ve ListenBrainz dökümlerinden kendi sanatçı eşzamanlılık matrisi. Risk: tek kaynağa (Last.fm) bağımlılık ve iznin gelmemesi.

**Discogs API Terms of Use (support.discogs.com, son güncelleme 27 Mayıs 2025, 29 Ekim 2026 okundu):**
- Ticari kullanım "genel olarak izinli" ama Discogs'un takdirine bağlı; ücretli uygulamada, Discogs'un ücretsiz verdiği erişim için ücret almak yazılı izin ister.
- CC0 veri: sürüm başlıkları, parça listeleri, kredi/kimlikler, sanatçı adları ve ilişkili sürümler. Kısıtlı veri: kullanıcı verisi, pazar yeri verisi, görseller (ticari kullanım ve üçüncü tarafa aktarım yasak).
- Stil/tür alanlarının CC0 mü kısıtlı mı olduğu metinde açıkça yazmıyor; doğrulanmadı.
- İçerik gerekli olandan uzun önbelleğe alınamaz ve 6 saatten eski gösterilemez (bu kural CC0 olmayan "Content" için de genel cümleyle yazılmış; CC0 veri dökümleri ayrı konudur ve burada doğrulanmadı).
- Zorunlu atıf: uygulamada "This application uses Discogs' API but is not affiliated with…" bildirimi ve kullanılan verinin yanında "Data provided by Discogs" + discogs.com bağlantısı (nofollow olmadan). Gelecekte ücretlendirme hakkı saklı; erişim her an gerekçesiz kapatılabilir.
- Sonuç: Discogs sanatçı benzerliği vermez; olası rolü sürüm/stil etiketiyle soğuk başlangıç. Önbellek ve atıf kuralları Last.fm'den daha sıkı; çekirdek bağımlılık olmamalı. 
- **Kapsam ölçümü (`spikes/discogs_probe.py`, 100 şarkı):** sonuç dönen %29, stil etiketi %26, tür %29. Eşleşmeler eski/ana akım içerikte (Müslüm Gürses, İbrahim Tatlıses, Neşet Ertaş, Kanye West); güncel niş rap/SoundCloud içeriğinde neredeyse hiç (Murda, Motive, Keskin, Kava, UZI… sıfır). Karar: Discogs niş soğuk başlangıç için işe yaramıyor; v1'de kullanılmaz, atıf ve önbellek yükünü almaya değmez. Gerekirse ana akım/eski katalog için sonradan eklenir.
- Not: örnekte 47. satır boş sanatçı/başlıklı bir kayıt var (muhtemelen yerel dosya veya silinmiş parça); adaptör boş metadata'yı ele almalı.

**Apple (29 Ekim 2026, developer.apple.com):**
- Apple Developer Program ücreti 99 USD / üyelik yılı (bölgeye göre yerel para birimiyle listelenir); kâr amacı gütmeyen/eğitim kurumları için ücret muafiyeti var.
- MusicKit sayfası Android için indirilebilir bir SDK sunuyor (oturum açma + çalma kütüphaneleri); "Beta" etiketi Android'e değil Apple Music Feed'e ait. SDK'nın sürümü/olgunluğu ve bir Flutter bağlayıcısı olup olmadığı doğrulanmadı; Faz 7'de platform kanalı (method channel) gerekebilir.
- Apple Developer Program License Agreement okunmadı.

**Doğrulanamayan:** Spotify'ın Şubat 2026 blog yazısı okunamadı.

## Faz 5 / S4 spike: yayın kaynağı doğrulaması (1 Kasım 2026, gerçek istekler)

Örnek: veritabanındaki ilk 40 MBID'li sanatçı.

- **MusicBrainz `release-group` listeleme (`?artist=MBID`)**: büyük kataloglu sanatçılarda (Jay-Z, Kendrick, Ye) limit 100'de kesilir ve sıralama tarihe göre değildir; "en yeni yayın" bununla güvenilir bulunamaz. Kullanılmaz.
- **MusicBrainz arama ucu + tarih aralığı** (`/release-group?query=arid:MBID AND firstreleasedate:[2026-08-01 TO 2026-11-01] AND (primarytype:album OR ep OR single)`): 40 sanatçının 17'sinde son ~3 ayda yayın döndü (Don Toliver, Drake, Travis Scott, Eminem, Lennsko, EsDeeKid…); tarihler tam gün hassasiyetinde ve gerçekçi. Sanatçı başına tek istek. 1 istek/sn ile 40 sanatçı ≈ 2 dk; ~250 sanatçı ≈ 5 dk (haftalık iş için kabul). Anonim 503'ler görüldü; kaynak istemcisinin geri çekilmesi şart. **Birincil kaynak bu.**
- **ListenBrainz `explore/fresh-releases`** (global, `days=30`): 9897 yayın döndü, bunlardan yalnızca 5'i bizim 40 sanatçıdan (MusicBrainz aramasının yakaladığı 17'nin alt kümesi). Tek istekle tüm sanatçılar için bakılabilir ama kapsamı düşük (yalnızca ListenBrainz'e giren yayınlar). Kullanılmaz; ikincil/yedek olarak ertelenir.
- **Çalışma notları:** işbirliği yayınları ("X feat. Y") ana sanatçı MBID'sine ait görünür; aynı release-group birden çok sanatçıda çıkabilir (VULTURES: Ye ve ¥$) → `release` tablosu release-group MBID'sine göre tekilleştirilir. Eski albümlerin yeniden yayını (Donda, VULTURES 2026-08-28 tarihli) `first-release-date` değerine yansıyabilir; "yeni" sayılırken tür ve tarih penceresi birlikte kullanılır.
- **MBID'siz sanatçılar** (~%26): Last.fm'de yayın tarihi veren uç yok (`artist.getTopAlbums` tarihsiz). Bu sanatçılar için yayın tespiti kapsam dışı; takip listesi yalnızca MBID'li sanatçılarla çalışır.

## Faz 0 tipi doğrulama: ListenBrainz tür omurgası (KESIF_PLANI PR-0, 7 Kasım 2026, gerçek istekler)

Betik: `spikes/lb_genre_probe.py` (salt okunur, token'sız). 20 alt tür × 3 popülerlik bandı × 25 kayıt; her istekte kayıtların ilk 8'i MusicBrainz `recording/{mbid}?inc=isrcs+artist-credits` ile ISRC'ye çevrildi (bant başına 8, toplam 480 örnek).

**Uç davranışı**
- `GET /1/lb-radio/tags` **token'sız çalışır** (anonim). Hız sınırı 30 istek / ~10 sn (`X-RateLimit-*` başlıkları). Yanıt süresi tipik 0,2–1,5 sn, en fazla 3,5 sn. `count=25` istenen kadar kayıt döndü (üst sınır denenmedi).
- Yanıt **yalnızca** `recording_mbid`, `percent`, `source` (ör. `release-group`), `tag_count` taşır; başlık, sanatçı ve popülerlik alanı yok. Başlık/sanatçı/ISRC için MusicBrainz çağrısı şart (plan bunu varsaymıyordu).
- `pop_begin/pop_end` yönü **ters**: 0–33 en çok dinlenenler, 66–100 uzun kuyruk. Doğrulama: `POST /1/popularity/recording` ile bant başına dinlenme medyanı (ör. house 93.764 → 11.654 → 6). Plandaki `known/mid/niche` adları `top/mid/tail` olarak okunmalı.
- `GET /1/popularity/top-recordings-for-artist/{mbid}` **token'sız 401** verir; yanıt biçimi doğrulanamadı (kullanıcı token'ı gerekli).

**MBID → ISRC çözülme (MusicBrainz, örnek 480 kayıt)**

| Grup | top | mid | tail |
| --- | --- | --- | --- |
| Türkçe dışı 15 tür | 110/120 (%92) | 85/120 (%71) | 40/120 (%33) |
| Türkçe 5 tür | 14/40 (%35) | 7/40 (%18) | 8/40 (%20) |
| Tümü | 124/160 (%78) | 92/160 (%58) | 48/160 (%30) |

**Kapı (alt tür başına ≥ 20 ISRC'li kayıt tahmini ve ≥ %60 çözülme, 3 bant birlikte):** 20 türden **8'i geçti** (trap, drill, jazz fusion, house, synthpop, reggae, soul, k-pop), 12'si kaldı. **Beş Türkçe türün hiçbiri geçmedi** (çözülme: arabesk %33, Anadolu rock %21, Türkçe pop %50, Türkçe rap %4, Türk halk %12). Türkçe rap'te üç bandın de dinlenme medyanı 5–6: etiket adı ("turkish hip hop") büyük olasılıkla yanlış ya da çok seyrek.

**Sınırlar (ölçülmedi, yorum katılmadı)**
- Kapı ölçümü 8'erli örnekle yapıldı; `--full` koşulmadı. Küçük örnekte (8) güven aralığı geniş.
- Dönen kayıt sayısı istek başına 25 ile sınırlı tutuldu; daha büyük `count` ile ISRC'li kayıt sayısı artabilir, denenmedi.
- Düşük (tail) bantta etiket tutarlılığı (konu dışı kayıt oranı) **elle örneklenmedi**; kayıtlar `spikes/out/lb_genre_probe.json` içinde (git dışı).
- Türkçe etiket takma adları sınırlı denendi (arabesk/arabesque, anatolian/turkish rock, turkish pop, turkish hip hop/rap, turkish folk).

**Sonuç:** plana göre kapı tutmadı; B planı (MusicBrainz etiket araması + Last.fm `tag.getTopArtists`) geliştiriciye sunulur, PR-4 başlamaz. Uygulama kodu ve veri değişmedi. **Güncelleme (8 Kasım 2026):** genişletilmiş prob bu sonucu değiştirdi, aşağıdaki "Genişletilmiş PR-0 probu" bölümüne bakın (kapı GEÇTİ).

**Ek doğrulama (token ile, 7 Kasım 2026):** `GET /1/popularity/top-recordings-for-artist/{mbid}` token ile 200 döner (3 sanatçıda 0,4–1,0 sn; hız sınırı 30 istek / ~10 sn). Yanıt düz liste; kayıt başına `recording_mbid`, `recording_name`, `artist_mbids`, `artists`, `release_mbid`, `length`, `tags`, `total_listen_count`, `total_user_count` (ISRC yok). Sanatçı başına kayıt sayısı 221–2323 arası. Token'sız 401.

**Çeşitlilik ve etiket tutarlılığı (7 Kasım 2026, 160 kayıtlık örnek; bant başına ilk 8 kayıt)**
- Sanatçı tekrarı yüksek: 3 bantta 24 kayıttaki benzersiz sanatçı sayısı Türkçe rap 2, Anadolu rock 4, Türk halk 4, Türkçe pop 6, arabesk 11, drill 7; Türkçe olmayan türlerin çoğunda 15–23. Ölçüm ISRC sorgulanan ilk 8 kayıttan; `lb-radio` sırasının sanatçıya göre öbeklenip öbeklenmediği ve 25 kaydın tamamı ölçülmedi.
- Kuyruk bandı elle örneklemesi (geliştirici): yalnızca Türkçe rap (8/8 konu dışı, hepsi Grup Ses, çoğu enstrümantal) ve shoegaze (6/8 konu dışı, hepsi The Smashing Pumpkins) işaretlendi; diğer 18 tür için işaretleme bilgisi yok, oran yazılmadı.
- Yorum: tek bir sanatçının kataloğu etiketi alıp kuyruk bandını doldurabiliyor; yanlış etiket ile tekrar aynı kaynaktan geliyor.
- Kapı tanımına eklenecek: alt tür başına ≥ 15 benzersiz sanatçı. Önlem adayları: sanatçı başına üst sınır, `tag_count` eşiği, çok sayıda istekle havuz genişletme.

## Genişletilmiş PR-0 probu: kapı yeniden ölçüldü (KESIF_PLANI PR-0, 8 Kasım 2026, gerçek istekler)

Betik: `spikes/lb_genre_probe2.py` (+ `spikes/test_lb_genre_probe2.py`, 60 çevrimdışı test; git dışı çıktılar `spikes/out/lb_probe2_*`). Yukarıdaki ilk ölçüm (8'erli örnek, MusicBrainz tekli ISRC) Türkçe 5 türde kapıyı geçirmemişti; bu prob daha büyük havuz (count=1000), toplu ISRC çözümü ve sanatçı yolu ile aynı kapıyı yeniden ölçer. Kapı bu probda şöyle okunur: alt tür başına **≥ 20 ISRC'li benzersiz kayıt (C)**, **≥ 15 ISRC'li benzersiz sanatçı (A)** ve **en büyük sanatçı payı ≤ %30**; program kapısı Türkçe 5/5 ve toplam ≥ 16/20. ISRC çözülme oranı artık bilgi amaçlıdır (kapıda değil).

**P0 bulguları (20 istek)**
- `POST /1/metadata/recording/` (token) tek istekte 200 MBID için başlık, sanatçı MBID ve **ISRC** döndürür; MusicBrainz'e göre yaklaşık 40 kat hızlıdır. Önceki varsayım (V5a: ISRC yalnızca MusicBrainz'den gelir) **çürüdü**; ISRC için birincil kaynak ListenBrainz'dir.
- `GET /1/lb-radio/tags` `count=1000` ile çalışır. Küçük havuzlu türlerde (Türkçe rap, Türk halk) üst/orta bant deterministiktir; kuyruk bandı rastgeledir.
- MusicBrainz `recording?query=rid:(...)` toplu aramasıyla ISRC çözümü 49/50 ve 96/100; MusicBrainz sanatçı `browse` ile ISRC verimi düşüktür (4/100), bu yüzden kullanılmadı.
- `GET /1/popularity/top-recordings-for-artist/{mbid}` token ister; `POST /1/popularity/artist` (100/çağrı) ve `/popularity/recording` (500/çağrı) çalışır. LB hız sınırı 30 istek/10 sn; MusicBrainz aralığı 1,1 sn, ara sıra 503 "server busy" (yeniden denemeler bütçeye sayıldı).
- Eski önbellekteki başlıklar bozuktu (U+FFFD); eşleştirme yalnızca taze API adlarıyla yapıldı.

**T1/D/E bulguları (Türkçe 5 tür)**
- T1 (lb-radio count=1000, 3 bant, en çok 3 çekim, kabul edilen takma adlar OR): kayıt başına ISRC oranı yalnızca %4–18. Darboğaz oran değil, **ISRC'li sanatçı çeşitliliği**: T1'de A arabesk 14, Anadolu rock 15, Türkçe pop 13, Türkçe rap 5, Türk halk 1.
- D (sanatçı yolu: `popularity/artist` ile K4 tertili, sanatçı başına en çok dinlenen 30 kayıt, ISRC LB metadata'dan): C ve A'yı büyüttü (ör. Türkçe pop 286/13 → 599/39, Anadolu rock 299/15 → 481/32).
- E (aynı sanatçı + normalize başlık + aynı sürüm işaretçisi): yalnızca kayıt başına oranı artırdı (pop 0,27 → 0,40, Anadolu rock 0,16 → 0,21); benzersiz ISRC sayısı hiçbir türde artmadı (kardeşin ISRC'si zaten havuzdaydı). `sibling_closes` hiçbir türde 0,60'a ulaşmadı.
- Türk halk için ilk D denemesi A=8–9'da kaldı (MusicBrainz etiketli TR sanatçı yalnızca ~20). Çözüm: `lb-radio/tags` **AND** kombinasyonları (turkish+folk, anatolian+folk, turkish+traditional, turkish+saz, turkish+türkü, turkish+alevi) + ülke filtresiz ve sayfalı MusicBrainz etiket araması (saz, halk ozanı, uzun hava, bozlak, zeybek, alevi deyiş…) → 88/9 yerine 357/34.
- Arabesk ilk D'de pay 0,31 ile düşmüştü; seçim üst sınırı 40 → 80 sanatçı ile pay 0,20'ye indi (cap = 5 sürdü).

**20 türlük kapı tablosu** (gate raporu, N = 20, m = 5; `*` = Türkçe dışı türlerde T1 havuzundan seed'li ~1000 kayıt çözüldü, C alt sınırdır)

| Tür | Varyant | C | A | En büyük pay | Kayıt ISRC oranı | D(g) | Karar |
| --- | --- | --- | --- | --- | --- | --- | --- |
| arabesk | T1+D+arabeskx | 316 | 30 | 0,14 | 0,071 | 9 | GEÇTİ (ham) |
| Anadolu rock | T1+D+rockx | 729 | 46 | 0,07 | 0,198 | 8 | GEÇTİ (ham) |
| Türkçe pop | T1+D | 599 | 30 | 0,25 | 0,270 | 9 | GEÇTİ (ham) |
| Türkçe rap | T1+D+rapx | 651 | 66 | 0,06 | 0,439 | 4 | GEÇTİ (ham) |
| Türk halk | T1+D+halkx | 206 | 26 | 0,14 | 0,116 | 8 | GEÇTİ (ham; dil düzeltmeli C=189, A=25) |
| trap* | T1 | 509 | 232 | 0,09 | 0,489 | 25 | GEÇTİ |
| drill* | T1 | 510 | 132 | 0,16 | 0,514 | 25 | GEÇTİ |
| boom bap* | T1 | 543 | 308 | 0,05 | 0,540 | 27 | GEÇTİ |
| shoegaze* | T1 | 363 | 134 | 0,07 | 0,360 | 18 | GEÇTİ |
| jazz fusion* | T1 | 446 | 143 | 0,09 | 0,462 | 22 | GEÇTİ |
| house* | T1 | 794 | 450 | 0,06 | 0,683 | 39 | GEÇTİ |
| techno* | T1 | 536 | 290 | 0,07 | 0,489 | 26 | GEÇTİ |
| synthpop* | T1 | 786 | 426 | 0,06 | 0,701 | 39 | GEÇTİ |
| black metal* | T1 | 436 | 161 | 0,05 | 0,437 | 21 | GEÇTİ |
| bossa nova* | T1 | 391 | 161 | 0,08 | 0,389 | 19 | GEÇTİ |
| reggae* | T1 | 557 | 317 | 0,06 | 0,539 | 27 | GEÇTİ |
| punk rock* | T1 | 569 | 198 | 0,05 | 0,562 | 28 | GEÇTİ |
| soul* | T1 | 702 | 415 | 0,03 | 0,664 | 35 | GEÇTİ |
| country* | T1 | 651 | 278 | 0,07 | 0,660 | 32 | GEÇTİ |
| k-pop* | T1 | 665 | 165 | 0,09 | 0,688 | 33 | GEÇTİ |

**Not:** Türkçe 5 satır, işaretleme ve dışlama turlarından sonraki son ham değerlerdir; ilk turdaki değerler (ör. halk 357/34, rap 80/19) örnek içi sızıntı ve konu dışı kayıtlarla şişkindi. Türkçe dışı 15 tür değişmedi.

**Program kapısı: GEÇTİ** (ham: Türkçe 5/5, Türkçe dışı 15/15, toplam 20/20). A_düz (aşağıda) ile de nokta ve alt uçta Türkçe 5/5, toplam 20/20. Türkçe dışı türlerde D, T1 açıkça geçtiği için (C ≥ 40 ve A ≥ 25) atlandı (E2). Strateji sırası (K3): T1+D > D > T1; Türkçe için sanatçı yolu (D) şart, Türkçe dışı için T1 yeterli.

**Kapı yolculuğu (Türkçe 5 tür).** Ham kapı ilk turda geçti, ama geliştirici elle işaretleyince havuzların bir kısmının konu dışı ya da yabancı olduğu görüldü. Bu yüzden kapı, işaretlenmiş uygun orana göre düzeltilmiş sayı (A_düz) ile yeniden okundu. Kapı gevşetilmedi: eşikler (C ≥ 20, A ≥ 15, pay ≤ 0,30) aynı kaldı, yalnızca A düzeltildi ve alt uç ayrıca sınandı. Ara turlarda rock ve arabesk alt uçta kalmıştı; havuz genişletmesinden sonra geçti.

**İşaretleme turları** (geliştirici `[x]` = uygun değil işaretledi; örnek dosyaları git dışı `spikes/out/lb_sample_*`)
- Halk: v1, v2. Kayıt düzeyi uygun oranı 24/40 = 0,60; ardından Türkçe izin listesi ile dil düzeltmesi.
- Rap: v1, v2. Sanatçı uygun oranı 0,56 (A = 66).
- Arabesk: v1 (oran 0,60, A_düz 15,6 [10,6–19,9]) -> yabancı/uygunsuz sanatçı dışlaması -> v3 (A = 18) -> arabeskx havuz genişletmesi -> v4 (A = 31 -> 30).
- Rock: v1 (A_düz 17,0 [12,1–20,7]) -> v2 (A = 15; 13,0 [9,3–14,4]) -> rockx genişletmesi -> v3 (A = 46; işaret öncesi havuz 54).
- Pop: yalnızca v1 (tek ve eski örnek).

**Son A_düz tablosu** (A_düz = sanatçı düzeyi uygun oranı x ISRC'li sanatçı havuzu; oran için Wilson %95; köşeli parantez = alt–üst uç)

| Tür | Havuz (A) | Sanatçı uygun oranı | A_düz [95% aralık] | Kapı (A ≥ 15) |
| --- | --- | --- | --- | --- |
| Türk halk | 26 | 0,84 | 21,8 [17,0–24,3] | geçti (nokta ve alt uç) |
| Türkçe rap | 66 | 0,56 | 37,0 [24,5–48,4] | geçti |
| arabesk | 39 (ön havuz) | 28/29 = 0,97 (v3+v4) | 37,7 [32,3–38,8] | geçti |
| Anadolu rock | 54 (ön havuz) | 34/40 = 0,85 (v2+v3) | 45,9 [38,3–50,2] | geçti |
| Türkçe pop | 30 | 0,84 | 25,2 [19,6–28,1] | geçti |

Halk dil düzeltmeli: C = 189, A = 25, en büyük pay 0,148; dil uyuşmazlığı 0,0825 (206 kayıttan 15 Kürtçe + 2 Slovence). Daha sıkı alternatif okumalar: arabesk yalnız v4 ile 28,2 [19,3–30,5]; rock yalnız v3 ile 38,6 [30,1–43,1]. Kayıt düzeyi uygun oranlar: halk 0,60, arabesk 39/40, rock 35/40, pop 19/25.

**Yöntem notları**
- A_düz = sanatçı oranı x havuz; oran kayıt değil sanatçı düzeyinde alınır (bir sanatçının [x] sayısı uygun sayısından büyükse "uygunsuz"; eşitlikte tutulur).
- Ülke dışlaması: MusicBrainz ülkesi dolu ve TR değilse sanatçı havuzdan çıkarılır; ayrıca işaret çoğunluğu dışlaması uygulanır. Halkta ek olarak tür dışı etiketler (derlenmiş sanatçılar muaf). Rock ve arabeskte A_düz tabanı işaret çoğunluğu dışlamasından önceki havuzdur (A_pre); temiz havuz daha küçüktür (arabesk 30, rock 46).
- Feat. credit düzeltmesi: ortak sanatçı kredisi tek sanatçıya yazılmaz; havuz ve pay buna göre sayılır.
- Kayıt dili: MusicBrainz recording kaydında dil alanı **yoktur**; dil, ilk 3 sürümün `text-representation.language` değerinden çıkarılır ('tur' varsa Türkçe, yoksa en sık tanımlı dil; mul/zxx/und/boş nötr). Sınıflar: tur / yabancı / izin / belirsiz; izin listesi halk v1/v2 işaretlerinden gelir.
- Ölçüt tek ve geneldir: **"Türkçe şarkı"**, tüm Türkçe türlerde aynı. Etnik ya da dile özel kara liste yoktur; halktaki dil düzeltmesi bu genel ölçütün sonucudur.
- Havuz genişletme (`rockx`, `arabeskx`): MusicBrainz etiket araması (country:TR) + lb-radio AND çiftleri + popularity -> sanatçı seçimi -> top-recordings -> LB metadata ISRC; hata/429'da durur.

**Tekrarlanabilirlik (tohum 2, kısmi).** İkinci tohumla (`--out-dir spikes/out/seed2`; radio/tags verisi kopyalandı, yeniden çekilmedi) kapı kararı değişmedi. Ortak sanatçı kümelerinde Jaccard: halk 1,00 (aday sayısı sınırın altında kaldığı için bilgisiz), rap 0,92, rock 0,84, arabesk 0,54. Tam bağımsız tekrar değildir. Seed2 A_düz'de halk alt ucu 13,6 çıktı (kayıt işaretlerinden türetilen farklı etiket tanımıyla); 15'in altında olduğu için risk olarak tutulur.

**Veri sınırı.** Büyük arabesk isimleri (Orhan Gencebay, Şevval Sam, Gülben Ergen, Cengiz Kurtoğlu, Kibariye) hem LB'de hem MusicBrainz'de ISRC'siz; `isrcfill` (MB rid ile doldurma) az fayda sağladı. Çözüm PR-4b'de (Deezer ISRC doldurma).

**Harcanan istek (loglu):** toplam yaklaşık **1340** (ListenBrainz ≈ 890, MusicBrainz ≈ 450): ana koşu 776 LB + 436 MB = 1212; tohum 2 kendi 128 (LB 114, MB 14); Deezer 0, Last.fm 0; loglanmamış elle sorgu ≈ 6.

**Riskler ve sınırlar**
- Tek tohum + kısmi tekrar; radio/tags ikinci kez çekilmedi. Türkçe dışı türlerde C, örnekten gelen alt sınırdır (havuz 5000+, çözülen ~1000).
- Seed2'de halk A_düz alt ucu 13,6 (< 15); arabesk Jaccard 0,54 (küçük, tohuma duyarlı havuz); halk Jaccard 1,00 tavan nedeniyle bilgisiz.
- Rock ve arabesk A_düz tabanı işaret öncesi havuz; temiz havuzlar daha küçük (46 / 30), yine de ≥ 15.
- Pop yalnızca tek ve eski örnekle işaretlendi. Rap sanatçı uygun oranı 0,56.
- Büyük arabesk sanatçıları ISRC'siz (PR-4b); arabeskte kayıt ISRC oranı 0,071.
- A_niş (K4) Türkçe dışı türlerde hesaplanmadı (D atlandı).
- MusicBrainz kullanıcı etiketleri (user tag) CC BY-NC-SA: yalnızca spike'ta kullanıldı, ticari omurgada uygun değil (PR-4'te yeniden değerlendirilmeli).
- Last.fm ticari izni ve Deezer lisansı bu probda kullanılmadı; borç olarak duruyor.
- Betik riski: `request_totals`, `spikes/out` altındaki liste tipli `lb_probe2_repro_*.json` dosyalarında çökebilir (gate yeniden üretilirse); kod bu görevde değiştirilmedi.
