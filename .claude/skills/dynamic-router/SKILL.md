---
name: dynamic-router
description: Görev karmaşıklığını hesaplayıp doğru modeli (Haiku, Sonnet, Opus, Gemini) ve Test-Time Compute (Effort) bütçesini seçen karar ağacı.
---
# DİNAMİK ROUTER VE EFOR (TEST-TIME COMPUTE) MATRİSİ

Bir görev geldiğinde şu puanlama algoritmasını uygula:
1. **Dosya Sayısı:** 1-2 dosya = 1 Puan | 3-9 dosya = 2 Puan | 10+ dosya = 5 Puan (Doğrudan `@gemini-scout` çağır!)
2. **Algoritmik Derinlik:** CRUD/Formatlama = 1 Puan | İş Mantığı/API = 2 Puan | Eşzamanlılık (Concurrency)/Mimari/Optimizasyon = 4 Puan

**Yönlendirme Kararı:**
- **Toplam 2 Puan:** Arama/keşif `@explorer-haiku` (`effort: low`, salt-okunur); 1-2 satırlık düzeltme/format ana modelde doğrudan. Düşünme bütçesi harcama, anında çöz.
- **Toplam 3-4 Puan:** Ana Model `Sonnet` (`effort: medium`) — Standart cerrahi uygulama.
- **Toplam 5+ Puan:** Önce `@gemini-scout` ile `SPEC.md` çıkar (algoritmik derinlik 4 ise önce `@architect-planner` ile uç durum planı) -> Ardından `Sonnet/Opus` (`effort: high` / `ultrathink`) ile derin düşünerek kodla -> Son olarak `@tester-healer` ve `@reviewer-guard` ile doğrula.

## EFOR OTOMASYONU (alt ajan `effort` parametresi)
Bu bölüm, Agent aracında `effort` vermeme açık izin verir. Ajan dosyasındaki `effort:` taban değerdir; aşağıdaki mod ve tabloya göre yukarı/aşağı ezilebilir.

**Mod seçimi** (`.aegis/MODE` dosyası; yoksa `auto`; kullanıcı "tam otomatik" / "normal" diyerek değiştirir):
- `normal` (manuel): Ajan dosyasındaki taban eforu kullan; `effort` parametresi verme. Seviye 4 ve model değişimini kullanıcıya öner.
- `auto` (varsayılan): Her alt ajan çağrısında aşağıdaki tabloya göre `effort` ver; ayrıca puanlamayı kendin yap, sormadan ilgili ajan zincirini (planner → implementer → test-runner → reviewer-guard) çalıştır. Yıkıcı/dış etkili eylemler (commit, push, silme) yine onay ister.

**Efor tablosu** (auto modda):
| Görev | Ajan | effort |
|---|---|---|
| Arama, format, test koşumu | explorer-haiku, aegis-test-runner | low |
| Standart özellik, refactor, birim test, log süzme | implementer-sonnet, tester-healer, gemini-scout | medium |
| Yarış durumu, güvenlik diff'i, derin mimari, uç durum planı | architect-planner, reviewer-guard | high |

Kural: toplam puan ≥5 veya güvenlik/eşzamanlılık içeriyorsa bir kademe yukarı (en fazla `high`); tek dosyalık basit işte bir kademe aşağı. Ana oturumun eforu/modeli değişmez (önbellek).

## İSTEĞE BAĞLI EKLENTİLER (gerekirse aç)
`clangd-lsp` ve `context7` yüklü ama `enabledPlugins`'te `false` (token tasarrufu). Eklentiler oturum başında yüklenir; oturum içinde açılamaz. `auto` modda kendin karar ver, sormadan uygula:
- **context7:** Görev güncel kütüphane/API dokümanı gerektiriyorsa (sürüme özgü davranış, bilinmeyen API) işi durdurma; şimdilik WebSearch/web-fetch ile ilerle, `settings.json`'da `context7`'yi `true` yap ve kullanıcıya tek satırla bildir: yeni oturumda geçerli, `/mcp` yetkilendirmesi gerekir.
- **clangd-lsp:** Projede C/C++ varsa (session-start notu) aynı şekilde `true` yap ve bildir.
- Başka bir eklenti için yapma; yalnızca bu ikisi. `normal` modda açmadan önce kullanıcıya sor.
