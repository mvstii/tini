#!/usr/bin/env bash
# Token kullanım günlüğü (SessionEnd + SubagentStop): ajan/oturum bazında toplam tokenı
# .claude/logs/usage.log dosyasına ekler (gitignore'da). Bağlama bir şey yazmaz; her zaman exit 0.
# Satır: tarih | etiket | session | giriş | çıkış | önbellek-okuma | önbellek-yazma | mesaj
# jq yoksa sessizce atlar. AEGIS_USAGE=off kapatır.
[ "${AEGIS_USAGE:-on}" = "off" ] && exit 0
command -v jq > /dev/null 2>&1 || exit 0
INPUT=$(cat 2>/dev/null)
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"

EVENT=$(printf '%s' "$INPUT" | jq -r '.hook_event_name // ""' 2>/dev/null)
SID=$(printf '%s' "$INPUT" | jq -r '.session_id // "-"' 2>/dev/null)
if [ "$EVENT" = "SubagentStop" ]; then
  LABEL="ajan:$(printf '%s' "$INPUT" | jq -r '.agent_type // "?"' 2>/dev/null)"
  T=$(printf '%s' "$INPUT" | jq -r '.agent_transcript_path // empty' 2>/dev/null)
else
  LABEL="oturum"
  T=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
fi
T=$(printf '%s' "$T" | tr '\\' '/')
[ -n "$T" ] && [ -f "$T" ] || exit 0

# Aynı mesaj kimliği birden çok satırda tekrarlanır: kimlik başına son kaydı al, topla.
SUM=$(jq -s -r '[.[] | select(.type == "assistant" and .message.usage != null) | {id: .message.id, u: .message.usage}]
  | group_by(.id) | map(last)
  | [(map(.u.input_tokens // 0) | add // 0), (map(.u.output_tokens // 0) | add // 0),
     (map(.u.cache_read_input_tokens // 0) | add // 0), (map(.u.cache_creation_input_tokens // 0) | add // 0), length]
  | join("|")' "$T" 2>/dev/null)
[ -n "$SUM" ] || exit 0

mkdir -p "$ROOT/.claude/logs" 2>/dev/null
printf '%s|%s|%s|%s\n' "$(date '+%F %T')" "$LABEL" "$SID" "$SUM" >> "$ROOT/.claude/logs/usage.log" 2>/dev/null
exit 0
