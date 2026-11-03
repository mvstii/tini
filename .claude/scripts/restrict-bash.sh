#!/usr/bin/env bash
# Ajan kapsamlı PreToolUse kancası: Bash'i yalnızca salt-okunur komutlara izin verir (reviewer-guard için).
# İzinli: git (diff|log|show|status|blame|rev-parse|ls-files), grep, rg, cat, ls, head, tail, wc;
# boru (|) yalnızca head|tail|grep|wc|sort|uniq|cut ile. Yönlendirme, zincirleme (; && ||), komut
# ikamesi ve sed -i / tee reddedilir. Sezgiseldir; kesin güvenlik sınırı değil, kazara yazmayı önler.
INPUT=$(cat 2>/dev/null)
command -v jq > /dev/null 2>&1 || exit 0
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[ -n "$CMD" ] || exit 0

deny() {
  echo "🚫 [AJAN KISITI]: Bu ajan yalnızca salt-okunur komut çalıştırabilir ($1). Reddedilen: ${CMD:0:80}" >&2
  exit 2
}

case "$CMD" in
  *';'*|*'&'*|*$'\n'*|*$'\r'*|*'||'*|*'>'*|*'<'*|*'`'*|*'$('*) deny "yönlendirme/zincirleme/komut ikamesi yok" ;;
esac
printf '%s' "$CMD" | grep -qE '(^|[[:space:]])(--output|--pre|--ext-diff|--textconv)([=[:space:]]|$)' && deny "yazma/çalıştırma bayrağı"
printf '%s' "$CMD" | grep -qE '(^|[[:space:]])(tee|sed[[:space:]]+-i|rm|mv|cp|chmod|dd)([[:space:]]|$)' && deny "yazıcı komut"

# Ek argümanlar (örn. agy gemini.cmd) ilk komut olarak da izinlenir (gemini-scout köprü CLI'ları).
EXTRA=""
for c in "$@"; do EXTRA="$EXTRA|$(printf '%s' "$c" | tr -cd 'A-Za-z0-9_.-' | sed 's/\./[.]/g')"; done
FIRST_OK="^[[:space:]]*(git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+(diff|log|show|status|blame|rev-parse|ls-files)|grep|rg|cat|ls|head|tail|wc${EXTRA})([[:space:]]|\$)"
PIPE_OK='^[[:space:]]*(head|tail|grep|wc|uniq|cut)([[:space:]]|$)'
FIRST=${CMD%%|*}
printf '%s' "$FIRST" | grep -qE "$FIRST_OK" || deny "izinli komut listesi dışı"
REST=${CMD#"$FIRST"}
while [ -n "$REST" ]; do
  REST=${REST#|}
  SEG=${REST%%|*}
  printf '%s' "$SEG" | grep -qE "$PIPE_OK" || deny "boru yalnızca head/tail/grep/wc/uniq/cut"
  NEXT=${REST#"$SEG"}
  [ "$NEXT" = "$REST" ] && break
  REST=$NEXT
done
exit 0
