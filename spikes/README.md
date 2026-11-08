# spikes/ — Faz 0 doğrulama betikleri

Atılabilir betikler; üretim kodu değildir. Yalnızca Python standart kütüphanesi kullanır. Çıktılar `spikes/out/` içine yazılır (git'e girmez).

## Gereken `.env` değişkenleri

`.env.example` dosyasına da ekle (bu oturumda o dosyaya erişimim kapalıydı):

```
SPOTIFY_CLIENT_ID=
LASTFM_API_KEY=
LISTENBRAINZ_ALGORITHM=   # isteğe bağlı
```

Spotify dashboard'da redirect URI: `http://127.0.0.1:8888/callback`

## Sıra

```bash
python spikes/spotify_probe.py     # tarayıcıda izin ver; uç nokta durumları + sample.json
python spikes/coverage_probe.py    # ISRC/MBID/benzerlik/etiket kapsamı + kapı sonucu
python spikes/lb_genre_probe2.py --phase offline     # PR-0 ek prob A0: eski json/önbellekten çevrimdışı analiz, 0 istek
python spikes/lb_genre_probe2.py --phase p0 --dry-run  # faz bütçelerini basar, istek atmaz (ağ fazları G4+)
python spikes/lb_genre_probe2.py --phase excl|lang      # ülke/işaret dışlaması ve kayıt dili düzeltmesi, 0 istek (işaretli örnek dosyalarından)
python spikes/lb_genre_probe2.py --phase rockx|arabeskx # havuz genişletme (istek atar; bütçe ve 429'da durma)
python spikes/lb_genre_probe2.py --phase isrcfill       # MusicBrainz rid ile ISRC doldurma (az fayda; asıl çözüm PR-4b)
python spikes/lb_genre_probe2.py --phase repro [--repro-dir spikes/out/seed2]  # ana koşu ile ikinci tohum karşılaştırması (C/A/pay, Jaccard, A_düz); ikinci koşu --out-dir ile ayrı dizine yazılır
# bayraklar: --out-dir (çıktı dizini), --suffix (dosya soneki), --only-new (yalnız yeni sanatçılar), --n-rec, --max-per-art
python -m unittest discover -s spikes -p "test_lb_genre_probe2.py"
```

Niş kapsamı için `spikes/out/sample_niche.json` dosyasını elle oluştur (~50 az bilinen şarkı, kendi dinlediklerinden):

```json
[{"title": "...", "artist": "...", "isrc": "opsiyonel"}]
```

`coverage_probe.py` şarkıları Last.fm dinleyici sayısına göre "yaygın" ve "niş" (`NICHE_LISTENERS`, varsayılan 50000) katmanlara ayırır. Özet hem katman bazında hem de Last.fm olmadan (ListenBrainz, Deezer, MusicBrainz ilişkileri) kapsamı verir. Süre: şarkı başına ~5 sn (MusicBrainz 1 istek/sn), 150 şarkı için ~12 dk.

Sonuçları (`spotify_probe.json`, `coverage.csv`, konsol özeti) bana ver; `docs/ARCHITECTURE.md`'ye işlerim.
