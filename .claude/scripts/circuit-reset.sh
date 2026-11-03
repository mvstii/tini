#!/usr/bin/env bash
# UserPromptSubmit: kullanıcı yeni mesaj yazınca maliyet sigortasını sıfırlar (işaretçi + sayaç silinir).
# Kullanıcı müdahalesi = döngü kırıldı. Her koşulda exit 0.
command -v jq > /dev/null 2>&1 || exit 0
INPUT=$(cat 2>/dev/null)
SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null | tr -d '\r\n' | tr -c 'A-Za-z0-9_-' '_')
[ -n "$SID" ] || exit 0
DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}/.claude/logs/circuit"
rm -f "$DIR/TRIPPED.$SID" "$DIR/$SID.log" 2>/dev/null
exit 0
