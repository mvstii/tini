# Faz 5 Planı — Keşif döngüsü ve yeni çıkanlar

Taslak: 31 Ekim 2026 · Durum: **onaylandı (kararlar aşağıda)** · Süre: 4–17 Ocak (erken başlanabilir; Faz 4 kapısı geçildi, 31 Ekim 2026)

Kapı: Unheard döngüsü uçtan uca çalışıyor, ilk haftalık Taze listesi üretildi.

## Mevcut zemin

- Oy olay kaydı (`vote_event`, 1–6), profil anlık görüntüsü, PPR adayları, MMR listesi (`generated_list`, `list_item`), gerekçe itirazı kaydı (`list_feedback`), Spotify'a yazma.
- **Unheard bugün hiçbir yere yazılmıyor:** mobil sola kaydırma oturum içinde atlıyor, parça sonraki oturumda kuyruğa geri geliyor (Faz 4 S2 kararı). Durum makinesi için kalıcı kayıt gerekir.
- Liste öğeleri sanatçı düzeyinde; öğenin sonradan oylanıp oylanmadığını bağlayan bir alan yok, slot tipi yok (hepsi "keşif").
- Yayın verisi yok: MusicBrainz istemcisi yalnızca ISRC→kayıt→sanatçı yapıyor; ListenBrainz istemcisi hiç yazılmadı. Sanatçıların 246'sından 63'ünün MBID'si yok (yalnızca Last.fm kimliği).
- Spotify'dan yayın çekmek seçenek değil: `new-releases` kapalı (değişmez karar 4) ve Spotify verisi kalıcı tutulamaz (karar 5, CLAUDE.md).

## Önerilen aşamalar (her biri ayrı PR, her aşama sonrası DURUM.md ve telefon bildirimi)

