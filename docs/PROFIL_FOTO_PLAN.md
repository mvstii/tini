# Profil fotoğrafı — sunucuda saklama planı

Durum: **onaylandı, backend PR'ı uygulanıyor** (13 Kasım 2026; geliştirici kararları: çıkışta sunucu fotoğrafı kalır, 256 KB, yalnızca JPEG, önce backend sonra mobil). CLAUDE.md gereği yeni tablo/göç ve yeni uç nokta büyük değişikliktir.

## Amaç

Profil fotoğrafı bugün yalnızca cihazda durur (`mobile/lib/profile_photo.dart`). Cihaz değişince ya da uygulama yeniden kurulunca kaybolur. Amaç: fotoğrafı hesaba bağlı, kişisel veri olarak sunucuda tutmak; hesap silinince tamamen silmek.

## Karar: Postgres `bytea`

- Render diski kalıcı değil (dosya sistemi yeniden dağıtımda sıfırlanır); nesne depolama (S3/R2) yeni bağımlılık, yeni gizli bilgi ve yeni maliyet getirir. Tek kullanıcı başına tek küçük görsel için ikisi de gereksiz.
- 512 px JPEG ≈ 30–80 KB; üst sınır 256 KB. 100 kullanıcı ≈ 8 MB, Neon ücretsiz kotasında (0,5 GB) gözle görülmez.
- `ON DELETE CASCADE` ile hesap silme kendiliğinden çalışır (`app/jobs/delete_user.py` ve `DELETE /me` zaten bu kurala dayanır); ayrı temizlik kodu yazılmaz.
- Ödünleşim: görsel veritabanı yedeğini şişirir ve bağlantı başına ek bayt taşır. Bu yüzden `GET /me/photo` ayrı uçtur; `/me` ve diğer yanıtlara gömülmez.

## Şema (göç `0023_user_photo`)

```
user_photo
  user_id     uuid  PK, FK user_account(id) ON DELETE CASCADE
  content     bytea NOT NULL            -- en çok 262144 bayt
  mime        varchar(32) NOT NULL      -- yalnızca image/jpeg
  etag        varchar(40) NOT NULL      -- içeriğin SHA-1'i; istemci önbelleği için
  updated_at  timestamptz NOT NULL default now()
```

Kişisel veri tablosudur; paylaşılan katalog/grafik verisiyle karışmaz (CLAUDE.md kuralı).

## Uç noktalar (`app/photo.py`, yeni modül; `main.py`'ye router eklenir)

| Uç | Davranış |
|---|---|
| `PUT /me/photo` | Gövde ham `image/jpeg`. Oturum zorunlu. >256 KB → 413. JPEG sihirli baytı (`FF D8 FF`) yoksa → 415. Upsert; yeni `etag` döner. |
| `GET /me/photo` | Oturum zorunlu. `If-None-Match` eşleşirse 304; fotoğraf yoksa 404. `Cache-Control: private, max-age=0, must-revalidate`. |
| `DELETE /me/photo` | 204; yoksa da 204 (idempotent). |

- Yalnızca kullanıcının kendi fotoğrafı: başka kullanıcı kimliği alan yok, `user_id` oturumdan gelir.
- `PUT` için hız sınırı gerekir. `app/ratelimit.py` şu an `SlidingWindowLimiter` + giriş/kayıt ayarlarını (`AuthLimits`) içerir; fotoğraf için aynı sınıftan ayrı bir örnek (kullanıcı başına, ör. saatte 10) eklenir ve ayar `config.py`'den gelir.
- Gövde boyutu `Content-Length` ve okunan bayt sayısıyla sınırlanır (bellek şişmesin).
- Görsel çözülüp yeniden kodlanmaz (Pillow bağımlılığı eklenmez); istemci zaten 512 px/JPEG üretir. Sihirli bayt + boyut + mime kontrolü yeterli; sunucu görseli yorumlamadığı için ayrıştırıcı saldırı yüzeyi yok. Sınırı: kötü niyetli kullanıcı geçerli başlıklı bozuk bir dosya yükleyebilir, yalnızca kendi ekranında bozuk görüntü olur.

## İstemci (`mobile/`)

- `ProfilePhotoStore` yerel dosyayı **önbellek** olarak tutmaya devam eder; kaynak sunucudur.
  - Seçim sonrası: yerel kaydet → `PUT /me/photo` (başarısızsa yerel kalır, sonraki açılışta yeniden denenir).
  - Açılışta Profil: yerel dosya varsa hemen göster; `GET /me/photo` ile `If-None-Match` gönder, 200 gelirse yerel dosyayı güncelle, 404 ise yereli sil.
  - Kaldır: `DELETE /me/photo` + yerel sil.
  - Çıkışta yalnızca yerel dosya silinir (sunucudaki fotoğraf hesapla kalır); hesap silinince sunucu kendisi siler.
- `Api` sınıfına üç metot eklenir; ağ hatası UI'yı bozmaz (sessiz).
- Gizlilik: `NSPhotoLibraryUsageDescription` metinlerindeki "yalnızca bu cihazda saklanır" ifadesi **"hesabında saklanır"** olarak güncellenir; gizlilik politikası (Faz 7) taslağına fotoğraf satırı eklenir.

## Testler

- Backend (yalnızca CI'da çalışır, yerelde Python yok): PUT/GET/DELETE yolu; 413, 415, 401; `If-None-Match` → 304; kullanıcı A, B'nin fotoğrafını göremez; `delete_user` ve `DELETE /me` sonrası satır kalmaz (`tests/test_delete_user.py` kalıbı).
- Mobil: sahte `Api` ile yükleme/indirme/404 senaryoları; eklenti yokken sessiz düşme (mevcut testler gibi).

## Adımlar ve sıra

1. Backend PR (`feat/profile-photo-server`): göç 0023, model, `photo.py`, testler. `main`'e birleşince Render'a dağıtılır; göç açılışta `Dockerfile` `CMD`'sindeki `alembic upgrade head` ile kendiliğinden uygulanır (`docs/DAGITIM.md`).
2. Mobil PR: `Api` metotları + `ProfilePhotoStore` eşitlemesi + izin metni. Backend canlıya çıkmadan birleştirilmez (eski sunucuda 404 döner; istemci sessiz düşer, ama gereksiz istek olur).
3. `docs/DURUM.md`, `docs/KESIF_OTURUM.md`, `docs/ROADMAP.md` güncellenir; APK/IPA yeniden alınır.

## Riskler

- **Göç canlıda:** yeni tablo ekler, mevcut veriye dokunmaz; geri alma `downgrade` ile tabloyu düşürmektir. Düşük risk.
- **Yedek/KVKK:** fotoğraf yüz içerebilir, yani kişisel veri. Hesap silmede cascade ile silinir ama Neon yedeklerinde geçici kalabilir; gizlilik metninde belirtilir.
- **Kötüye kullanım:** hız sınırı + 256 KB üst sınır; yine de kullanıcı başına tek kayıt olduğundan depolama büyümesi sınırlı.
- **Doğrulanamayanlar:** Neon kotasının güncel değeri (0,5 GB varsayımı) ve Render'ın istek gövdesi sınırı canlıda denenmedi; backend PR'ında staging'de doğrulanır.

## Karar bekleyen sorular

1. Çıkışta sunucudaki fotoğraf kalsın mı (önerilen, hesap kalıcıdır) yoksa çıkışta da silinsin mi?
2. 256 KB üst sınır ve yalnızca JPEG kabulü uygun mu?
3. Backend PR'ı önce, mobil PR'ı sonra sırası uygun mu?
