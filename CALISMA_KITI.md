# CALISMA_KITI.md — Günlük Başvuru

`CLAUDE.md` anayasa, bu dosya hızlı başvuru. Çelişkide `CLAUDE.md` geçerlidir.

## Oturum açılışı
1. Klasörde yeni oturum aç (PATH güncel olsun: `bash`, `git`, `dotnet`, `gh`).
2. `MEMORY.md` ve varsa `SPEC.md` oku.
3. `git status` ile temiz olduğunu doğrula.

## Router tablosu
| Seviye | İş türü | Kime |
|---|---|---|
| 1 | Arama, keşif, basit düzeltme | `@explorer-haiku` (haiku, low) |
| 2 | >10 dosya, büyük log, UI analizi | `@gemini-scout` (`agy -p`) → çıktı `SPEC.md` |
| 3 | Standart özellik, refactor, birim test | `@implementer-sonnet` (medium) |
| 4 | Karmaşık algoritma, race condition, derin tasarım | `/seviye4 <görev>` (high efor, önce architect-planner) |

## Standart akış
1. Görevi sınıflandır.
2. Gerekirse keşif/tarama yaptır, hedefleri `SPEC.md`'ye yaz.
3. Yalnızca hedef satırları düzenle (önce `Grep`, sonra 30-50 satır `Read`).
4. Derleme/test hatasını `PostToolUse` kancasından al, sormadan düzelt.
5. Testleri `@tester-healer`, denetimi `@reviewer-guard` yapsın.
6. Kalıcı kararları `MEMORY.md`'ye yaz.

## Commit kuralları
- Küçük, tek amaçlı commit; mesaj `tip(kapsam): açıklama` biçiminde (ör. `docs(plan): ...`).
- Commit mesajı sonunda ortamın istediği ortak yazar satırı eklenir.
- Push yalnızca kullanıcı istediğinde; `--force` yasak.
- Gizli dosyalar commit edilmez (`.gitignore` korur).

## Bağlam hijyeni
- Ham log ve geniş aramalar alt ajana gider.
- Doluluk %60 → `MEMORY.md` güncelle; iş bittiyse `/clear` (bedava), sürüyorsa `/compact` öner. Oturum başında SessionStart kancası devir notu verir.

## Sızıntı taraması
- `.githooks/pre-commit` her commit'te staged değişiklikleri `gitleaks` ile tarar; bulguda commit durur.
- Yeni klonda etkinleştirme: `kurulum.ps1` çalıştırın (veya `git config core.hooksPath .githooks`).
- Yanlış alarm: ilgili parmak izini `.gitleaksignore` dosyasına ekleyin.

