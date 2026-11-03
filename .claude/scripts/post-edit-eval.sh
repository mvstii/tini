#!/usr/bin/env bash
# Madde 15 & 21: Dosya kaydedildiği an çalışan Otomatik Doğrulama Döngüsü (Eval-Driven Loop)
# Proje türüne göre derleyiciyi otomatik algılar ve hata varsa Claude'a geri besler (exit 2).
# Ortam notu (Windows 11): dotnet kurulu; araç eksikse atlanır ve stderr'e tek satır uyarı yazılır.

INPUT=$(cat 2>/dev/null)
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Hook girdisindeki (JSON) düzenlenen dosya yolu; elle çalıştırmada boş olabilir.
FILE=""
if command -v jq > /dev/null 2>&1; then
  FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null | tr '\\' '/')
fi
# jq yoksa veya ayrıştıramadıysa eski grep+sed yoluna düş.
if [ -z "$FILE" ]; then
  FILE=$(printf '%s' "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed 's/.*:[[:space:]]*"\(.*\)"/\1/' | sed 's/\\\\/\//g')
fi
# Tek veya çift ters eğik çizgili Windows yollarını / biçimine çevir (aksi halde find_up sessizce bulamaz).
FILE=$(printf '%s' "$FILE" | tr '\\' '/' | sed 's#//*#/#g')

# SPEC.md yazıldığında, "yol:satır" biçimiyle verilen hedef yollarının diskte var olduğunu doğrula
# (gemini-scout çıktısı gibi uydurma yolları yakalar). Yalnızca `dosya/yol.ext:12-30` biçimine bakılır.
spec_check() {
  local spec="$1" missing="" p
  [ -f "$spec" ] || return 0
  while IFS= read -r p; do
    [ -n "$p" ] && [ ! -e "$ROOT/$p" ] && missing="$missing $p"
  done < <(grep -oE '`[A-Za-z0-9_./-]+:[0-9][0-9,-]*`' "$spec" | tr -d '`' | sed 's/:.*//' | sort -u)
  if [ -n "$missing" ]; then
    echo "❌ [SPEC DOĞRULAMA - EVAL LOOP]: SPEC.md'de diskte olmayan yollar var:$missing. Gerçek dosyalarla düzelt." >&2
    return 2
  fi
}

# Diğer diller (Python söz dizimi, Go, Rust): araç kuruluysa çalışır, yoksa sessizce atlanır.
# Düzenlenen dosyadan yukarı doğru işaret dosyasını (go.mod, Cargo.toml) arar.
find_marker() {
  local dir
  dir=$(dirname "$1")
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -e "$dir/$2" ] && { echo "$dir"; return; }
    { [ "$dir" = "$ROOT" ] || [ "$dir" = "/" ] || [ "$dir" = "." ]; } && return
    dir=$(dirname "$dir")
  done
}
run_check() { # etiket, klasör, komut...
  local label="$1" dir="$2" out st
  shift 2
  out=$(cd "$dir" && timeout 180 "$@" 2>&1)
  st=$?
  if [ $st -eq 124 ]; then echo "⚠️ [EVAL LOOP]: $label 180 sn içinde bitmedi, doğrulama atlandı." >&2; exit 0; fi
  if [ $st -ne 0 ]; then
    echo "❌ [$label HATASI - EVAL LOOP]: Kullanıcıya dönmeden önce şu hataları hemen düzelt:" >&2
    echo "$out" | tail -n 25 >&2
    exit 2
  fi
  exit 0
}
other_lang() {
  case "$1" in
    *.py)
      local py=""
      for c in python3 python; do # Windows Store yer tutucusu çalışmaz; gerçekten çalışanı seç.
        if command -v "$c" > /dev/null 2>&1 && "$c" -c "" > /dev/null 2>&1; then py="$c"; break; fi
      done
      [ -n "$py" ] || { echo "⚠️ [EVAL LOOP]: python bulunamadı, söz dizimi doğrulaması atlandı." >&2; exit 0; }
      run_check "PYTHON SÖZ DİZİMİ" "$(dirname "$1")" "$py" -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1])" "$1" ;;
    *.go)
      command -v go > /dev/null 2>&1 || exit 0
      local d; d=$(find_marker "$1" go.mod); [ -n "$d" ] || exit 0
      run_check "GO DERLEME" "$d" go build ./... ;;
    *.rs)
      command -v cargo > /dev/null 2>&1 || exit 0
      local d; d=$(find_marker "$1" Cargo.toml); [ -n "$d" ] || exit 0
      run_check "RUST DERLEME" "$d" cargo check -q --message-format short ;;
  esac
}

