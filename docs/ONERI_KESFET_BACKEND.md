# Öneri: Keşfet için backend değişikliği (onay bekliyor)

Amaç: Keşfet'te günün şarkısına hızlı oy (1–6) ve "Oylama kuyruğuna ekle". Şu an yapılamıyor çünkü:

- `GET /recommend/daily` yanıtında parça kimliği yok (`ListItem.track_id` var ama dönmüyor).
- `POST /votes` yalnızca kullanıcının kütüphanesindeki parçaya oy kabul ediyor (`UserTrackLink` yoksa 404 "Parça kütüphanede yok"). Öneriler kütüphane dışından geldiği için günün şarkısına oy verilemez.
- `GET /votes/queue` kütüphane eksi oylananlardan türetiliyor; "kuyruğa ekle" için yazılacak bir yer yok.

## Değişiklik 1: günün şarkısına `track` (küçük, şemasız)

`/recommend/daily` yanıtına `"track": item.track_id` eklenir. Geriye uyumlu; istemci alanı yoksa düğmeleri gizler. Birim testi: yanıtta kimlik var.

## Değişiklik 2: kütüphane dışı parçaya oy (asıl karar)

İki seçenek:

| | A: Oy kuralını gevşet | B: Oyla ve kütüphaneye bağla |
|---|---|---|
| Ne yapar | `POST /votes` parça, kullanıcının **oluşturulmuş listelerinde** varsa da kabul eder | Öneri parçasına oy gelince `UserTrackLink` satırı da yazılır |
| Şema | Yok | Yok (kaynak alanı `recommended` eklenirse küçük göç) |
| Risk | Oy ile kütüphane ayrışır; "Dinlemedim" ve kuyruk mantığı etkilenmez | Kütüphane içe aktarımı ile karışır; hesap silinince temizlik aynı kalır |
| Karar 7 / 1 | Uyumlu (olay kaydı silinmez) | Uyumlu |

Öneri: **A**. Oylar zaten silinmeyen olay kaydı; kütüphane kavramına dokunmaz. Doğrulama: parça kullanıcının `GeneratedList` öğelerinde olmalı (başkasının listesindeki parçaya oy verilemesin).

## Değişiklik 3: "Kuyruğa ekle" (şema değişikliği, onay gerekir)

Yeni kişisel tablo `queue_pin(user_id, track_id, created_at)` (hesap silinince tamamen silinir) + `POST /votes/queue/pin` ve `GET /votes/queue` başına sabitlenenleri koyma. Sabitlenen parça oylanınca kuyruktan düşer. Spotify metadata'sı saklanmaz; başlık yine TTL'li kullanıcı önbelleğinden gelir, önbellek yoksa istemci "başlık yok" gösterir.

Alternatif (şemasız): kuyruğa ekleme yerine yalnızca hızlı oy. Önerim önce 1 ve 2'yi yapmak, 3'ü ayrı karar olarak bırakmak.

## Testler ve sıra

1. `track` alanı + test. 2. Oy kuralı (A) + test: listede olan parça kabul, olmayan 404. 3. İstemci: Keşfet kahraman kartına 1–6 oy satırı + test. 4. (İsteğe bağlı) `queue_pin`.

Etkilenen: `backend/app/recommend/api.py`, `backend/app/profile/api.py`, `mobile/lib/screens/discover_screen.dart`. Algoritma/parametre değişmez; algoritma sürümü artmaz.
