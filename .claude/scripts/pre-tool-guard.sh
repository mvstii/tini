#!/usr/bin/env bash
# Madde 26: Tool Poisoning ve Tehlikeli Komut Koruması (alan bazlı).
# Yalnızca ilgili alanlar denetlenir: komut, dosya yolu, yazılan içerik. Tüm JSON taranmaz.
# jq yoksa veya girdi ayrıştırılamazsa eski, geniş ve sıkı taramaya düşer (güvenlik gevşemez).
# Not: desenler parçalı yazılır ('' birleşimi); bu dosya kendi kuralına takılmasın diye.
INPUT=$(cat)

block() {
  echo "🚫 [GÜVENLİK DUVARI - PRE-TOOL HOOK]: $1 İşlem reddedildi." >&2
  exit 2
}

# Maliyet sigortası açıksa (circuit-breaker.sh işaretçi bıraktı) yeni işlem yapılmasın; kullanıcının
# yeni mesajı işaretçiyi siler (circuit-reset.sh). 60 dakikadan eski işaretçi yok sayılır.
if command -v jq > /dev/null 2>&1; then
  CB_SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null | tr -d '\r\n' | tr -c 'A-Za-z0-9_-' '_')
  CB_M="${CLAUDE_PROJECT_DIR:-$(pwd)}/.claude/logs/circuit/TRIPPED.$CB_SID"
  if [ -n "$CB_SID" ] && [ -f "$CB_M" ] && [ -n "$(find "$CB_M" -mmin -60 2>/dev/null)" ]; then
    block "Maliyet sigortası açık: aynı işlem tekrar tekrar başarısız oldu. Yeni işlem yapma; durumu kullanıcıya bildir ve yeni mesajını bekle."
  fi
fi

LEGACY='(\.e''nv|API''_KEY|SECR''ET|r''m -rf /|DROP[ ]TABLE)'
KEYW='(API''_KEY|SECR''ET)[A-Z0-9_]*'

if ! command -v jq > /dev/null 2>&1 || ! printf '%s' "$INPUT" | jq -e . > /dev/null 2>&1; then
  if printf '%s' "$INPUT" | grep -qiE "$LEGACY"; then
    block "Gizli dosya/anahtar erişimi veya yıkıcı komut tespit edildi (jq yok: geniş tarama)."
  fi
  exit 0
fi

# Kapsanan araçlar (settings.json matcher): Bash, PowerShell, Monitor (command); Edit, Write (file_path);
# NotebookEdit (notebook_path, new_source).
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
FPATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' | tr '\\' '/')
BODY=$(printf '%s' "$INPUT" | jq -r '[.tool_input.content, .tool_input.new_string, .tool_input.new_source] | map(select(. != null)) | join("\n")')

# 1) Dosya yolu: son bileşen gizli dosya adı mı?
if [ -n "$FPATH" ]; then
  BASE=${FPATH##*/}
  if printf '%s' "$BASE" | grep -qiE '^(\.e''nv(\..*)?|secre''ts?(\..*)?)$'; then
    block "Gizli dosya yoluna yazma/düzenleme tespit edildi."
  fi
fi

# 1b) SPEC.md kapsam kilidi (opt-in): SPEC.md'de "<!-- scope-lock: on -->" satırı varsa, Edit/Write
# yalnızca SPEC.md'de geçen dosyalara izin verir (CLAUDE.md, MEMORY.md, SPEC.md hariç).
# Eşleşme yol sonekiyle yapılır (mutlak/göreli ve harf büyüklüğü farkını tolere eder).
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')
SPEC="${CLAUDE_PROJECT_DIR:-$(pwd)}/SPEC.md"
if [ -n "$FPATH" ] && { [ "$TOOL" = "Edit" ] || [ "$TOOL" = "Write" ] || [ "$TOOL" = "NotebookEdit" ]; } \
   && [ -f "$SPEC" ] && grep -qxE '[[:space:]]*<!-- scope-lock: on -->[[:space:]]*' "$SPEC"; then
  case "${FPATH##*/}" in
    CLAUDE.md|MEMORY.md|SPEC.md) ;;
    *)
      LOW=${FPATH,,}
      ALLOWED=0
      while IFS= read -r t; do
        t=${t,,}
        if [ -n "$t" ] && { [ "$LOW" = "$t" ] || [ "${LOW%/"$t"}" != "$LOW" ]; }; then ALLOWED=1; break; fi
      done < <(grep -oE '`[A-Za-z0-9_./-]+(:[0-9][0-9,-]*)?`' "$SPEC" | tr -d '`' | sed 's/:.*//' | sort -u)
      [ "$ALLOWED" = 1 ] || block "Bu dosya SPEC.md kapsamında değil (scope-lock açık): ${FPATH##*/}."
      ;;
  esac
fi

