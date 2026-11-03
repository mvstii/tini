#!/usr/bin/env bash
# PreCompact: /compact (elle, otomatik veya boşta) öncesi görev durumunu günlüğe yazar. Her koşulda exit 0.
# .claude/logs/precompact.log: dal, git durumu, SPEC.md başı; log gitignore'dadır.
# MEMORY.md'ye artık yazmaz (sürüm kontrollü dosyada gürültü yapıyordu). Sıkıştırma sonrası bağlam
# session-start.sh tarafından SessionStart (compact) olayında kısa devir notu olarak verilir.
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG="$ROOT/.claude/logs/precompact.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || exit 0
BR=$(git -C "$ROOT" branch --show-current 2>/dev/null)
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') PreCompact ==="
  echo "dal: $BR"
  git -C "$ROOT" status --short 2>/dev/null | head -n 20
  if [ -f "$ROOT/SPEC.md" ]; then
    echo "--- SPEC.md (ilk 20 satır) ---"
    head -n 20 "$ROOT/SPEC.md"
  fi
  echo
} >> "$LOG" 2>/dev/null
exit 0
