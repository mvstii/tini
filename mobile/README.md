# mobile

Flutter uygulaması (iOS + Android). Faz 1 iskeleti: giriş/kayıt, Spotify bağlama, kütüphane aktarma, boş oylama ekranı.

## Çalıştırma (Android emülatörü)

Spotify yönlendirme adresi `127.0.0.1:8000` olduğundan, emülatörün tarayıcısının backend'e ulaşması için port yönlendirilir:

```bash
adb reverse tcp:8000 tcp:8000
flutter run
```

Uygulama API'ye varsayılan olarak `http://10.0.2.2:8000` ile bağlanır. Gerçek cihazda `--dart-define=API_BASE=http://<lan-ip>:8000` verilir. Düz http yalnızca geliştirme içindir (Android `usesCleartextTraffic`); yayından önce HTTPS'e geçilip kaldırılır.

Test: `flutter analyze && flutter test`.

Planlanan ekranlar:

- Giriş ve servis bağlama
- Başlangıç oylama turu
- Oylama kuyruğu (kaydırmalı kartlar, 6 oy + Daha Dinlemedim)
- Keşif listesi (gerekçe ve slot tipiyle)
- Haftalık Taze listesi ve "Yeni" akışı
- Oy geçmişi ve oy değiştirme
