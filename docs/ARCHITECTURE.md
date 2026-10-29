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

**Doğrulanamayan:** Spotify'ın Şubat 2026 blog yazısı ve Deezer koşulları/rate limit sayfaları okunamadı.
