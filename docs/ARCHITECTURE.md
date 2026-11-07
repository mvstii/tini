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

**Sonuç:** plana göre kapı tutmadı; B planı (MusicBrainz etiket araması + Last.fm `tag.getTopArtists`) geliştiriciye sunulur, PR-4 başlamaz. Uygulama kodu ve veri değişmedi.

**Ek doğrulama (token ile, 7 Kasım 2026):** `GET /1/popularity/top-recordings-for-artist/{mbid}` token ile 200 döner (3 sanatçıda 0,4–1,0 sn; hız sınırı 30 istek / ~10 sn). Yanıt düz liste; kayıt başına `recording_mbid`, `recording_name`, `artist_mbids`, `artists`, `release_mbid`, `length`, `tags`, `total_listen_count`, `total_user_count` (ISRC yok). Sanatçı başına kayıt sayısı 221–2323 arası. Token'sız 401.

**Çeşitlilik ve etiket tutarlılığı (7 Kasım 2026, 160 kayıtlık örnek; bant başına ilk 8 kayıt)**
- Sanatçı tekrarı yüksek: 3 bantta 24 kayıttaki benzersiz sanatçı sayısı Türkçe rap 2, Anadolu rock 4, Türk halk 4, Türkçe pop 6, arabesk 11, drill 7; Türkçe olmayan türlerin çoğunda 15–23. Ölçüm ISRC sorgulanan ilk 8 kayıttan; `lb-radio` sırasının sanatçıya göre öbeklenip öbeklenmediği ve 25 kaydın tamamı ölçülmedi.
- Kuyruk bandı elle örneklemesi (geliştirici): yalnızca Türkçe rap (8/8 konu dışı, hepsi Grup Ses, çoğu enstrümantal) ve shoegaze (6/8 konu dışı, hepsi The Smashing Pumpkins) işaretlendi; diğer 18 tür için işaretleme bilgisi yok, oran yazılmadı.
- Yorum: tek bir sanatçının kataloğu etiketi alıp kuyruk bandını doldurabiliyor; yanlış etiket ile tekrar aynı kaynaktan geliyor.
- Kapı tanımına eklenecek: alt tür başına ≥ 15 benzersiz sanatçı. Önlem adayları: sanatçı başına üst sınır, `tag_count` eşiği, çok sayıda istekle havuz genişletme.
