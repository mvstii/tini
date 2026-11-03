#!/usr/bin/env bash
# tester-healer için Stop (SubagentStop) kancası: test dosyalarında assertion silme/zayıflatma ve
# Skip/Ignore eklemeyi deterministik olarak yakalar (önceden yalnızca istem kuralıydı).
# HEAD'e göre çalışma ağacı farkına bakar; bulgu varsa {"decision":"block"} ile ajanı geri gönderir.
# Döngü koruması: stop_hook_active=true ise karışmaz. git/jq yoksa sessizce geçer. Kapatmak: AEGIS_ASSERT_GUARD=off.
[ "${AEGIS_ASSERT_GUARD:-on}" = "off" ] && exit 0
command -v jq > /dev/null 2>&1 || exit 0
command -v git > /dev/null 2>&1 || exit 0
INPUT=$(cat 2>/dev/null)
[ "$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
git -C "$ROOT" rev-parse --verify -q HEAD > /dev/null 2>&1 || exit 0

# Test dosyası sayılan yollar: *Test*/*test*/*spec* adları ve tests/ klasörleri.
DIFF=$(git -C "$ROOT" diff -U0 HEAD -- \
  ':(glob)**/*[Tt]est*' ':(glob)**/*[Ss]pec*' ':(glob)**/tests/**' ':(glob)**/test/**' 2>/dev/null)
[ -n "$DIFF" ] || exit 0

REMOVED=$(printf '%s\n' "$DIFF" | grep -E '^-[^-]' | grep -cE '(Assert\.|assert[[:space:](]|expect\(|Should\(\)|\.Should[A-Z]|EXPECT_|ASSERT_)')
ADDED=$(printf '%s\n' "$DIFF" | grep -E '^\+[^+]' | grep -cE '(Assert\.|assert[[:space:](]|expect\(|Should\(\)|\.Should[A-Z]|EXPECT_|ASSERT_)')
SKIPS=$(printf '%s\n' "$DIFF" | grep -E '^\+[^+]' | grep -ciE '(Skip[[:space:]]*=|\[Ignore|\.skip\(|pytest\.mark\.skip|@unittest\.skip|@Disabled|xit\(|xdescribe\(|GTEST_SKIP|DISABLED_)')

MSG=""
if [ "${REMOVED:-0}" -gt "${ADDED:-0}" ]; then
  MSG="Test dosyalarında $REMOVED assertion satırı silinmiş, yalnızca $ADDED eklenmiş."
fi
if [ "${SKIPS:-0}" -gt 0 ]; then
  MSG="${MSG:+$MSG }Testlere $SKIPS Skip/Ignore işareti eklenmiş."
fi
[ -n "$MSG" ] || exit 0

REASON="Assertion koruması: $MSG Testi geçirmek için assertion silmek/zayıflatmak veya Skip eklemek yasak. Ya gerçek hatayı kodda düzelt ya da beklenti gerçekten eskidiyse geri al ve gerekçeyi raporunda açıkça yaz (git diff HEAD -- <test dosyası>)."
jq -n --arg r "$REASON" '{decision: "block", reason: $r}'
exit 0