# Derleme gerektirmeyen dosyalar (.md, .sh vb.) için hiçbir şey yapma.
if [ -n "$FILE" ]; then
  case "$FILE" in
    *SPEC.md) spec_check "$FILE"; exit $? ;;
    *.py|*.go|*.rs) other_lang "$FILE"; exit 0 ;;
    *.cs|*.csproj|*.sln|*.slnx|*.props|*.targets|*.ts|*.tsx|*tsconfig.json) ;;
    *) exit 0 ;;
  esac
fi

# Düzenlenen dosyadan yukarı doğru en yakın .sln/.slnx (yoksa .csproj) dosyasını bul.
find_up() {
  local dir
  dir=$(dirname "$1")
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    local hit
    hit=$(compgen -G "$dir/*.sln" | head -n 1)
    [ -z "$hit" ] && hit=$(compgen -G "$dir/*.slnx" | head -n 1)
    [ -z "$hit" ] && hit=$(compgen -G "$dir/*.csproj" | head -n 1)
    if [ -n "$hit" ]; then echo "$hit"; return; fi
    [ "$dir" = "$ROOT" ] || [ "$dir" = "/" ] || [ "$dir" = "." ] && return
    dir=$(dirname "$dir")
  done
}

TARGET=""
if [ -n "$FILE" ]; then
  TARGET=$(find_up "$FILE")
fi
# Dosya bilinmiyorsa kökün en fazla 3 seviye altında ara.
if [ -z "$TARGET" ] && [ -z "$FILE" ]; then
  TARGET=$(find "$ROOT" -maxdepth 3 \( -name '*.sln' -o -name '*.slnx' -o -name '*.csproj' \) \
    -not -path '*/node_modules/*' -not -path '*/obj/*' -not -path '*/bin/*' \
    -not -path '*/.git/*' -not -path '*/.claude/*' 2>/dev/null | sort | head -n 1)
fi

if [ -n "$TARGET" ]; then
  if ! command -v dotnet > /dev/null 2>&1; then
    echo "⚠️ [EVAL LOOP]: dotnet bulunamadı, derleme doğrulaması atlandı." >&2
    exit 0
  fi
  # Yalnızca hata satırları (bağlam şişmesin). .cs düzenlemesinde restore atlanır; paket/varlık
  # eksikliği (NETSDK1004/1064) görülürse bir kez restore'lu yeniden denenir.
  BUILD_ARGS=(--nologo -v q -clp:ErrorsOnly)
  case "$FILE" in *.cs) BUILD_ARGS=(--no-restore "${BUILD_ARGS[@]}") ;; esac
  OUTPUT=$(timeout 180 dotnet build "$TARGET" "${BUILD_ARGS[@]}" 2>&1)
  STATUS=$?
  if [ $STATUS -ne 0 ] && [ $STATUS -ne 124 ] && printf '%s' "$OUTPUT" | grep -qE 'NETSDK1004|NETSDK1064'; then
    OUTPUT=$(timeout 180 dotnet build "$TARGET" --nologo -v q -clp:ErrorsOnly 2>&1)
    STATUS=$?
  fi
  if [ $STATUS -eq 124 ]; then
    echo "⚠️ [EVAL LOOP]: dotnet build 180 sn içinde bitmedi, doğrulama atlandı." >&2
    exit 0
  fi
  if [ $STATUS -ne 0 ]; then
    echo "❌ [OTOMATİK DERLEME HATASI - EVAL LOOP]: Yazdığın C# kodu derlenemedi! Kullanıcıya dönmeden önce şu hataları hemen düzelt:" >&2
    echo "$OUTPUT" | tail -n 25 >&2
    exit 2
  fi
elif [ -f "$ROOT/tsconfig.json" ]; then
  if ! command -v npx > /dev/null 2>&1; then
    echo "⚠️ [EVAL LOOP]: npx bulunamadı, tip doğrulaması atlandı." >&2
    exit 0
  fi
  OUTPUT=$(cd "$ROOT" && timeout 180 npx --no-install tsc --noEmit --pretty false 2>&1)
  if [ $? -ne 0 ]; then
    echo "❌ [TYPESCRIPT TİP HATASI - EVAL LOOP]: Lütfen tip hatalarını hemen düzelt:" >&2
    echo "$OUTPUT" | tail -n 25 >&2
    exit 2
  fi
fi
exit 0