if [ -n "$CMD" ]; then
  # 2) Komut: gizli dosya adı belirteci (her belirteç ayrı denetlenir).
  # Tırnaklar silinir ki cat .e''nv gibi bölünmüş yazımlar tek belirteç olarak denetlensin.
  if printf '%s' "$CMD" | tr -d "'\"" | tr '\\' '/' | tr -c 'A-Za-z0-9_./~*=-' '\n' | grep -qiE '^(.*/)?(\.e''nv(\..*)?|secre''ts?(\.[a-z0-9]+)?|id_(rsa|ed25519|ecdsa)|[^/]+\.(pem|key))$'; then
    block "Gizli dosya erişimi tespit edildi."
  fi
  # 3) Komut: gizli değişkeni okuma veya değer atama.
  if printf '%s' "$CMD" | grep -qiE "\\$\\{?[A-Z0-9_]*${KEYW}|${KEYW}[[:space:]]*=[[:space:]]*[^[:space:]]{8,}"; then
    block "Gizli değişken okuma/atama tespit edildi."
  fi
  # 4) Komut: kök veya ev dizinini silme (alt klasör silme serbest).
  if printf '%s' "$CMD" | grep -qE 'r''m([[:space:]]+-[a-zA-Z-]+)+[[:space:]]+(/|~|\$HOME)\*?([[:space:]]|$|[;&|])'; then
    block "Kök/ev dizinini silme komutu tespit edildi."
  fi
  # 4b) PowerShell: sürücü kökünü veya ev dizinini özyinelemeli silme
  # (Remove-Item/ri/rm/del/rd ... -Recurse C:\ | ~ | $HOME | $env:USERPROFILE). Alt klasör silme serbest.
  if printf '%s' "$CMD" | grep -qiE '(^|[;|&[:space:](])(remove-item|ri|rm|del|rd|rmdir|erase)[[:space:]]' \
     && printf '%s' "$CMD" | grep -qiE '(^|[[:space:]])-r(ecurse|f)?([[:space:]]|$)' \
     && printf '%s' "$CMD" | tr -d "'\"" | grep -qiE '(^|[[:space:]])([a-z]:[\\/]?|~[\\/]?|\$home[\\/]?|\$env:userprofile[\\/]?)\*?([[:space:]]|$|[;&|)])'; then
    block "Kök/ev dizinini silme komutu tespit edildi (PowerShell)."
  fi
  # 5) Komut: yıkıcı SQL.
  if printf '%s' "$CMD" | grep -qiE 'DROP[[:space:]]+(TABLE|DATABASE)'; then
    block "Yıkıcı SQL komutu tespit edildi."
  fi
fi

# 6) Yazılan içerik: yalnızca değer atanmış gizli anahtar biçimi (düz kelime değil).
if [ -n "$BODY" ] && printf '%s' "$BODY" | grep -qiE "${KEYW}[[:space:]]*[=:][[:space:]]*[^[:space:]]{12,}"; then
  block "İçerikte değer atanmış gizli anahtar biçimi tespit edildi."
fi

# Token uyarısı (yalnızca UZUN oturumlarda): ana bağlamdaki çok uzun Write içeriği veya Bash komutu kalıcı girer
# ve kalan her turda yeniden okunur. Ölçüm: kısa oturumda ajana devretmek (~15k token sabit başlangıç yükü)
# daha PAHALI çıktı, bu yüzden uyarı yalnızca oturum AEGIS_LONG_TURNS (40) turu aştıysa verilir.
# Alt ajanda (agent_id var) uyarılmaz; SPEC.md/MEMORY.md hariç. Eşik: AEGIS_BIG_CONTENT (12000 karakter).
if [ -z "$(printf '%s' "$INPUT" | jq -r '.agent_id // empty' 2>/dev/null)" ]; then
  SIZE=0
  [ "$TOOL" = "Write" ] && SIZE=${#BODY}
  { [ "$TOOL" = "Bash" ] || [ "$TOOL" = "PowerShell" ]; } && SIZE=${#CMD}
  case "${FPATH##*/}" in SPEC.md|MEMORY.md) SIZE=0 ;; esac
  if [ "$SIZE" -ge "${AEGIS_BIG_CONTENT:-12000}" ]; then
    TP=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null | tr '\\' '/')
    TURNS=0
    [ -n "$TP" ] && [ -f "$TP" ] && TURNS=$(grep -c '"type":"assistant"' "$TP" 2>/dev/null)
    if [ "${TURNS:-0}" -ge "${AEGIS_LONG_TURNS:-40}" ]; then
      jq -n --arg m "Token uyarısı: bu içerik yaklaşık $((SIZE / 4)) token ve uzun bir oturumda ana bağlamda kalıcı olur (kalan her turda yeniden okunur). Büyük dosya üretimini/yeniden yazımını @implementer-sonnet'e devretmeyi düşün; ana bağlam yalnızca kısa özeti görür." \
        '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $m}}'
    fi
  fi
fi
exit 0
