---
paths:
  - "**/*.sh"
  - ".githooks/**"
---
# Kanca/bash betiği kuralları
- Değiştirdikten sonra `shellcheck -S warning <dosya>` çalıştır; yalnızca gerçek hataları düzelt.
- Satır sonu LF olmalı (`git ls-files --eol`); CRLF bash kancalarını bozar.
- Kanca değişikliğinden sonra `bash .claude/scripts/test-guards.sh` (CI de çalıştırır).
- Varlık testi için `ls a b` değil `compgen -G` / `find` kullan.
