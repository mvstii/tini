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
```

Niş kapsamı için `spikes/out/sample_niche.json` dosyasını elle oluştur (~50 az bilinen şarkı, kendi dinlediklerinden):

```json
[{"title": "...", "artist": "...", "isrc": "opsiyonel"}]
```

`coverage_probe.py` şarkıları Last.fm dinleyici sayısına göre "yaygın" ve "niş" (`NICHE_LISTENERS`, varsayılan 50000) katmanlara ayırır. Özet hem katman bazında hem de Last.fm olmadan (ListenBrainz, Deezer, MusicBrainz ilişkileri) kapsamı verir. Süre: şarkı başına ~5 sn (MusicBrainz 1 istek/sn), 150 şarkı için ~12 dk.

Sonuçları (`spotify_probe.json`, `coverage.csv`, konsol özeti) bana ver; `docs/ARCHITECTURE.md`'ye işlerim.