## Yeni projeye kurulum (arkadaşlar için)
1. Bu depoyu klonla.
2. `powershell -ExecutionPolicy Bypass -File .\yeni-proje.ps1 -Hedef C:\dev\benim-projem -Kurulum` (`-Extra` ek CLI'lar, `-DotnetCi` .NET CI, `-Force` üzerine yazma).
3. Hedefte `powershell -ExecutionPolicy Bypass -File .\giris-yardimcisi.ps1` (gh, agy, codex girişi; `-KontrolEt` yalnızca durum). Şifre sormaz.
4. `claude` ile başla. Dile göre uyar: `post-edit-eval.sh` .NET, TypeScript, Python (söz dizimi), Go ve Rust algılar; diğer diller için uyarlayın.

## SPEC.md kapsam kilidi (opt-in)
- SPEC.md'ye tek başına bir satır olarak `<!-- scope-lock: on -->` ekle: Edit/Write yalnızca SPEC.md'de geçen dosyalara izin verir (CLAUDE.md, MEMORY.md, SPEC.md serbest). Satırı silince kilit kalkar.
- SPEC.md yazılınca `yol:satır` biçimindeki yollar diskte doğrulanır; olmayan yol exit 2 ile bildirilir.

## Arayüz/tasarım işleri
- Ekran görüntüsü, büyük CSS/XAML ağacı ve "mevcut token/bileşen envanteri" taraması `@gemini-scout`'ta; sonuç SPEC.md'ye yazılır.
- Kod yazarken `.claude/skills/ui-design-efficiency/SKILL.md`: hardcoded renk/boyut yok, mevcut token/bileşeni kullan, yalnızca ilgili stil bloğunu düzenle.

## Ajan notları
- Ajan tanımını değiştirdikten sonra yeni oturumda dene; aynı oturumdaki ajanlar eski tanımla çalışabilir.
- `explorer-haiku` salt-okunurdur; 1-2 satırlık düzeltme ana modelde yapılır.
- Paralel backend + UI için Agent çağrısında `isolation: "worktree"` (SPEC'i istem içine göm; worktree varsayılan daldan açılır). Ayrıntı: `git-worktree` skill'i.
- `/compact` öncesi durum `.claude/logs/precompact.log` dosyasına yazılır.

## Maliyet sigortası ve günlükler
- **Maliyet sigortası** (`circuit-breaker.sh`): 10 dakikada aynı işlem 3 kez başarısız olursa uyarır, 6'da (veya toplam 12 hatada) sigortayı açar: Claude'un sonraki Bash/Edit/Write çağrıları reddedilir ve sizi beklemesi söylenir. Yeni bir mesaj yazdığınızda sıfırlanır. Hiçbir şeyi geri almaz; nedeni bulup yönergeyi değiştirerek devam edin. Kapatmak: `AEGIS_CB=off`; eşikler: `AEGIS_CB_WARN`, `AEGIS_CB_STOP`, `AEGIS_CB_TOTAL`, `AEGIS_CB_WINDOW`.
- **Token günlüğü:** `.claude/logs/usage.log` (tarih | etiket | oturum | giriş | çıkış | önbellek-okuma | önbellek-yazma | mesaj). Etiket `oturum` veya `ajan:<ad>`. Kapatmak: `AEGIS_USAGE=off`.
- **Devir notu:** `/compact` öncesi ayrıntı `.claude/logs/precompact.log`'a yazılır; oturum başında/`/clear`/sıkıştırma sonrası `session-start.sh` dal, değişen dosya sayısı ve SPEC hedefini bağlama ekler (`AEGIS_SESSION_NOTE=off` kapatır). MEMORY.md'ye otomatik yazılmaz.
- **Assertion koruması:** `tester-healer` bitirirken `assert-guard.sh` test diff'ine bakar; silinen assertion veya eklenen Skip varsa ajanı geri gönderir (`AEGIS_ASSERT_GUARD=off`).
- **Guard engellerse:** dur ve kullanıcıya bildir; başka araçla aşma. Kanca değişikliğinden sonra `bash .claude/scripts/test-guards.sh`.
- **Token raporu:** `session-report` plugin'i ("son 7 günün token raporunu çıkar").
- **Seviye 4:** zor işlerde önce `@architect-planner` (salt planlayıcı, yalnızca SPEC.md yazar).
- **Güvenlik denetimi:** `/security-audit <klasör>` (Cloudflare skill'i). Varsayılan `quick` profil ve en fazla 8 alt ajan (Sonnet); `standard`/`deep` önce sorulur. Hedef kod çalıştırılmaz (Windows'ta sandbox yok), çalıştırma isteyen bulgular `needs_validation` kalır. Rapor `.guvenlik-denetimi/run-<N>/` (git dışı). Tüm repoyu taramak kotanın büyük kısmını yiyebilir; sürüm öncesi, dış girdi alan modüllerde kullanın.

## Token disiplini (ölçülmüş kurallar)
- **Uzun oturumda bağlamı sıkıştır:** `settings.json` içindeki `autoCompactWindow: 200000` bağlamı ~170k'da kendiliğinden sıkıştırır (canlı doğrulandı: 170k → ~14k). Ölçülen tasarruf **mütevazı**: canlı testte %9 (cache okuması 4,6x azaldı ama maliyet çoğunlukla YENİ içeriğin önbelleğe yazılmasından gelir), gerçek oturum simülasyonunda %11-16. 100k'ya düşürmek zararlı (+%17). Asıl kaldıraç bağlama giren yeni içeriği azaltmaktır.
- **Kısa işte alt ajan başlatma:** ajan başlatmak ~15k token sabit yük; 250 satırlık üretimi devretmek ölçümde %70+ pahalıya geldi. Uzun oturumda (~40+ tur) büyük dosya üretimini `@implementer-sonnet`'e devredin; kanca bu durumda uyarır (`AEGIS_BIG_CONTENT`, `AEGIS_LONG_TURNS`).
- Görselleri `Read` ile açmayın (`agy`'ye yaptırın), komut çıktısını daraltın, aynı dosyayı tekrar okumayın.
- Ölçüm: `.claude/logs/usage.log` (oturum/ajan token toplamı).

## Başlangıç yükü ve Read koruması
- `bash .claude/scripts/measure-tokens.sh`: CLAUDE.md, MEMORY.md, SPEC.md ve ajan/skill açıklamalarının tahmini token boyutunu gösterir; dosya başına 1.500 token aşılırsa uyarır (`AEGIS_MAX_STARTUP_TOKENS`).
- `MEMORY.md` kısa tutulur (~1k token); tarihçe `docs/ARSIV.md`'dedir, gerekirse `grep -n` ile ara. MEMORY okuma görevinde maliyet %32-35 düştü (ölçüldü).
- `pre-tool-read-guard.sh`: kilit dosyaları, `bin/`, `obj/`, `node_modules/`, `*.Designer.cs` ve 500+ satırlık limitsiz `Read` reddedilir; çözüm `Grep` + `offset/limit`. Kapatmak: `AEGIS_READ_GUARD=off`. Ölçümde model zaten `Grep` kullandığı için etkisi görülmedi; sigorta niteliğindedir.
