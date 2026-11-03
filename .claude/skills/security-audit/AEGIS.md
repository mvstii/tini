# Aegis yerel kuralları (security-audit)

Bu dosyayı SKILL.md'den önce oku. SKILL.md veya ek dosyalarıyla çelişirse bu dosya geçerlidir.
Buradaki seçimleri (çıktı klasörü, profil, bütçe) kullanıcı Aegis kurulumunda yaptı.

## Ne zaman ve neyi tarar
- Yalnızca kullanıcı `/security-audit` yazınca çalışır. Argüman kapsamdır: yol(lar), alt sistem veya `<ref>..<ref>` diff.
- Argüman yoksa tek soru sor: "Hangi klasör veya modül?" Tüm repoyu yalnızca kullanıcı açıkça "tüm repo" derse tara.
- Argüman bir soruysa (ör. "bu token kontrolü güvenli mi?") rehberlik modunda kal, dosya yazma.

## Profil ve bütçe (kota korunur)
- Varsayılan profil `quick`. `standard` veya `deep` için önce kullanıcıya sor ve tahmini alt ajan sayısını söyle.
- Alt ajan bütçesi (eleştirmen ve doğrulayıcı dahil): quick en fazla 8, standard 20, deep 40 çağrı.
  Bütçe biterse kalan birimleri `deferred` bırak; raporda kapsamın kısmi olduğunu yaz.
- Her alt ajan çağrısında `model: "sonnet"` ver. `research` ajanı = `Explore`, `general` ajanı = `general-purpose`.
  Ana oturumun modelini değiştirme (önbellek sıfırlanır).
- Alt ajana dosyanın tamamını değil birimin kapsamını ver; Aegis okuma kuralı geçerli (önce Grep, sonra offset/limit).

## Hedef kod çalıştırılmaz (Windows)
- Bu makinede SKILL.md'nin istediği işletim sistemi düzeyi sandbox yok. Hedef kodu, testleri, derlemeyi
  veya betikleri ÇALIŞTIRMA. Çalıştırma gerektiren her aday `needs_validation` kalır; `validation_plan`
  alanına kullanıcının elle yapabileceği güvenli adımları yaz.
- Ağ erişimi, bağımlılık kurma ve canlı sisteme dokunma yok (SKILL.md ile aynı).

## Çıktı klasörü
- `.guvenlik-denetimi/run-<N>/` (proje kökü). Yazmadan önce `git check-ignore -q .guvenlik-denetimi/x`
  çalıştır; 0 dönmezse dur ve kullanıcıya bildir.
- Ortak dosyaları yalnızca ana oturum yazar; alt ajan klasörleri `agents/<id>/` altındadır.

## Gizli bilgiler ve kancalar
- Aegis kancaları gizli dosyaları okumayı ve anahtar ataması içeren yazımı engeller. Engellenirse aşmaya
  çalışma (CLAUDE.md guard kuralı): birimi `blocked` işaretle, nedenini yaz.
- Bulgu ve raporlarda gizli değeri yazma: `dosya:satır` ve değerin ilk 4 karakteri + `…` yeter.

## Doğrulayıcılar
- Git Bash'te, ileri eğik çizgili göreli yolla çalıştır:
  - `node .claude/skills/security-audit/validate-findings.cjs .guvenlik-denetimi/run-<N>/findings.json`
  - `node .claude/skills/security-audit/validate-coverage-ledger.cjs .guvenlik-denetimi/run-<N>/coverage-ledger.json`
- Windows'ta girdi okunamazsa (upstream issue #53) raporda "doğrulayıcı çalışmadı" yaz; sonucu doğrulanmış sayma.

## Bitiş
- Kodu düzeltme. Sohbete en fazla 15 satırlık özet ver: Kritik/Yüksek bulgular (`dosya:satır`, 1 cümle),
  kapsamın kısmi olup olmadığı, rapor klasörü.
- `confirmed` Kritik veya Yüksek bulgu varsa `MEMORY.md` dosyasına en fazla 1 satır ekle:
  `<tarih> security-audit <kapsam>: N doğrulanmış bulgu, rapor .guvenlik-denetimi/run-<N>`.
- Düzeltmeler normal akışla yapılır: SPEC.md hedefi ve `superpowers-tdd` ile önce başarısız test.
