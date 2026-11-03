#!/usr/bin/env bash
# Maliyet sigortası (PostToolUseFailure): hata döngüsünde bütçe yakmayı durdurur.
# Aynı araç+girdi kısa sürede tekrar tekrar başarısız olursa önce uyarır, eşikte oturumu durdurur
# ({"continue":false}); kullanıcı yeni mesajla devam edebilir. Geri alma/silme YAPMAZ.
# Ayar (ortam değişkeni): AEGIS_CB=off kapatır; AEGIS_CB_WINDOW (sn, 600), AEGIS_CB_WARN (3),
# AEGIS_CB_STOP (6, aynı imza), AEGIS_CB_TOTAL (12, toplam hata). jq yoksa sessizce atlar.
[ "${AEGIS_CB:-on}" = "off" ] && exit 0
command -v jq > /dev/null 2>&1 || exit 0
INPUT=$(cat 2>/dev/null)
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
WINDOW=${AEGIS_CB_WINDOW:-600}; WARN=${AEGIS_CB_WARN:-3}; STOP=${AEGIS_CB_STOP:-6}; TOTAL=${AEGIS_CB_TOTAL:-12}

SID=$(printf '%s' "$INPUT" | jq -r '.session_id // "oturum"' 2>/dev/null | tr -d '\r\n' | tr -c 'A-Za-z0-9_-' '_')
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
KEY=$(printf '%s' "$INPUT" | jq -r '(.tool_input.command // .tool_input.file_path // .tool_input.pattern // .tool_input.prompt // "")' 2>/dev/null \
      | tr '\n|' '  ' | cut -c1-80)
SIG="$TOOL:$KEY"

DIR="$ROOT/.claude/logs/circuit"
mkdir -p "$DIR" 2>/dev/null || exit 0
F="$DIR/$SID.log"
NOW=$(date +%s)
touch "$F" 2>/dev/null || exit 0
# Pencere dışındaki kayıtları at, yenisini ekle.
awk -F'|' -v n="$NOW" -v w="$WINDOW" '$1 >= n - w' "$F" > "$F.tmp" 2>/dev/null && mv "$F.tmp" "$F"
printf '%s|%s\n' "$NOW" "$SIG" >> "$F"

N_TOTAL=$(wc -l < "$F" | tr -d ' ')
N_SAME=$(cut -d'|' -f2- "$F" | grep -cxF -- "$SIG")

if [ "$N_SAME" -ge "$STOP" ] || [ "$N_TOTAL" -ge "$TOTAL" ]; then
  MSG="Maliyet sigortası: $WINDOW sn içinde aynı işlem $N_SAME kez, toplam $N_TOTAL hata. Döngü durduruldu; hiçbir şey geri alınmadı. Nedeni inceleyin (ör. git status, son hata) ve yönergeyi değiştirerek devam edin."
  echo "$(date '+%F %T') DURDUR $SIG same=$N_SAME total=$N_TOTAL" >> "$ROOT/.claude/logs/circuit.log" 2>/dev/null
  : > "$F"
  # PostToolUseFailure'da continue:false turu kesmeyebilir; bu yüzden işaretçi bırakılır: pre-tool-guard.sh
  # işaretçi varken Bash/Edit/Write'ı reddeder, kullanıcının yeni mesajı (circuit-reset.sh) işaretçiyi siler.
  printf '%s\n' "$MSG" > "$DIR/TRIPPED.$SID" 2>/dev/null
  jq -n --arg m "$MSG" '{continue: false, stopReason: $m, decision: "block", reason: $m}'
  exit 0
fi
if [ "$N_SAME" -ge "$WARN" ]; then
  MSG="Uyarı (maliyet sigortası): aynı işlem $N_SAME kez başarısız oldu. Aynı komutu tekrar deneme; kök nedeni bul veya farklı bir yaklaşım seç. $STOP. başarısızlıkta oturum durdurulur."
  echo "$(date '+%F %T') UYARI $SIG same=$N_SAME total=$N_TOTAL" >> "$ROOT/.claude/logs/circuit.log" 2>/dev/null
  jq -n --arg m "$MSG" '{hookSpecificOutput: {hookEventName: "PostToolUseFailure", additionalContext: $m}}'
fi
exit 0
