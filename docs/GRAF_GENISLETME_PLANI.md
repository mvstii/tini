# Sanatçı grafiğini sürekli genişletme — plan

Durum: onaylandı, uygulandı (S1-15). İstemci (APK) değişmez. Şema değişikliği yok (A ve B adımları); C adımı yeni bir iş/bağımlılık içerir, ayrıca onay istenir.

## Sorun
- Genişleme yalnızca elle (`python -m app.jobs.expand`) ve yalnızca **kütüphane sanatçılarından** başlar (`load_anchors`). Render'da hiç çalışmıyor; kullanıcı yeni sanatçı oyladıkça grafik büyümüyor.
- Komşu sanatçıların çoğunun `Track` kaydı yok; öneri listesi `track_id`'siz öğeleri kuyrukta kullanamıyor → liste kısa kalıyor.

## Adımlar

### A. Otomatik genişleme (sunucu içi, `releases/scheduler.py` kalıbı)
- `graph/scheduler.py`: lifespan görevi; her turda `expand(limit=graph_auto_limit)` (başlangıç 60 sanatçı/tur ≈ 15 sn, Last.fm 0.25 sn aralığı). Sunucu uyuyorsa tur atlanır; TTL'li `FetchLog` yinelenen çağrıyı önler.
- Çapalar genişler: kütüphane **+ oylanan sanatçılar + öneri listelerindeki sanatçılar** (`load_anchors`'a iki kaynak daha). Böylece her oy, sonraki turda o sanatçının komşularını getirir.
- Ayarlar `GraphSettings`'te: `auto_expand`, `auto_expand_hours`, `auto_expand_limit`, `auto_expand_delay_seconds`.

### B. Oy sonrası öncelikli genişletme
- `/votes` oy yazınca, o sanatçı `FetchLog`'da yoksa arka plan görevine (`BackgroundTasks`) tek `fetch_one` kuyruğa alınır. Böylece 5 oylık profil yenilemesinde yeni sanatçının komşuları hazır olur.
- Derinlik 2 kalır (`expand_depth`); 3 yapılırsa Last.fm 100 MB sınırı hızla dolar (şimdiki tahmin: ~20 komşu × kenar başına ~16 bayt, 100 bin sanatçıda ≈ 32 MB).

### C. Komşu sanatçılara parça kapsaması (onay ister)
- Komşu sanatçıların `Track`'i yoksa liste öğesi kullanılamaz. Seçenekler:
  1. **MusicBrainz**: sanatçının kayıtlarından ISRC'li ilk N parça (çekirdek kaynak, ücretsiz, 1 istek/sn). Yavaş ama yasal ve kalıcı (ISRC paylaşılan katalogda durabilir).
  2. **Last.fm `artist.getTopTracks`** + adaptör aramasıyla ISRC çözümü: hızlı, ancak Spotify yanıtından yalnızca ISRC saklanabilir (karar 29 Ekim); Last.fm sınırına yük bindirir.
- Önerim: 1 (MusicBrainz), lazy: yalnızca öneri listesine **giren ama parçası olmayan** sanatçı için, turda en çok `auto_tracks_limit` sanatçı.

## Riskler
- Render ücretsiz katman uykuya geçer: tur yalnızca uyanıkken çalışır; kullanıcı kullanırken zaten uyanıktır.
- Last.fm 100 MB: `enforce_size_cap` zaten en eskileri atıyor; boyut her turda loga yazılır.
- Ticari kullanım için Last.fm izni borcu sürüyor (mağaza öncesi).

## Test
- `load_anchors` oylanan/önerilen sanatçıları içerir; zamanlayıcı kapalıyken görev başlamaz; `fetch_one` oy sonrası tek kez çağrılır (FetchLog isabeti); C için sahte MusicBrainz istemcisiyle ISRC'li parça yazılır, ISRC'siz atlanır.
