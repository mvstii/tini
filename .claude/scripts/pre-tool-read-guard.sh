#!/usr/bin/env bash
# Read koruması (PreToolUse, matcher: Read): gereksiz/dev dosyaların bağlama tamamen girmesini engeller.
#  - Kilit dosyaları ve derleme/bağımlılık çıktıları (lock, bin/, obj/, node_modules/, *.Designer.cs): reddedilir.
#  - Metin dosyası AEGIS_READ_MAX_LINES (500) satırdan uzunsa ve offset/limit verilmemişse: reddedilir.
# Kapatmak: AEGIS_READ_GUARD=off. jq yoksa veya dosya okunamıyorsa sessizce izin verir.
[ "${AEGIS_READ_GUARD:-on}" = "off" ] && exit 0
command -v jq > /dev/null 2>&1 || exit 0
INPUT=$(cat 2>/dev/null)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null | tr '\\' '/')
[ -n "$FILE" ] || exit 0
MAXL=${AEGIS_READ_MAX_LINES:-500}

deny() {
  echo "TOKEN GUARD: $1 Grep veya ast-grep ile ilgili satır aralığını bul, sonra Read'i offset/limit ile kullan. (Kapatmak: AEGIS_READ_GUARD=off)" >&2
  exit 2
}

BASE=${FILE##*/}
case "$FILE" in
  */node_modules/*|*/bin/*|*/obj/*|node_modules/*|bin/*|obj/*) deny "Bu klasör derleme/bağımlılık çıktısıdır, gereksiz token yakar." ;;
esac
case "${BASE,,}" in
  *.lock|package-lock.json|pnpm-lock.yaml|*.designer.cs|*.min.js|*.min.css)
    deny "Bu dosya üretilmiş/kilit dosyasıdır ve çok büyüktür." ;;
  *.png|*.jpg|*.jpeg|*.gif|*.webp|*.pdf|*.ipynb|*.svg) exit 0 ;;
esac

# offset veya limit verilmişse hedefli okumadır, izin ver.
if printf '%s' "$INPUT" | jq -e '(.tool_input.offset // .tool_input.limit // null) != null' > /dev/null 2>&1; then exit 0; fi

[ -f "$FILE" ] || exit 0
grep -Iq . "$FILE" 2> /dev/null || exit 0   # ikili dosya: bu koruma ilgilenmez
LINES=$(wc -l < "$FILE" 2> /dev/null | tr -d ' ')
[ "${LINES:-0}" -gt "$MAXL" ] && deny "'$BASE' $LINES satır (>$MAXL); tamamını okumak çok token harcar."
exit 0
