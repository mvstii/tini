# Faz 3 Planı — Profil ve öneri motoru v1

Taslak: 30 Ekim 2026 · Durum: **onaylandı** (S1 #16, S2 #17 birleşti, S3 PR'da) · Süre: 7–20 Aralık (erken başlanabilir; Faz 2 kapısı geçildi)

Kapı: kendi oylarınla üretilen listede gerekçeler mantıklı görünüyor.

## Mevcut zemin

- `vote_event` (silinmeyen olay kaydı, UPDATE tetikleyiciyle engelli), `track.artist_id`, `user_track_artist` (kademe B bağı), `artist_edge` + `graph_snapshot`, `graph/matrix.py` ve `graph/neighborhood.py` (saf, sürümlü anlık görüntüye bağlı) hazır.
- Oy yazma/okuma uç noktası, profil, liste tabloları **yok**.
- Grafik sanatçı düzeyinde (hibrit karar): PPR sanatçı düğümlerinde, sanatçı içinde şarkı seçimi oy ve etiketle yapılır.

## Önerilen aşamalar (her biri ayrı PR, her aşama sonrası DURUM.md ve telefon bildirimi)

| # | Aşama | İçerik |
|---|---|---|
| S1 | Oy olayı + güncel oy | `POST /votes`, `GET /votes/current` (parçanın son olayı); skor eşlemesi, ≥30 oydan sonra persentil normalizasyonu ve zaman sönümü (saf `profile/scoring.py`). Göç yok, mevcut `vote_event` yeter. |
| S2 | Profil anlık görüntüsü | Göç 0006 `taste_profile` (sürümlü: `user_id`, `version`, `algo_version`, `graph_version`, `created_at`, JSON gövde). Saf `profile/build.py`: pozitif oyları sanatçı vektörüne topla, KMeans kümeleri (tohum parametre), Amazing → çapa, Awful/Bad → kaçınma bölgesi. |
| S3 | PPR aday skoru + gerekçe | Saf `recommend/ppr.py`: çapa başına ayrı başlangıç vektörü (doğrusallık → gerekçe), Awful budama, Bad cezası, yenilik bonusu. Gerekçe = en çok katkı veren 1–3 çapa; hesabın kendisinden. |
| S4 | Liste üretimi | MMR çeşitlilik, sanatçı üst sınırı, sanatçı içi şarkı seçimi. Göç 0007 `generated_list` + `list_item` (algoritma ve grafik sürümü, gerekçe). `POST /lists/generate`, `GET /lists/{id}`. |
| S5 | Sentetik veri + kapı | Sentetik oy seti ve özellik testleri (determinizm, gerekçe toplamı = skor); gerçek oylarla elle bakış. |

Tüm parametreler (λ, β, γ, küme sayısı, keşif/yenilik oranı, MMR λ, sanatçı sınırı, sönüm yarı ömrü) `config.py` içinde yeni `ProfileSettings` / `RecommendSettings` bloklarından gelir. Algoritma sürümü her profil ve listeye yazılır. Her aşamada birim test zorunlu.

## Karar bekleyen noktalar

1. **Oy girişi için veri kaynağı.** Mobil oylama ekranı Faz 4'te. Faz 3 kapısı için oylar geçici olarak API/betikle girilecek (ör. `python -m app.jobs.seed_votes` kütüphaneden). Öneri: betik, kullanıcı elle CSV/komut satırıyla verir. Onay?
2. **Sanatçı etiketleri** (ROADMAP Faz 2'de açık kalem). Öneri: v1'de yok; yenilik bonusu ve sanatçı içi seçim yalnızca oy ve grafik ağırlığıyla yapılır, etiketler Faz 5+ (ListenBrainz/MusicBrainz etiketi) karar verilir. Risk: sanatçı içi şarkı seçimi daha zayıf kalır.
3. **22 sanatçı Last.fm'de boş, ~%6 parça grafikte çapa olamıyor.** Öneri: bu parçalar oylanabilir kalır, profilde sayılır ama PPR'a çapa girmez; kapı ölçümünde oranı raporlanır.
4. **Çok işçili matris önbelleği** (S4 notu): Faz 3'te tek işçi varsayılır; paylaşılan önbellek Faz 4+'a kalır.
5. **Yeni bağımlılık:** scikit-learn (KMeans). Değişmez karar listesinde zaten yığının parçası; yine de onay istiyorum.

## Riskler

- Tek kişinin sahnesi: gerçek oylar azken (<30) persentil normalizasyonu devreye girmez, soğuk başlangıç skorları kullanılır.
- Last.fm ağırlıkları popüler sanatçıya yanlı; PPR sonuçları popülerliğe kayabilir. Yenilik bonusu ve derece normalizasyonu bunu kısmen dengeler, kapıda gözle kontrol edilecek.
- Last.fm izni gelmeden üretim bağımlılığı yok sayılır (yedek: kendi eşzamanlılık matrisi, Faz 3 kapsamı dışı).
