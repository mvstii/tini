#!/usr/bin/env bash
# Başlangıç bağlam yükü ölçümü: oturumda otomatik/standart okunan dosyaların tahmini token boyutu.
# Tahmin: karakter / 3,3 (Türkçe için kaba). Eşik: AEGIS_MAX_STARTUP_TOKENS (varsayılan 1500) dosya başına.
# Kullanım: bash .claude/scripts/measure-tokens.sh   (aşılırsa çıkış kodu 1, yoksa 0)
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LIM=${AEGIS_MAX_STARTUP_TOKENS:-1500}
st=0
printf '%-34s %8s %10s  %s\n' dosya karakter ~token durum
est() { echo $(( $1 * 10 / 33 )); }
for f in CLAUDE.md MEMORY.md SPEC.md; do
  p="$ROOT/$f"; [ -f "$p" ] || continue
  c=$(wc -m < "$p" | tr -d ' '); t=$(est "$c")
  if [ "$t" -gt "$LIM" ]; then d="UYARI: >$LIM (arşivle/kısalt)"; st=1; else d="ok"; fi
  printf '%-34s %8s %10s  %s\n' "$f" "$c" "$t" "$d"
done
# Ajan/skill açıklamaları her oturumda bağlama girer (yalnızca description satırı).
c=0
for f in "$ROOT"/.claude/agents/*.md "$ROOT"/.claude/skills/*/SKILL.md; do
  [ -f "$f" ] || continue
  n=$(sed -n 's/^description: //p' "$f" | head -n 1 | wc -m); c=$((c + n))
done
printf '%-34s %8s %10s  %s\n' "ajan+skill açıklamaları" "$c" "$(est "$c")" "(her oturumda yüklenir)"
[ $st -ne 0 ] && echo "Öneri: uzun kayıtları docs/ARSIV.md'ye taşı; MEMORY.md yalnızca kalıcı kuralları tutsun."
exit $st
