#!/usr/bin/env bash
# SessionStart (startup|clear|compact|resume): bağlama 3-5 satırlık devir notu ekler.
# Amaç: /clear'ı ucuz ve güvenli bir görev sınırı yapmak; MEMORY.md'ye otomatik yazmadan bağlamı taşımak.
# İçerik: dal, değişen dosya sayısı, SPEC.md "## Hedef" satırı, açık maliyet sigortası. Her koşulda exit 0.
# Kapatmak: AEGIS_SESSION_NOTE=off.
[ "${AEGIS_SESSION_NOTE:-on}" = "off" ] && exit 0
INPUT=$(cat 2>/dev/null)
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"

BR=$(git -C "$ROOT" branch --show-current 2>/dev/null)
N=$(git -C "$ROOT" status --short 2>/dev/null | wc -l | tr -d ' ')
SPECT=""
[ -f "$ROOT/SPEC.md" ] && SPECT=$(awk '/^## Hedef/{f=1;next} f&&NF{print;exit}' "$ROOT/SPEC.md" | sed 's/^- *//' | cut -c1-120)
case "$SPECT" in ""|"(boş)") SPECT="aktif SPEC yok" ;; esac

NOTE="[aegis devir notu] dal: ${BR:-?} · değişen dosya: ${N:-0} · SPEC hedefi: $SPECT"
# .aegis/STATE.md (/aegis-handoff çıktısı): yalnızca varlığını ve açık iş sayısını bildir, içeriği okutma.
if [ -f "$ROOT/.aegis/STATE.md" ]; then
  OPEN=$(awk '/^## Açık işler/{f=1;next} /^## /{f=0} f&&NF' "$ROOT/.aegis/STATE.md" | wc -l | tr -d ' ')
  NOTE="$NOTE"$'\n'"Devir: .aegis/STATE.md var (açık iş: ${OPEN:-0}); görev ilgiliyse oku."
fi
MODE=$(tr -d '[:space:]' < "$ROOT/.aegis/MODE" 2>/dev/null)
case "$MODE" in normal|auto) ;; *) MODE=auto ;; esac
NOTE="$NOTE"$'\n'"Efor modu: $MODE (varsayılan auto)."
SRC=$(printf '%s' "$INPUT" | jq -r '.source // empty' 2>/dev/null | tr -d '\r\n')
case "$SRC" in
  startup|clear) NOTE="$NOTE"$'\n'"Oturumun ilk yanıtında kullanıcıya tek satırla sor: efor modu otomatik (auto) mı, manuel (normal) mı kalsın? Cevap gelene kadar $MODE ile ilerle; cevaba göre .aegis/MODE dosyasına auto veya normal yaz." ;;
esac
# İsteğe bağlı LSP: kapalı clangd-lsp, projede C/C++ varsa kullanıcıya bildirilir (değişiklik yeni oturumda geçerli).
if [ "$(jq -r '.enabledPlugins["clangd-lsp@claude-plugins-official"] // empty' "$ROOT/.claude/settings.json" 2>/dev/null)" = "false" ] \
  && [ -n "$(find "$ROOT" -maxdepth 3 \( -name .git -o -name node_modules \) -prune -o -type f \( -name '*.c' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) -print -quit 2>/dev/null)" ]; then
  NOTE="$NOTE"$'\n'"Projede C/C++ var ama clangd-lsp kapalı: gerekirse kullanıcıya settings.json'da enabledPlugins içinde true yapmasını öner (yeni oturumda geçerli)."
fi
if command -v jq > /dev/null 2>&1; then
  SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null | tr -d '\r\n' | tr -c 'A-Za-z0-9_-' '_')
  if [ -n "$SID" ] && [ -f "$ROOT/.claude/logs/circuit/TRIPPED.$SID" ]; then
    NOTE="$NOTE"$'\n'"Maliyet sigortası açık: son işlem döngüye girmişti; kullanıcıya durumu bildir."
  fi
  NOTE="$NOTE"$'\n'"Kalıcı kararları MEMORY.md'ye yaz; aktif görev SPEC.md'de."
  jq -n --arg m "$NOTE" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $m}}'
else
  printf '%s\n' "$NOTE"
fi
exit 0
