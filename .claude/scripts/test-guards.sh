#!/usr/bin/env bash
# Kanca regresyon testi (CI'da da çalışır). Beklenen çıkış kodu tutmazsa 1 ile biter.
# 2 = reddedildi, 0 = geçti. Gerekenler: bash, jq, git; shellcheck varsa o da çalışır.
# Not: test girdilerindeki gizli dosya adları parçalı yazılır ki bu dosya guard'a takılmasın.
cd "$(dirname "$0")/../.." || exit 1
G=.claude/scripts/pre-tool-guard.sh; R=.claude/scripts/restrict-bash.sh; W=.claude/scripts/restrict-write.sh
A=.claude/scripts/assert-guard.sh; S=.claude/scripts/session-start.sh
FAIL=0
check() { # beklenen, gerçek, etiket
  if [ "$1" = "$2" ]; then echo "ok   rc=$2 :: $3"; else echo "FAIL rc=$2 (beklenen $1) :: $3"; FAIL=1; fi
}
# guard: araç adı + girdi JSON'u
gj() { printf '%s' "$2" | bash $G >/dev/null 2>&1; check "$1" $? "guard $3"; }
gb() { gj "$1" "$(jq -cn --arg t "${3:-Bash}" --arg c "$2" '{tool_name:$t, tool_input:{command:$c}}')" "${3:-Bash}: $2"; }

E='.e''nv'
gb 2 "cat .e''nv"; gb 2 "cat $E"; gb 2 "cat id_rsa"; gb 2 "cat server.pem"; gb 2 "cat \"my.key\""
gb 0 "ls src"; gb 0 "git status"; gb 0 "git commit -m ok"
gb 2 "rm -rf /"; gb 2 "rm -r ~"; gb 0 "rm -rf build/tmp"
# PowerShell ve Monitor da aynı komut denetiminden geçer.
gb 2 "Get-Content $E" PowerShell
gb 2 "Remove-Item -Recurse -Force C:\\" PowerShell
gb 2 "Remove-Item -Recurse \$HOME" PowerShell
gb 0 "Remove-Item -Recurse -Force .\\bin" PowerShell
gb 0 "Get-ChildItem src" PowerShell
gb 2 "tail -f $E" Monitor
# NotebookEdit: yol notebook_path alanında, içerik new_source alanında.
gj 2 "$(jq -cn --arg p "nb/$E" '{tool_name:"NotebookEdit", tool_input:{notebook_path:$p, new_source:"x=1"}}')" "NotebookEdit: gizli dosya yolu"
gj 2 "$(jq -cn --arg s "API""_KEY = 'abcdefghijklmnop'" '{tool_name:"NotebookEdit", tool_input:{notebook_path:"nb/a.ipynb", new_source:$s}}')" "NotebookEdit: içerikte anahtar ataması"
gj 0 "$(jq -cn '{tool_name:"NotebookEdit", tool_input:{notebook_path:"nb/a.ipynb", new_source:"print(1)"}}')" "NotebookEdit: zararsız"

# restrict-bash (salt-okunur ajan Bash'i)
rb() { printf '%s' "$(jq -cn --arg c "$2" '{tool_input:{command:$c}}')" | bash $R >/dev/null 2>&1; check "$1" $? "restrict $2"; }
rb 2 'git diff --output=x'; rb 2 'rg --pre cmd foo'; rb 2 'cat a | sort -o f'; rb 2 'cat a | sort'
rb 0 'git diff | head'; rb 0 'git log'

# restrict-write (yalnızca izinli dosya adları; notebook_path de denetlenir)
rw() { printf '%s' "$2" | bash $W SPEC.md >/dev/null 2>&1; check "$1" $? "restrict-write $3"; }
rw 0 '{"tool_input":{"file_path":"C:\\dev\\p\\SPEC.md"}}' "SPEC.md"
rw 2 '{"tool_input":{"file_path":"src/a.cs"}}' "src/a.cs"
rw 2 '{"tool_input":{"notebook_path":"nb/a.ipynb"}}' "notebook"

# session-start: geçerli JSON üretmeli
OUT=$(printf '{"session_id":"t"}' | bash $S 2>/dev/null)
printf '%s' "$OUT" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null 2>&1; check 0 $? "session-start JSON"

# assert-guard: geçici bir git deposunda assertion silme bloklanmalı, ekleme geçmeli
T=$(mktemp -d)
(
  cd "$T" && git init -q && git config user.email t@t && git config user.name t
  mkdir -p tests && printf 'def test_a():\n    assert 1 == 1\n    assert 2 == 2\n' > tests/test_a.py
  git add . && git commit -qm init
)
printf 'def test_a():\n    assert 1 == 1\n' > "$T/tests/test_a.py"
OUT=$(printf '{}' | CLAUDE_PROJECT_DIR="$T" bash $A 2>/dev/null)
D=$(printf '%s' "$OUT" | jq -r '.decision // empty'); check block "${D:-yok}" "assert-guard: silinen assertion bloklanır"
OUT=$(printf '{"stop_hook_active":true}' | CLAUDE_PROJECT_DIR="$T" bash $A 2>/dev/null)
check "" "$OUT" "assert-guard: stop_hook_active döngü yapmaz"
printf 'def test_a():\n    assert 1 == 1\n    assert 2 == 2\n    assert 3 == 3\n' > "$T/tests/test_a.py"
OUT=$(printf '{}' | CLAUDE_PROJECT_DIR="$T" bash $A 2>/dev/null)
check "" "$OUT" "assert-guard: assertion ekleme geçer"
rm -rf "$T"

# security-audit (Aşama 21): elle çağrılır, AEGIS.md'ye yönlendirir, çıktı klasörü git dışı
SA=.claude/skills/security-audit
grep -q '^disable-model-invocation: true' "$SA/SKILL.md"; check 0 $? "security-audit: yalnızca elle çağrılır"
grep -q 'AEGIS.md' "$SA/SKILL.md"; check 0 $? "security-audit: AEGIS.md yönlendirmesi"
git check-ignore -q .guvenlik-denetimi/x; check 0 $? "security-audit: çıktı klasörü git dışı"
jq -e . .claude/settings.json >/dev/null; check 0 $? "settings.json geçerli JSON"
if command -v shellcheck > /dev/null 2>&1; then
  shellcheck -S warning .claude/scripts/*.sh >/dev/null; check 0 $? "shellcheck -S warning"
fi
exit $FAIL
