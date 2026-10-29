# Tını

> Şarkıları 6 kademeli bir ölçekte oyla, zevkini keşfet, gerekçeli keşif listeleri al.

Tını, kullanıcının müzik zevkini nötr seçeneği olmayan 6 kademeli oylamayla çıkaran ve buna göre **her önerisinin nedenini gösteren** keşif listeleri üreten bir mobil uygulamadır. Zevk zekâsı tamamen uygulamanın kendi çekirdeğinde çalışır; Apple Music ve Spotify gibi müzik servisleri değiştirilebilir bağlantılardır.

> **Durum:** Planlama tamamlandı, geliştirme Faz 0 (fizibilite) ile 2 Kasım 2026'da başlıyor. Henüz çalışan kod yok.

---

## Nasıl çalışır?

### 1. Oyla

| Oy | Etiket | Anlamı |
|---|---|---|
| 1 | Awful (Berbat) | Bir daha karşıma çıkmasın |
| 2 | Bad (Kötü) | Sevmedim |
| 3 | Meh (İdare eder) | Tolere ederim |
| 4 | Good (İyi) | Sevdim |
| 5 | Great (Çok iyi) | Çok sevdim |
| 6 | Amazing (Efsane) | Zevkimin çapası |
| — | Unheard (Daha Dinlemedim) | Bilmiyorum, sonra karar vereceğim |

Oylar her zaman değiştirilebilir. "Daha Dinlemedim" dediğin şarkılar kaybolmaz; zevkine uyanlar keşif listelerine aday olur ve dinledikten sonra tekrar oylaman istenir.

### 2. Zevk profilin çıkar

Tek bir ortalama yerine **çok modlu bir profil** hesaplanır: sevdiğin şarkılar "zevk modları"na kümelenir, Amazing şarkıların bu modların çapası olur, Awful ve Bad oyların ayrı bir kaçınma bölgesi oluşturur.

### 3. Gerekçeli öneriler al

Öneriler, çapa şarkılarından başlayan bir benzerlik grafiği yürüyüşüyle (kişiselleştirilmiş PageRank) üretilir. Bu yöntem doğrusal olduğu için her önerinin hangi şarkılarından geldiği doğrudan hesaplanır:

> **Neden bu şarkı?** "Amazing verdiğin 2 şarkıya benziyor · ortak etiketler: dream pop, shoegaze · Keşif"

### 4. Listeni kaydet

- **Keşif listesi:** bilinen sevdiklerin, uyumlu "Daha Dinlemedim" şarkıları ve yeni keşiflerin karışımı
- **Haftalık Taze listesi:** takip ettiğin sanatçıların yeni yayınları ve zevkine uyan yeni çıkanlar

Listeler bağlı müzik servisine kaydedilir; servis bağlamayan kullanıcı her şarkıyı istediği uygulamada açabilir.

---

## Mimari

```
┌──────────────────────────────────────────────┐
│          Mobil uygulama (Flutter)            │
└──────────────────────┬───────────────────────┘
                       │ REST API
┌──────────────────────▼───────────────────────┐
│   Tını çekirdeği — FastAPI, PostgreSQL       │
│   Oylar/profil · Öneri motoru · Benzerlik    │
│   grafiği · Yeni çıkanlar                    │
└─────────▲──────────────────────────┬─────────┘
          │ veri                     │ eşle, oku, yaz, çal
┌─────────┴──────────┐     ┌─────────▼──────────┐
│ Keşif kaynakları   │     │ Servis adaptörleri │
│ Last.fm            │     │ Apple Music        │
│ ListenBrainz       │     │ Spotify (test)     │
│ MusicBrainz        │     │ Bağlantısız mod    │
└────────────────────┘     └────────────────────┘
```

**Neden Spotify merkezde değil?** Spotify, Kasım 2024'ten beri yeni uygulamalara öneri ve ses özelliği uç noktalarını kapattı; Şubat 2026'dan beri de Development Mode uygulamalarını en fazla 5 kullanıcıyla sınırlıyor. Bu yüzden Spotify kapalı testte kullanılır, yayında ana servis Apple Music'tir.

Ayrıntılar: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Teknoloji yığını

| Katman | Seçim |
|---|---|
| Mobil | Flutter (iOS + Android) |
| Backend | Python, FastAPI |
| Veritabanı | PostgreSQL + pgvector |
| Hesaplama | NumPy, SciPy (seyrek matris PPR), scikit-learn |
| Dağıtım | Docker Compose |

## Yol haritası

- [ ] **Faz 0** — Fizibilite (2–8 Kasım 2026)
- [ ] **Faz 1** — Temel altyapı: hesap, Spotify bağlantısı, veri modeli (9–22 Kasım)
- [ ] **Faz 2** — Katalog ve benzerlik grafiği (23 Kasım–6 Aralık)
- [ ] **Faz 3** — Profil ve öneri motoru v1 (7–20 Aralık)
- [ ] **Faz 4** — Mobil deneyim ve playlist çıktısı (21 Aralık–3 Ocak)
- [ ] **Faz 5** — Keşif döngüsü ve yeni çıkanlar (4–17 Ocak 2027)
- [ ] **Faz 6** — Kapalı test, MVP (18–24 Ocak)
- [ ] **Faz 7** — Yayın hazırlığı: Apple Music, TestFlight, Play kapalı test (25 Ocak–21 Şubat)

Ayrıntılı görevler: [docs/ROADMAP.md](docs/ROADMAP.md)

## Proje yapısı

```
tini/
├── backend/     # FastAPI servisi ve öneri motoru (Faz 1'de başlar)
├── mobile/      # Flutter uygulaması (Faz 1'de başlar)
└── docs/        # Mimari doküman ve yol haritası
```

## Veri ve gizlilik

- Oylar, profil ve servis bağlantıları kişisel veridir; hesap silindiğinde tamamen silinir.
- Paylaşılan katalog ve benzerlik grafiği kişisel veri içermez.
- Müzik servislerinden alınan veriler model eğitiminde kullanılmaz.

## Teşekkür

Oylama fikri [Taste.io](https://www.taste.io)'nun film ve dizi oylama yaklaşımından ilham alır. Benzerlik verisi [Last.fm](https://www.last.fm/api), [ListenBrainz](https://listenbrainz.org) ve [MusicBrainz](https://musicbrainz.org) tarafından sağlanır.