| # | Aşama | İçerik |
|---|---|---|
| S1 | Unheard durum makinesi | Göç 0010 `unheard_event` (silinmeyen olay kaydı, `vote_event` gibi UPDATE engelli; durumlar: `pooled`, `presented`, `awaiting`, `expired`; "Oylandı" ayrı durum değil, sonraki `vote_event`'ten türer). Saf `profile/unheard.py`: geçişler ve "N kez sunuldu, oylanmadı → süresi doldu". `POST /votes/unheard`. Mobil: sola kaydırma bu uca yazar. Süresi dolan parça `scoring.py`'de çok zayıf örtük negatif sayılır (N ve ceza `ProfileSettings`'ten; başlangıç N=3, −0,05). Algoritma değişikliği → birim testleri, `algo_version` artar. |
| S2 | Aktif öğrenme kuyruğu | Saf `profile/active.py`: oylanmamış parçalar için belirsizlik skoru; `GET /votes/queue` bunu kullanır, Unheard havuzundakiler "Oylama bekliyor"a geçerek sunulur. Belirsizlik: tahmin edilen skorun karar sınırına yakınlığı (PPR yüzdeliği ≈ 0,5 olan sanatçı önce) + profilde kümesiz/komşusu az sanatçılar; eşitlik tohumlu özet. Göç yok. |
| S3 | Slot dağılımı (Thompson sampling) | Göç 0011: `list_item.slot` (`familiar` / `unheard` / `explore`; mevcut öğeler `explore`). Saf `recommend/bandit.py`: slot başına Beta(a, b) sonsal dağılımı, tohumlu örnekleme, liste boyutu slotlara bölünür. Başarı = öğenin sanatçısına liste tarihinden sonra Good+ (≥4) oy; başarısızlık = Bad− oy veya gerekçe itirazı. Sonuçlar `list_item` + `vote_event` + `list_feedback` birleşiminden **türetilir** (ek tablo yok). Önceller ve slot taban payları yapılandırmadan gelir. `familiar` = yüksek PPR, `unheard` = havuzdaki oylanmamış parça, `explore` = grafikte uzak ama kaçınma bölgesi dışı. |
| S4 | Yayın kaynağı spike + takip listesi | Önce **doğrulama** (ARCHITECTURE'a not): MusicBrainz `release-group` listeleme (sanatçı MBID'siyle, `first-release-date`, hız 1 istek/sn) ve ListenBrainz fresh-releases uçları gerçekten yeni çıkanları verip vermediği. Sonra göç 0012 `release` (paylaşılan katalog: `artist_id`, MB `release-group` kimliği, başlık, tür, tarih; Spotify verisi yok) ve `followed_artist` (kişisel). Takip = net pozitif ve çapa sanatçılar (türetilir) + elle takip/bırakma. `python -m app.jobs.detect_releases` MBID'li takip sanatçıları için yayın çeker, `fetch_log` ile önbellek ve 429 geri çekilme kaynak istemcisinde. |
| S5 | Haftalık Taze listesi + "Yeni" akışı | `generated_list.kind` (`main` / `fresh`, göç 0013). Saf `recommend/fresh.py`: takip sanatçılarının son N gündeki yayınları, profil skoru ve kaçınma bölgesiyle sıralı, sanatçı başına bir yayın, gerekçe "X'i takip ettiğin için". `POST /lists/generate-fresh`, `GET /releases/new`. Ana listede `new` slotu: sabit %10–15 pay (`RecommendSettings`; bandit dışı). Mobil: "Yeni" ekranı (yeni bağımlılık yok). Yayın çalma/aç: sanatçı araması (`open_url` mevcut mantığı; Spotify kimliği saklanmaz). |
| S6 | Değerlendirme betikleri + kapı | `python -m app.jobs.evaluate EPOSTA`: ROADMAP ölçütlerini kişisel olay kayıtlarından hesaplar (önerilenin Good+ oranı, Unheard'in sonradan Good+ oranı, tahmin hatası, gerekçe itiraz oranı, slot başına başarı). Yalnızca okur, salt rapor. Kapı: Unheard döngüsü baştan sona canlı denendi, ilk Taze listesi üretildi. |

Her aşamada birim/entegrasyon testi; algoritma değişiklikleri (S1 örtük negatif, S2 sıralama, S3 bandit) önce saf fonksiyon + test. Tüm parametreler (N, ceza, öncüller, slot payları, Taze penceresi) yapılandırmadan gelir; her profil/listeye algoritma sürümü yazılır.

## Alınan kararlar (31 Ekim 2026, geliştirici onayı)

1. Unheard havuzu: yalnızca sola kaydırılan/Unheard işaretlenen parçalar.
2. Yayın kaynağı: MusicBrainz birincil. MBID'siz sanatçılar için Last.fm ikincil kaynak olarak **S4 spike'ında denenir**; geliştirici ticari kaygı olmadığı için izin verdi. Koşullar: (a) Last.fm API'sinde yayın tarihi veren bir uç yoktur (`artist.getTopAlbums` tarih döndürmez), yani "yeni çıktı" ancak albüm listesindeki yeni girişten sezilir, bu zayıf bir sinyaldir; spike bunu ölçer, işe yaramazsa MBID'siz sanatçılar kapsam dışı kalır. (b) Last.fm verisi 100 MB sınırı altında ve ham yanıt saklanmadan tutulur. (c) Mağaza yayını/ticari kullanım öncesi Last.fm'in önceden izni gerekir (CLAUDE.md); bu bir borç olarak DURUM.md'de izlenir.
3. Thompson sampling: başlangıçta slotlar yaklaşık eşit; bandit etkisi ≥ N sonuçtan sonra açılır (eşik yapılandırmada).
4. Başarı: sanatçıya liste sonrası verilen herhangi bir parçada Good+ (≥4) oy.
5. Örtük negatif: N=3 sunum, −0,05, sönümlü.

## Karar bekleyen noktalar (kapandı, kayıt için)

1. **Unheard kaynağı.** Öneri: yalnızca kullanıcının sola kaydırdığı/Unheard işaretlediği parçalar havuza girer. Alternatif: kütüphanede hiç oylanmamış tüm parçalar da havuz sayılır (çok geniş, aktif öğrenme kuyruğuyla zaten örtüşür).
2. **Yayın kaynağı ve MBID'siz sanatçılar.** Öneri: MusicBrainz birincil (ListenBrainz ikincil, S4 spike sonucuna göre); yayın tespiti yalnızca MBID'li sanatçılarda çalışır. Ölçüm: ilk örnekte sanatçıların ~%74'ünün MBID'si var, kalan ~%26 takip edilse bile yayın üretmez. Alternatif: MBID'siz sanatçılar için Last.fm'de yayın ucu aramak (Last.fm ikincil ve izin belirsiz, önermiyorum).
3. **Thompson sampling veri azlığı.** Tek kullanıcılı geliştirme verisinde birkaç liste, öğrenmek için yetersiz; öncüller ve taban payları bu yüzden belirleyici olur. Öneri: makul öncül (başlangıçta slotlar yaklaşık eşit, `explore` biraz düşük) ve bandit etkisi yalnızca ≥ N sonuç sonrası açılır (eşik yapılandırmada). Faz 6'da 5 kullanıcıyla ayarlanır.
4. **Başarı tanımı (S3).** Öneri: sanatçıya liste sonrası verilen herhangi bir parça oyu sayılır (öğeler sanatçı düzeyinde olduğundan). Alternatif: yalnızca öğenin `track_id`'si oylanırsa (çok az öğenin parçası var, veri seyrek kalır).
5. **Örtük negatif (S1).** N=3 sunum ve −0,05 ceza öneri değerleri; Awful gibi sönmez, zaman sönümüne tabidir. Onay?
6. **Dışarıya bakış:** Last.fm izni ve Premium durumu bu faza engel değil; Last.fm olmadan grafik zaten Faz 2'de kuruldu.

## Riskler

- MusicBrainz yayın tarihleri bazen eksik/yanlış ve gecikmeli gelir; "bu hafta çıkan" boş kalabilir. S4 spike'ında gerçek takip sanatçılarıyla ölçülür, boşsa pencere genişletilir veya ListenBrainz eklenir.
- Hız sınırı: 1 istek/sn ile ~250 sanatçı ≈ 4–5 dk; haftalık iş olarak kabul edilebilir, önbellekle tekrar çağrı yok.
- Bandit geri bildirim döngüsü: çok erken öğrenirse tek slota yığılır; taban payı ve ≥ N sonuç eşiği bunu sınırlar.
- Örtük negatif, kullanıcının sadece dinlemeye vakit bulamadığı parçaları cezalandırabilir; ceza küçük ve sönümlü tutuldu, `unheard_event` olduğu için geri alınabilir (profil yeniden kurulur).
- Spotify'dan yayın çekilmediği için "Yeni" akışında kapak/başlık Spotify'dan gelmez; kapaklar plan sırasındaki en son UI işine kalır.
- Göç sayısı (0010–0013) yüksek; her biri ayrı aşamada, geri alınabilir.
