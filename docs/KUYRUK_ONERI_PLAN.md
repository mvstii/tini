# Oylama kuyruğunu öneri motoruyla doldurma — plan

Durum: onay bekliyor. İstemci (APK) değişmez; yalnızca backend.

## Sorun
`/votes/queue` yalnızca kullanıcının içe aktarılmış kütüphanesini (`UserTrackLink`) sunar. Kütüphane bitince kuyruk boş kalır ve yeni şarkı gelmez.

## Çözüm
`GET /votes/queue` boşalmaya yaklaşınca (`kalan < queue_suggest_threshold`) öneri motorundan parça ekler. Şema değişikliği yok.

1. **Kaynak:** kullanıcının son `main` listesi (yoksa üretilir; tüm öğeleri oylanmışsa yeniden üretilir, profil oylarla değiştiği için içerik değişir). `track_id` dolu, oylanmamış öğeler adaydır.
2. **Başlık/kapak:** `adapter.find_card(isrc, sanatçı)` ile çözülür (`/recommend/daily` ile aynı yol). Sonuç `UserTrackMeta`'ya TTL'li yazılır (kullanıcıya özel, mevcut tablo; Spotify verisi kalıcı saklanmaz kuralına uyar). `UserTrackLink` yazılmaz, yani kütüphane stale sayacına karışmaz.
3. **Gerekçe:** öğenin `reasons` alanı kuyruk öğesine eklenir (değişmez karar 7). Eski istemci bilinmeyen alanı yok sayar.
4. **Sıralama:** öneri öğeleri liste sırasıyla; kütüphane öğeleri varsa onlar önce.
5. **Sınır:** istek başına en çok `queue_suggest_batch` (10) `find_card` çağrısı; 429/hata olursa o öğe atlanır, kuyruk yine döner. Servis bağlı değilse öneri eklenmez.
6. **Yapılandırma:** `ProfileSettings`: `queue_suggest_threshold`, `queue_suggest_batch`; `queue_algo_version` `queue-6`.
7. **Test:** boş kuyrukta öneri gelir; oylanmış parça gelmez; servis yokken kuyruk bozulmaz; `find_card` kısmi başarısızlığı; gerekçe alanı; stale sayacı değişmez.

## Sürekli akış (revizyon, geliştirici isteği: her oylamadan sonra yeni öneri)
Sabit, kısa bir liste yetmez; istemci kartlar azalınca `/votes/queue`'yu zaten tekrar çağırır, akış bu çağrıda yenilenir:
- Son profilden sonra `queue_rebuild_after_votes` (5) yeni oy gelmişse profil otomatik yeniden kurulur ("Profili Güncelle" düğmesi artık zorunlu değil).
- Son listenin profil sürümü güncel profilden eskiyse ya da listede oylanmamış aday kalmadıysa liste yeniden üretilir.
- Yeni oy sonuçları öneri motoruna böylece her turda yansır; oylanan sanatçılar adaydan düşer.
- Öneri ekleme eşiği `queue_suggest_threshold` (20): kütüphane kalanı bunun altına inince öneriler karışır.
- Skip (sola kaydırma) öneri parçalarında da çalışır (`/votes/unheard` liste öğelerini de kabul eder).

## Riskler
- Öneri listesi `track_id` taşımayan öğeler (katalogda parçası olmayan sanatçı) atlanır; liste kısa kalabilir.
- Spotify kapalı test modunda; Deezer/Apple adaptörü `find_card` uygularsa aynı kod çalışır.
- Kuyruk isteği, `find_card` çağrıları yüzünden ilk seferde yavaşlar (≤10 çağrı); sonraki istekler önbellekten.
- Öneri motoru yalnızca profil ve grafik varsa çalışır (`NoProfile`/`NoGraph` → öneri eklenmez).
