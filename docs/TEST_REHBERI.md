# Tını — Kapalı Test Rehberi

Tını, şarkıları 6 kademede oylatarak müzik zevkini çıkarır ve önerdiği her şarkının **gerekçesini** gösterir. Bu bir erken sürüm; amaç önerilerin gerçekten işe yarayıp yaramadığını ölçmek.

## Ne saklıyoruz? (açık rıza)

Katılarak şunların saklanmasını kabul etmiş olursun: e-posta adresin, verdiğin oylar, bunlardan çıkan zevk profilin, Spotify kütüphanenden aktarılan şarkıların kimliği (ISRC) ile şarkı/sanatçı adları (adlar yalnızca sana özel, geçici önbellekte tutulur), Spotify bağlantı anahtarın (şifreli) ve gönderdiğin geri bildirimler. Veriler yalnızca test geliştiricisinin kendi bilgisayarında durur, kimseyle paylaşılmaz, reklam ya da model eğitimi için kullanılmaz. İstediğin an geliştiriciye yaz: hesabın ve tüm kişisel verin kalıcı olarak silinir. Katılım gönüllüdür.

## Kurulum (Android)

1. Geliştiricinin gönderdiği `app-release.apk` dosyasını telefona indir.
2. Aç. Android "bilinmeyen kaynaklardan yükleme" izni isteyecek; o an kullandığın uygulama (Drive, Telegram, Dosyalar) için ver.
3. Kur ve Tını'yı aç. İlk açılışta **kayıt ol** (e-posta + parola).
4. Spotify hesabının e-postasının geliştirici tarafından test listesine eklenmiş olması gerekir; eklenmediyse bağlama başarısız olur.

## Adımlar

1. **Spotify'ı bağla:** ana ekranda "Bağla" → tarayıcıda izin ver → uygulamaya dön ("Bağlı" yazmalı).
2. **Kütüphaneyi aktar:** "Kütüphaneyi aktar". Büyük kütüphanede birkaç dakika sürebilir; bekle.
3. **Oyla:** "Oylamaya başla". 1 (Awful) ile 6 (Amazing) arası oy ver; nötr seçenek yok. Dinlemediğin şarkıyı sola kaydır (Unheard). Oylar silinmez, fikrini değiştirirsen yeniden oyla.
4. **Hedef: en az 100 oy.** Sayıyı "Oy geçmişi" ekranından görebilirsin. 2-3 günde, birkaç oturumda vermen yeterli.
5. **Listeyi dene:** "Keşif listesi" → listeyi üret. Her şarkının altında neden önerildiği yazar. Gerekçe yanlış geliyorsa itiraz et.
6. **İstersen** "Yeni çıkanlar" ve Spotify'a çalma listesi aktarmayı da dene.

## Geri bildirim

Ana ekranın altında **"Geri bildirim gönder"**: tür (Hata / Öneri / Diğer) seç, ne olduğunu ve ne beklediğini yaz. Küçük şeyleri de yaz: yavaşlık, anlaşılmayan metin, tuhaf öneri. "Bu öneri çok isabetli/saçma" demek de çok değerli.

## Bilinen sınırlar

- Sunucu geliştiricinin bilgisayarında; kapalıysa "Sunucuya ulaşılamadı" görürsün, biraz sonra tekrar dene.
- Yalnızca Android. Uygulama henüz görsel olarak cilalı değil; cila testten sonra.
- Spotify'dan alınan bazı şarkılar eşleşmeyebilir ("atlandı" sayısı); normal.

## Sorun olursa

Geliştiriciye ekran görüntüsüyle yaz. Hesabını sildirmek için de aynı kanal.
