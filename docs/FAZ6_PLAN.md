# Faz 6 Planı — Kapalı test

Taslak: 2 Kasım 2026 · Durum: **onaylandı (2 Kasım 2026; ücretli hiçbir şey yayın öncesine kadar yapılmaz)** · Süre: 18–24 Ocak (erken başlanabilir; Faz 5 kapısı geçildi, 1 Kasım 2026)

Kapı: 5 test kullanıcısının her biri en az 100 oy verdi ve kritik hata yok.

## Mevcut zemin

- Backend yalnızca geliştirici makinesinde `uvicorn` ile çalışıyor; mobil emülatörde `10.0.2.2:8000`'e bağlanıyor. Arkadaşların telefonlarının ulaşabileceği bir sunucu yok.
- Spotify OAuth Development Mode'da: en fazla 5 kullanıcı, her biri geliştirici panelinden e-postayla elle eklenir (senin işin).
- Mobil yalnızca emülatörde denendi; gerçek cihaz, APK/TestFlight paketi ve sunucu adresi yapılandırması yok.
- Geri bildirim kanalı yalnızca liste öğesi itirazı (`list_feedback`); genel hata/öneri bildirimi yok.
- Değerlendirme betiği hazır (`python -m app.jobs.evaluate EPOSTA`) ama gerçek örnekle hiç koşmadı (tek kullanıcıda oranlar anlamsız).
- Bandit önceleri ve `eval_min_sample` varsayılan; gerçek veriyle ayarlanmadı.

## Önerilen aşamalar (her biri ayrı PR, her aşama sonrası DURUM.md ve telefon bildirimi)

| # | Aşama | İçerik |
|---|---|---|
| S1 | Sunucuya dağıtım | Docker Compose ile prod yapılandırması (backend + Postgres), HTTPS (ters vekil), `.env` üretim şablonu, günlük `pg_dump` yedeği, `/health`. Ücretsiz çözüm: geliştirici makinesi + sabit adresli tünel (karar 1). Göç yok. |
| S2 | Mobil paketleme | Sunucu adresi derleme zamanı yapılandırması (`--dart-define`), Android imzalı APK; iOS (TestFlight, ücretli) Faz 7'ye ertelendi; testçiler Android. Spotify yönlendirme URI'si gerçek cihazda doğrulanır. Yeni bağımlılık yok. |
| S3 | Geri bildirim ve hata izleme | Uygulama içi "Geri bildirim gönder" (serbest metin + ekran adı + sürüm), kişisel tablo `app_feedback` (göç 0014, hesap silinince silinir). Sunucu tarafı yapılandırılmış hata günlüğü (istek kimliği, kullanıcı kimliği, durum kodu); üçüncü taraf hata servisi eklenmez. **Şema değişikliği: onay şart.** |
| S4 | Test yürütme | Kullanıcı başına kısa başlangıç rehberi (`docs/TEST_REHBERI.md`: kurulum, Spotify bağlama, 100 oya kadar yol, geri bildirim), davet ve takip. 4 arkadaş Spotify paneline eklenir (senin işin), her biri hesap açar, kütüphane içe aktarır, tur + oylama. Günlük `python -m app.jobs.evaluate` ile ilerleme (oy sayısı) izlenir. |
| S5 | Ölçüt ve ayar | 5 kullanıcıdan toplanan olaylarla ROADMAP ölçütleri hesaplanır (Good+ oranı ≥%50, Unheard Good+ ≥%40, itiraz ≤%15, rank korelasyonu). Parametreler (λ, β, γ, bandit önceleri/eşiği, `fresh_share`, `eval_min_sample`) yalnızca yapılandırma noktasından değiştirilir; her değişiklik birim testi ve `algo_version` artışıyla. Sonuçlar `docs/ARCHITECTURE.md`'ye not edilir. |
| S6 | MVP etiketi ve kapı | Kritik hata listesi kapanır, her kullanıcı ≥100 oy, `v0.1.0-mvp` etiketi, DURUM/ROADMAP güncellenir, Faz 7 öncesi Last.fm izni hatırlatılır. |

Her aşamada test; algoritma değişikliği yalnızca S5'te ve test + sürüm artışıyla.

## Karar bekleyen noktalar

1. **Barındırma (S1) — kapandı.** Ücretli VPS yok. Geliştirici makinesinde Docker Compose + ücretsiz tünel. Sabit adres şart (APK'ya gömülür): ngrok ücretsiz statik alan adı (hesap açmak geliştiricinin işi) ya da kendi alan adı gerektirmeyen başka sabit adresli ücretsiz tünel. Rastgele adresli hızlı tüneller (adres her başlatmada değişir) elenir. Ödünleşim: makine test saatlerinde açık olmalı, kesinti olabilir; yedek yerel `pg_dump` ile alınır.
2. **Platform — kapandı.** Yalnızca Android (APK, ücretsiz). iPhone kullanan arkadaş varsa Faz 7'ye kadar katılamaz; 5 kişilik kapı için hepsinin Android olması gerekir (doğrulanacak).
3. **Veri onayı.** Arkadaşların oyları ve Spotify kütüphanesi kişisel veri. Öneri: S4'te bir paragraflık açık rıza metni (ne saklanıyor, nasıl silinir, silme uç noktası var); resmi KVKK metni Faz 7'de.
4. **Spotify sınırı.** Development Mode ≤5 kullanıcı: sen + 4 arkadaş = 5, yani yedek kişi yok. Biri çekilirse Faz 6 kapısı (5 kullanıcı) düşer; bu yüzden erken davet öneriyorum.

## Riskler

- Spotify Development Mode'da kütüphane içe aktarma ve ISRC çözümü 5 kullanıcıda 429'a girebilir; geri çekilme adaptörde var ama yoğun saatte yavaşlama beklenir.
- 100 oy, kütüphanesi küçük kullanıcı için zor olabilir (kuyruk tükenir); aktif öğrenme kuyruğu ve Unheard havuzu bunu kısmen kapatır, S4'te izlenir.
- Gerçek cihazda ilk kez çıkacak hatalar (yönlendirme URI'si, ağ, izinler) S2'de beklenir; tarih payı bırakıldı.
- Ölçütler 5 kişiyle istatistiksel olarak zayıf; hedefler yön gösterici, kesin kanıt sayılmaz.
- Sunucuda tutulan token'lar şifreli, ama arkadaşların verisi artık başka makinede: yedekler de şifreli diskte ve erişim yalnızca senin.
