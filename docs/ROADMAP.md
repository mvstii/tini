# Tını — Yol Haritası

Başlangıç: 2 Kasım 2026 · MVP (kapalı test): 24 Ocak 2027 · Mağaza beta: 21 Şubat 2027

Her fazın sonunda bir kapı vardır; kapıdan geçilmeden sonraki faza başlanmaz. Güncel takip Claude Docs'taki plan dokümanındaki görev kutularıyla yapılır; bu dosya depo içi kopyadır.

## Faz 0 — Fizibilite (Hafta 1: 2–8 Kasım)

Kapı: dış kaynakların gerçekten veri verdiği 100 şarkılık örnekle kanıtlanır.

- [x] Spotify Development Mode uygulamasını aç; kütüphane, top items, recently-played, arama, ISRC ve playlist yazma uç noktalarını tek tek doğrula
- [x] Last.fm, ListenBrainz ve MusicBrainz için 100 şarkılık örnekte benzerlik ve etiket kapsamını ölç (sonuçlar `docs/ARCHITECTURE.md`'de)
- [ ] Deezer listeler/yeni çıkanlar ve Apple MusicKit (iOS + Android) durumunu doğrula
- [x] Spotify, Last.fm ve Apple kullanım koşullarını oku (Apple lisans sözleşmesi ve Android SDK incelemesi geliştirici kararıyla Faz 7'ye ertelendi, bkz. Faz 7), kısıtları not et (Spotify, Last.fm ve Deezer okundu, Apple ücreti 99 USD/yıl olarak doğrulandı; Apple lisans sözleşmesi ve Android SDK olgunluğu okunmadı; bulgular `docs/ARCHITECTURE.md`'de)
- [ ] Last.fm'e (partners@last.fm) ticari kullanım ve kota için izin başvurusu gönder
- [x] Kapsam ölçümünü yaygın ve niş şarkı katmanlarında çalıştır (`spikes/coverage_probe.py`, niş için `sample_niche.json`); Last.fm olmadan kapsamı karşılaştır
- [x] Discogs API koşullarını oku ve stil etiketi kapsamını ölç (stil kapsamı %26, niş içerikte ~0; v1'de kullanılmayacak)
- [x] Kapı: örnek şarkıların en az %80'i için benzerlik verisi ve ISRC eşlemesi var mı? (Sanatçı düzeyinde evet: ISRC %98, Last.fm sanatçı benzerliği %96; şarkı düzeyinde hayır. Hibrit model kararı ve koşullar `docs/ARCHITECTURE.md`'de. Last.fm izni gelmeden üretim bağımlılığı sayılmaz.)

## Faz 1 — Temel altyapı (Hafta 2–3: 9–22 Kasım)

Kapı: kullanıcı hesap açıp Spotify'ı bağlayabilir ve kütüphanesi veritabanına iner.

- [ ] Docker Compose, PostgreSQL + pgvector, CI
- [ ] İlk veri modeli göçleri (kullanıcı, servis bağlantısı, parça, sanatçı, kimlik eşleme, oy olayı)
- [ ] Hesap sistemi ve Spotify OAuth (PKCE), şifreli token saklama
- [ ] Servis adaptörü arayüzü ve Spotify adaptörü (kütüphane okuma)
- [ ] Flutter iskeleti: giriş, servis bağlama, boş oylama ekranı

## Faz 2 — Katalog ve benzerlik grafiği (Hafta 4–5: 23 Kasım–6 Aralık)

Kapı: bir çapa şarkıdan 2 adımlık komşuluk önbellekten saniyeler içinde gelir.

- [ ] Zenginleştirme hattı: Spotify ID → ISRC → MBID → Last.fm
- [ ] Grafik kenarları ve etiketler; geçerlilik süreli paylaşılan önbellek
- [ ] Tembel genişleme işi (çapalardan 2–3 adım)
- [ ] Servise eşleme hunisi ve güven skoru
- [ ] Kota yönetimi: toplu istek, 429 geri çekilme, önbellek isabet metriği

## Faz 3 — Profil ve öneri motoru v1 (Hafta 6–7: 7–20 Aralık)

Kapı: kendi oylarınla üretilen listede gerekçeler mantıklı görünüyor.

- [ ] Oy olay kaydı, güncel oy görünümü, normalizasyon, zaman sönümü
- [ ] Çok modlu profil: kümeler, çapalar, kaçınma bölgesi
- [ ] PPR aday skoru, Awful budama, Bad cezası, yenilik bonusu
- [ ] Çapa katkısından gerekçe üretimi
- [ ] MMR çeşitlilik ve sanatçı üst sınırı
- [ ] Algoritma birim testleri ve sentetik veri seti

## Faz 4 — Mobil deneyim ve çıktı (Hafta 8–9: 21 Aralık–3 Ocak)

Kapı: telefonda oylayıp gerekçeli listeyi Spotify'a kaydedebiliyorsun.

- [ ] Kaydırmalı oylama kartları (6 oy + Unheard), başlangıç turu
- [ ] Spotify App Remote ile uygulama içi dinleme ve "servisinde aç"
- [ ] Keşif listesi ekranı: gerekçe, slot tipi, gerekçe itirazı
- [ ] Listeyi Spotify'a yazma; oy geçmişi ve oy değiştirme

## Faz 5 — Keşif döngüsü ve yeni çıkanlar (Hafta 10–11: 4–17 Ocak)

Kapı: Unheard döngüsü uçtan uca çalışıyor, ilk haftalık Taze listesi üretildi.

- [ ] Unheard durum makinesi ve aktif öğrenme kuyruğu
- [ ] Thompson sampling ile slot dağılımı
- [ ] Takip listesi, yayın tespiti, haftalık Taze listesi, ana listede %10–15 pay
- [ ] Uygulama içi "Yeni" akışı
- [ ] Değerlendirme betikleri

## Faz 6 — Kapalı test (Hafta 12: 18–24 Ocak)

Kapı: 5 test kullanıcısının her biri en az 100 oy verdi ve kritik hata yok.

- [ ] 4 arkadaşı Spotify test kullanıcısı olarak ekle
- [ ] Geri bildirim topla, ölçütleri hesapla, parametreleri ayarla
- [ ] MVP sürümünü etiketle

## Faz 7 — Yayın hazırlığı (Hafta 13–16: 25 Ocak–21 Şubat)

Kapı: TestFlight ve Play kapalı test kanalında, Spotify'sız kullanıcı uygulamayı uçtan uca kullanabiliyor.

- [ ] Faz 6 sonunda (en geç 18 Ocak): Apple Developer Program üyeliği (99 USD/yıl; onay süresi doğrulanmadı), Apple lisans sözleşmesini oku, MusicKit Android SDK sürümü ve Flutter bağlayıcısı var mı kontrol et; sonuç kötüyse Apple Music adaptörü için platform kanalı veya kapsam kararı ver
- [ ] Apple Music adaptörü (adaptör arayüzü Faz 1'de servis bağımsız yazılmış olmalı)
- [ ] Bağlantısız mod: platformlar arası şarkı bağlantıları
- [ ] Apple ile giriş, Google ile giriş, hesap ve veri silme
- [ ] Gizlilik politikası, KVKK metni, mağaza görselleri
- [ ] TestFlight ve Google Play kapalı test yayını

## Başarı ölçütleri (v1 hedefleri)

| Ölçüt | Hedef |
|---|---|
| Önerilen şarkıların Good+ alma oranı | ≥ %50 |
| Unheard şarkıların sonradan Good+ alma oranı | ≥ %40 |
| Tahmin hatası (ortalama mutlak fark) | ≤ 1.2 kademe |
| Gerekçe itiraz oranı | ≤ %15 |
| Eşleme doğruluğu | ≥ %97 |
| Önbellek isabeti (4. haftadan sonra) | ≥ %70 |
