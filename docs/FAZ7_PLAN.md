# Faz 7 Planı — Kullanılabilir son hâl (taslak, onay bekliyor)

Kapsam kararı (2 Kasım 2026, geliştirici): mağaza yayını en sona; önce uygulama kullanılabilir son hâline getirilir. Ücretli hiçbir şey yayın öncesine kadar yapılmaz.

## Sıra

| # | Aşama | Çıktı | Şema/bağımlılık |
|---|---|---|---|
| S1 | Genel UI/UX incelemesi | Ekran ekran düzeltme (ana, oylama, liste, geçmiş, Yeni, geri bildirim, giriş); boş/hata/yükleme durumları; ortak tema ve bileşenler | Yok |
| S2 | Uygulama içi hesap silme | `DELETE /account` (parola onaylı), kişisel verinin tamamını siler (`delete_user` ile aynı yol), mobilde onaylı buton | Yok |
| S3 | Bağlantısız mod | Servis bağlı olmadan öneri görme; platformlar arası şarkı bağlantıları (arama bağlantısı) | Yok (adaptör arayüzü korunur) |
| S4 | Oy ayarı | `evaluate` yeterli oyla yeniden çalışır; parametre değişirse test + `algo_version` artışı | Yok |
| S5 | Apple Music adaptörü, Apple/Google girişi | Yayın hazırlığıyla birlikte, ücretli üyelik gerektirir; sona kalır | Yeni bağımlılık, onay gerekir |

## S1 çalışma şekli

1. Geliştirici telefondaki sorunları ve ekran görüntülerini gönderir.
2. Kod tarafında ekranlar taranır (tutarsız boşluk, yazı boyutu, kontrast, koyu tema, küçük ekran).
3. Düzeltmeler ekran grubu başına küçük PR'lar hâlinde; her PR'da Flutter testi ve analyze.
4. Kapı: geliştirici telefonda uygulamayı baştan sona rahatça kullanabiliyor.

## Kapsam dışı

Mağaza görselleri, gizlilik politikası/KVKK metni, TestFlight ve Play yayını, Last.fm ticari izni (yayın öncesi hatırlatılır).
