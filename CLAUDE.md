# CLAUDE.md — Tını

Bu dosya, bu depoda çalışan Claude Code için proje bağlamını ve çalışma kurallarını tanımlar. Her oturumun başında okunur.

## Proje nedir?

Tını, şarkıları 6 kademeli bir ölçekte (nötr seçenek yok) oylatarak kullanıcının müzik zevkini çıkaran ve **her önerisinin gerekçesini gösteren** keşif listeleri üreten bir mobil uygulamadır. Taste.io'nun film/dizi oylama mantığının müziğe uyarlanmasıdır.

- Geliştirici: tek kişi (Yazılım Mühendisliği öğrencisi), en rahat dilleri Python ve C/C++.
- Hedef: önce çalışan, kullanılabilir bir MVP; ardından Play Store ve App Store yayını.
- Ayrıntılı kaynak: `docs/ARCHITECTURE.md` ve `docs/ROADMAP.md`. Güncel ana doküman Claude Docs'taki "Tını — Mimari Doküman ve Proje Planı"dır: https://claude.ai/artifact/N22bDxuQJsPMLXpLVX43gq

## Değişmez kararlar

Bu kararları geliştiriciye sormadan değiştirme:

1. **Zevk zekâsı çekirdektedir.** Oylar, profil, grafik ve öneri tamamen bizim backend'imizde çalışır. Hiçbir müzik servisi çekirdeğin parçası değildir.
2. **Müzik servisleri adaptördür.** Spotify, Apple Music ve bağlantısız mod aynı adaptör arayüzünü uygular (eşle, kütüphaneyi oku, playlist yaz, çal). Çekirdek kodunda servis adı geçmez.
3. **Spotify yalnızca kapalı test içindir.** Development Mode en fazla 5 kullanıcıya izin verir. Yayında ana servis Apple Music'tir.
4. **Kapalı Spotify uç noktalarını kullanma.** `recommendations`, `audio-features`, `audio-analysis`, `related-artists`, `new-releases`, `artist top-tracks` ve `preview_url` yeni uygulamalar için çalışmaz; bunlara dayanan kod yazma. `popularity` alanı da yok.
5. **Spotify verisiyle ML modeli eğitilmez.** Özellikler Last.fm, ListenBrainz ve MusicBrainz gibi üçüncü taraf kaynaklardan gelir.
6. **Oylar silinmeyen olay kaydıdır.** Oy değişikliği yeni bir olaydır; güncel oy son olaydır. Profiller bu kayıttan türetilen sürümlü anlık görüntülerdir.
7. **Her öneri gerekçe taşır.** Gerekçe hesabın kendisinden (PPR'ın çapa bazlı doğrusal ayrışımından) türetilir, sonradan uydurulmaz.
8. **Akustik analiz v1'de yoktur.** v2'de, ölçütleri iyileştirdiği kanıtlanırsa eklenir.

## Oylama ölçeği

| Oy | Etiket | Başlangıç skoru | Rol |
|---|---|---|---|
| 1 | Awful | −1.0 | Sert filtre, kaçınma bölgesi |
| 2 | Bad | −0.6 | Yumuşak ceza |
| 3 | Meh | −0.15 | Zayıf negatif |
| 4 | Good | +0.35 | Profili besler |
| 5 | Great | +0.7 | Profili güçlü besler |
| 6 | Amazing | +1.0 | Çapa (seed) |
| — | Unheard | yok | Keşif havuzu adayı (durum makinesi) |

## Mimari ve yığın

- **Mobil:** Flutter (iOS + Android), ince istemci → `mobile/`
- **Backend:** Python + FastAPI, modüler monolit → `backend/`
  - Modüller: `catalog`, `graph`, `profile`, `recommend`, `releases`, `adapters`
- **Veritabanı:** PostgreSQL + pgvector
- **Hesaplama:** NumPy, SciPy (seyrek matrisle PPR), scikit-learn
- **Dağıtım:** Docker Compose

## Kodlama kuralları

- Algoritma kodu **saf fonksiyonlar** olarak yazılır: aynı oy geçmişi her zaman aynı profili ve listeyi üretir. Rastgelelik varsa tohum (seed) parametre olarak verilir.
- Algoritma parametreleri (λ, β, γ, küme sayısı, keşif oranı) kodun içine gömülmez; tek bir yapılandırma noktasından gelir.
- Her profil ve listeye algoritma sürümü yazılır.
- Algoritma değişikliği birim testi olmadan birleştirilmez.
- Dış API çağrıları yalnızca adaptör veya kaynak istemcisi modüllerinde yapılır; önbellek ve 429 geri çekilme orada ele alınır.
- **Spotify verisi kalıcı saklanmaz** (Developer Terms v10: yalnızca geçici metadata önbelleği). Parçanın kalıcı kimliği ISRC/MBID'dir; başlık, sanatçı ve süre MusicBrainz'den gelir. Spotify yanıtları yalnızca TTL'li önbellekte durur (TTL yapılandırmadan gelir, başlangıç 24 saat). Spotify ID yalnızca kullanıcıya özel eşleme olarak tutulur.
- **Last.fm verisi 100 MB sınırı altında tutulur** (API ToS "Reasonable Usage Cap"). Ham yanıt saklanmaz; düğüm başına en çok ~20 komşu, tamsayı kimlik ve ağırlıkla kompakt yazılır, boyut izlenir, sınıra yaklaşınca en eskiler atılır. Last.fm zorunlu kaynak değil, ikincil kaynaktır; çekirdek kaynaklar ListenBrainz ve MusicBrainz'dir. Ticari kullanım için Last.fm'in önceden izni gerekir.
- Gizli bilgiler yalnızca `.env` içindedir (şablon: `.env.example`). Token'lar veritabanında şifreli saklanır.
- Kişisel veri (oylar, profil, token) ile paylaşılan katalog/grafik verisi ayrı tutulur; hesap silindiğinde kişisel veri tamamen silinir.

## Çalışma şekli

- **İletişim dili Türkçedir.** Kod, değişken adları ve commit mesajları İngilizce olabilir; dokümanlar Türkçedir.
- Geliştirici, tecrübeli bir yazılım mühendisi bakış açısı ister: kararların gerekçesini ve ödünleşimlerini açıkla, riskleri saklama.
- **Faz sırasına uy.** Güncel faz `docs/ROADMAP.md` içindeki ilk tamamlanmamış fazdır. Kapısı geçilmemiş bir fazın işine, geliştirici istemeden başlama.
- Büyük bir değişiklikten (yeni modül, şema değişikliği, bağımlılık ekleme) önce kısa bir plan sun ve onay al.
- Bir fazın görevi bittiğinde `docs/ROADMAP.md` içindeki kutuyu işaretle.
- Bir dış API'nin davranışı belirsizse varsayma; Faz 0'daki gibi önce doğrula ve sonucu `docs/ARCHITECTURE.md`'ye not et.
- Bu dosyadaki bir kararla çelişen bir istek gelirse, çelişkiyi belirt ve hangisinin geçerli olduğunu sor.

## Güncel durum

- Planlama tamamlandı (29 Ekim 2026).
- Sıradaki adım: **Faz 0 — Fizibilite** (2–8 Kasım 2026). Bu fazda üretim kodu yazılmaz; yalnızca API doğrulama denemeleri ve ölçümler yapılır.
