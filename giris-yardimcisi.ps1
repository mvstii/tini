<#
  giris-yardimcisi.ps1 - Kurulumdan sonra elle yapılması gereken girişleri adım adım yönlendirir.
  - Her aracın kurulu ve girişli olup olmadığını denetler; eksik olanı nasıl tamamlayacağınızı söyler.
  - Şifre/anahtar İSTEMEZ ve kaydetmez; girişler aracın kendi ekranında sizin tarafınızdan yapılır.
  Kullanım:
    powershell -ExecutionPolicy Bypass -File .\giris-yardimcisi.ps1              # adım adım yönlendirir
    powershell -ExecutionPolicy Bypass -File .\giris-yardimcisi.ps1 -KontrolEt   # yalnızca durumu gösterir
#>
param([switch]$KontrolEt)

$ErrorActionPreference = 'Continue'

function Test-Tool($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Update-SessionPath {
    $env:Path = "$([Environment]::GetEnvironmentVariable('Path','Machine'));$([Environment]::GetEnvironmentVariable('Path','User'))"
}
Update-SessionPath

# Her adım: Ad, komut, durum denetimi (scriptblock, $true = hazır), giriş komutu, açıklama, zorunlu mu
$adimlar = @(
    @{ Ad = 'GitHub CLI (gh)'; Cmd = 'gh'; Zorunlu = $false
       Kontrol = { gh auth status 2>&1 | Out-Null; $LASTEXITCODE -eq 0 }
       Giris = { gh auth login }
       Not = 'PR açmak/birleştirmek için gerekir. Tarayıcıdan GitHub hesabınızla onaylarsınız.' },
    @{ Ad = 'Antigravity CLI (agy) - Gemini köprüsü'; Cmd = 'agy'; Zorunlu = $false
       Kontrol = { agy -p /usage 2>&1 | Out-Null; $LASTEXITCODE -eq 0 }
       Giris = { Write-Host '  agy açılacak; Google AI Pro hesabınızla girin, sonra çıkın (Ctrl+C).'; agy }
       Not = 'Seviye 2 (geniş tarama) için gerekir. Google AI Pro aboneliği olmayanlar atlayabilir; Sonnet/Explore devralır.' },
    @{ Ad = 'Codex CLI (isteğe bağlı çapraz denetim)'; Cmd = 'codex.cmd'; Zorunlu = $false
       Kontrol = { codex.cmd login status 2>&1 | Out-Null; $LASTEXITCODE -eq 0 }
       Giris = { codex.cmd login }
       Not = 'Yalnızca -Extra ile kurulduysa. Router ile ilişkili değildir; atlayabilirsiniz.' }
)

Write-Host ''
Write-Host 'aegis-hybrid-harness - giriş yardımcısı' -ForegroundColor Cyan
Write-Host '---------------------------------------'

# Önkoşullar (giriş gerektirmeyen)
Write-Host 'Önkoşullar:'
foreach ($t in @(@('git','Git'), @('node','Node.js'), @('dotnet','.NET SDK'), @('claude','Claude Code'))) {
    if (Test-Tool $t[0]) { Write-Host ("  [var]   {0}" -f $t[1]) -ForegroundColor Green }
    else { Write-Host ("  [YOK]   {0}  -> kurulum.ps1 çalıştırın (Claude Code için: https://claude.com/claude-code)" -f $t[1]) -ForegroundColor Yellow }
}

$ozet = @()
foreach ($a in $adimlar) {
    Write-Host ''
    Write-Host ("> {0}" -f $a.Ad) -ForegroundColor Cyan
    Write-Host ("  {0}" -f $a.Not)
    if (-not (Test-Tool $a.Cmd)) {
        Write-Host '  [kurulu değil] Önce kurulum.ps1 (gerekirse -Extra) çalıştırın; yeni terminal açmanız gerekebilir.' -ForegroundColor Yellow
        $ozet += "[kurulu değil] $($a.Ad)"; continue
    }
    $hazir = & $a.Kontrol
    if ($hazir) { Write-Host '  [giriş tamam]' -ForegroundColor Green; $ozet += "[tamam]        $($a.Ad)"; continue }
    Write-Host '  [giriş gerekli]' -ForegroundColor Yellow
    if ($KontrolEt -or -not [Environment]::UserInteractive) { $ozet += "[giriş gerekli] $($a.Ad)"; continue }
    $yanit = Read-Host '  Şimdi giriş yapılsın mı? (e = evet, Enter = atla)'
    if ($yanit -match '^(e|evet|y|yes)$') {
        & $a.Giris
        if (& $a.Kontrol) { $ozet += "[tamam]        $($a.Ad)" } else { $ozet += "[giriş gerekli] $($a.Ad) (doğrulanamadı)" }
    } else { $ozet += "[atlandı]      $($a.Ad)" }
}

# Gemini yedek yolu: API anahtarı (yalnızca bilgi; anahtar istenmez)
Write-Host ''
Write-Host '> Gemini yedek yolu (isteğe bağlı)' -ForegroundColor Cyan
if ($env:GEMINI_API_KEY) { Write-Host '  GEMINI_API_KEY tanımlı: gemini.cmd yedeği kullanılabilir.' -ForegroundColor Green }
else { Write-Host '  agy yoksa gemini.cmd için GEMINI_API_KEY ortam değişkeni gerekir (Google AI Studio üzerinden alınır). Anahtarı sohbete/dosyaya yazmayın.' }

Write-Host ''
Write-Host 'Özet:'
$ozet | ForEach-Object { Write-Host "  $_" }
Write-Host ''
Write-Host 'Hazırsanız proje klasöründe `claude` komutuyla başlayın. Bu yardımcıyı istediğiniz zaman yeniden çalıştırabilirsiniz.'
