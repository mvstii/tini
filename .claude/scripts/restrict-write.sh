#!/usr/bin/env bash
# Ajan kapsamlı PreToolUse kancası: Edit/Write yalnızca argümanda verilen dosya adlarına izin verir.
# Kullanım (ajan frontmatter'ında): bash "$CLAUDE_PROJECT_DIR/.claude/scripts/restrict-write.sh" SPEC.md
# Örn. gemini-scout -> SPEC.md, reviewer-guard -> MEMORY.md. İzin dışı dosya: exit 2.
INPUT=$(cat 2>/dev/null)

FILE=""
if command -v jq > /dev/null 2>&1; then
  FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null)
fi
if [ -z "$FILE" ]; then
  FILE=$(printf '%s' "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed 's/.*:[[:space:]]*"\(.*\)"/\1/')
fi
# Dosya yolu yoksa (ör. başka araç) karışma.
[ -z "$FILE" ] && exit 0

# Windows yollarını / biçimine çevir, son bileşeni al, harf büyüklüğünü yok say.
BASE=$(printf '%s' "$FILE" | tr '\\' '/' | sed 's#//*#/#g')
BASE=${BASE##*/}
for ok in "$@"; do
  [ "${BASE,,}" = "${ok,,}" ] && exit 0
done

echo "🚫 [AJAN KISITI]: Bu ajan yalnızca şu dosyalara yazabilir: $*. Reddedilen: $BASE" >&2
exit 2
