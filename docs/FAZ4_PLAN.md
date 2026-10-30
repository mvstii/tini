# Faz 4 Planı — Mobil deneyim ve çıktı

Taslak: 30 Ekim 2026 · Durum: **onaylandı** (30 Ekim 2026; Premium sorusu açık) · Süre: 21 Aralık–3 Ocak (erken başlanabilir; Faz 3 kapısı geçildi)

Kapı: telefonda oylayıp gerekçeli listeyi Spotify'a kaydedebiliyorsun.

## Mevcut zemin

- Backend hazır: `POST /votes`, `GET /votes/current`, `POST /profile/rebuild`, `POST /lists/generate`, `GET /lists/{id}`, kütüphane içe aktarma, Spotify OAuth.
- Mobil (Flutter): giriş, ana ekran (Spotify bağla, kütüphaneyi aktar), `api.dart` istemcisi. `rating_screen.dart` boş yer tutucu.
- Eksik: oylanacak parça kuyruğu (başlık/sanatçı ile), liste çıktısında okunur ad ve parça başlığı, Spotify'a yazma, oy geçmişi.

## Doğrulananlar (Spotify, 30 Ekim 2026; kaynak: resmi Şubat 2026 geçiş rehberi)

- Development Mode: uygulama sahibinin **Premium** üyeliği şart (biterse uygulama durur), yeni uygulamada 5 kullanıcı. Kapsam kısıtı listelenmemiş.
- Playlist yazma: `POST /me/playlists` (eski `/users/{id}/playlists` kalktı), `POST /playlists/{id}/items` (eski `/tracks` adı kalktı). Yazma için sayısal sınır yok. Playlist okuma yalnızca kullanıcının sahibi olduğu listelerde.
- Arama: `limit` en çok 10 (varsayılan 5). Toplu `GET /tracks` vb. kalktı; tek tek `GET /tracks/{id}` var.
- Player uç noktaları (çal/duraklat/sıra) kaldırılanlar listesinde yok; kısıt belirtilmemiş.
- **Doğrulanmadı:** App Remote SDK'nın Development Mode'da çalışması (rehber SDK'dan söz etmiyor). Flutter paketi `spotify_sdk` var ama bakım durumu kesin değil; Spotify uygulaması telefonda kurulu ve girişli olmalı, belirli bir parçayı istek üzerine çalmak Premium ister. Bu yüzden S4'te önce kanıt (spike), sonra karar.

## Önerilen aşamalar (her biri ayrı PR, her aşama sonrası DURUM.md ve telefon bildirimi)

| # | Aşama | İçerik |
|---|---|---|
| S1 | Backend: kuyruk ve zengin çıktı | `GET /votes/queue` (kütüphaneden oylanmamış parçalar; başlık, sanatçı kullanıcıya özel TTL önbellekten, süresi dolmuşsa Spotify'dan yenilenir; sıra: oy almamış sanatçılar ve grafikte olanlar önde, sabit tohum), `GET /votes/history` (oylar + son olay), `GET /lists/{id}` yanıtına sanatçı adı ve (varsa) parça başlığı. Göç yok (mevcut tablolar yeter). |
| S2 | Mobil: oylama kartları | Kaydırmalı kart ekranı: 6 oy + Unheard (sola/sağa kaydır + düğmeler), geri al (yeni olay), başlangıç turu (ilk 30 oy, ilerleme çubuğu, sonunda profili kur). `api.dart` genişler. Widget testleri. |
| S3 | Mobil: keşif listesi | "Liste üret" → sanatçı kartları, her kartta gerekçe ("Drake ve Future'ı sevdiğin için", çapa işareti), slot tipi etiketi (Faz 4'te tek tip: "keşif"). Gerekçe itirazı: karttan "bu gerekçe yanlış" → `POST /lists/{id}/items/{pos}/feedback` (basit olay kaydı; algoritma etkisi Faz 5). Göç 0009 `list_feedback`. |
| S4 | Dinleme ve "servisinde aç" | Önce spike: `spotify:` URI ile `url_launcher` (SDK'sız, her durumda çalışır). App Remote yalnızca spike Development Mode'da ve Premium ile çalışırsa eklenir; çalışmazsa uygulama içi dinleme Faz 5+'a ertelenir. ISRC→Spotify URI çözümü: kullanıcıya özel eşleme (`isrc:` araması, sonuç kullanıcıya özel önbellek; Spotify kimliği paylaşılan katalogda tutulmaz). |
| S5 | Spotify'a yazma + geçmiş | `POST /lists/{id}/export/spotify`: `POST /me/playlists` + `POST /playlists/{id}/items` (kapsam: `playlist-modify-private`, yoksa yeniden yetkilendirme). Çözülemeyen parçalar atlanır ve raporlanır. Mobilde oy geçmişi ve oy değiştirme ekranı. |

Her aşamada birim/entegrasyon testi; mobilde `flutter analyze` + `flutter test` CI'da yeşil. Parametreler (kuyruk boyutu, tur uzunluğu, TTL) yapılandırmadan gelir.

## Karar bekleyen noktalar

1. **Uygulama içi dinleme.** Öneri: S4'te önce `url_launcher` ("Spotify'da aç"), App Remote'u spike sonucuna göre ekle. Alternatif: App Remote'u baştan hedefle (daha riskli, ek yerel kurulum).
2. **Gerekçe itirazı kapsamı.** Öneri: yalnızca geri bildirim kaydı (S3), profile/algoritmaya etkisi Faz 5'te. Alternatif: itiraz edilen çapayı o liste için anında sönümle (algoritma değişikliği, ayrı plan gerektirir).
3. **Slot tipi.** Faz 5'te Thompson sampling gelene kadar tek tip ("keşif"). Onay?
4. **Premium.** Development Mode, uygulama sahibinin Premium'ını ister. Senin hesabın Premium mı? (S4/S5 canlı testi bunu gerektirir.)
5. **Başlangıç turu uzunluğu.** Öneri: 30 oy (ROADMAP'teki persentil eşiğiyle aynı). Onay?
6. **Yeni bağımlılık (mobil):** kaydırma için `flutter_card_swiper` ya da kendi `Dismissible`/`Draggable` çözümü. Öneri: bağımlılık eklemeden `Dismissible` + düğmeler.

## Riskler

- App Remote Development Mode'da çalışmayabilir veya iOS'ta kararsız olabilir (paket dokümanı iOS token saklamanın hatalı olduğunu söylüyor); yedek yol deep link.
- ISRC→URI aramasında `limit` 10 ve hız sınırı: parça başına bir arama, 429 geri çekilme adaptörde (mevcut kural). 20 parçalık liste için ~20 çağrı; önbellekle tek seferlik.
- Playlist yazma 403 raporları (kullanıcı bildirimleri, resmî değil): kapsam ve liste sahipliği S5'te gerçek hesapla doğrulanır.
- Oy kuyruğu sanatçısız (çözülmemiş) parçaları nasıl ele alır: v1'de yalnızca sanatçısı çözülmüş parçalar sorulur (CSV aracıyla aynı kural).
