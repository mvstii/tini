<#
  kurulum.ps1 - aegis-hybrid-harness gereksinimlerini kurar.
  - Idempotent: kurulu olan araca dokunmaz, sormaz; yalnızca eksikleri kurar.
  - Kimlik doğrulama yapmaz (gemini/gh girişini kullanıcı yapar).
  Kullanım:
    powershell -ExecutionPolicy Bypass -File .\kurulum.ps1          # çekirdek araçlar
    powershell -ExecutionPolicy Bypass -File .\kurulum.ps1 -Extra   # + isteğe bağlı CLI'lar
#>
param([switch]$Extra)

$ErrorActionPreference = 'Continue'

function Test-Tool($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

$results = @()

function Install-Winget($name, $cmd, $id) {
    if (Test-Tool $cmd) { $script:results += "[var]    $name"; return }
    if (-not (Test-Tool 'winget')) { $script:results += "[HATA]   $name (winget yok)"; return }
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Update-SessionPath
    if (Test-Tool $cmd) { $script:results += "[kuruldu] $name" } else { $script:results += "[HATA]   $name (kurulum sonrası bulunamadı; yeni terminal açın)" }
}

function Install-Npm($name, $cmd, $pkg) {
    if (Test-Tool $cmd) { $script:results += "[var]    $name"; return }
    if (-not (Test-Tool 'npm.cmd')) { $script:results += "[HATA]   $name (npm yok; önce Node.js)"; return }
    npm.cmd install -g $pkg 2>&1 | Out-Null
    Update-SessionPath
    if (Test-Tool $cmd) { $script:results += "[kuruldu] $name" } else { $script:results += "[HATA]   $name" }
}

# Çekirdek araçlar
Install-Winget 'Git (bash kancaları için)' 'git'    'Git.Git'
Install-Winget 'Node.js LTS'               'node'   'OpenJS.NodeJS.LTS'
Install-Winget '.NET SDK 10'               'dotnet' 'Microsoft.DotNet.SDK.10'
Install-Winget 'GitHub CLI'                'gh'     'GitHub.cli'
Install-Winget 'Antigravity CLI (agy, Google AI Pro girişi)' 'agy' 'Google.AntigravityCLI'

function Install-DotnetTool($name, $cmd, $pkg) {
    if (Test-Tool $cmd) { $script:results += "[var]    $name"; return }
    if (-not (Test-Tool 'dotnet')) { $script:results += "[HATA]   $name (dotnet yok)"; return }
    dotnet tool install --global $pkg 2>&1 | Out-Null
    $env:Path = "$env:Path;$env:USERPROFILE\.dotnet\tools"
    if (Test-Tool $cmd) { $script:results += "[kuruldu] $name" } else { $script:results += "[HATA]   $name (yeni terminal açın)" }
}

# LSP sunucuları (csharp-lsp ve pyright-lsp pluginleri için; pluginler .claude/settings.json ile etkin)
Install-DotnetTool 'csharp-ls (C# LSP)'          'csharp-ls'               'csharp-ls'
Install-Npm        'pyright (Python LSP)'        'pyright-langserver.cmd'  'pyright'

# Claude Code sürümü: onFailure ve Windows kanca düzeltmeleri için en az 2.1.310
if (Test-Tool 'claude') {
    $cv = (claude --version 2>$null | Select-Object -First 1)
    if ($cv -match '(\d+)\.(\d+)\.(\d+)') {
        $ver = [version]"$($Matches[1]).$($Matches[2]).$($Matches[3])"
        if ($ver -lt [version]'2.1.310') { $results += "[UYARI]  Claude Code $ver eski; en az 2.1.310 gerekli (claude update)" }
        else { $results += "[var]    Claude Code $ver" }
    }
} else { $results += "[HATA]   Claude Code bulunamadı (claude komutu yok)" }

# İsteğe bağlı
if ($Extra) {
    Install-Npm 'Codex CLI (OpenAI, çapraz denetim; codex plugin bunu kullanır)' 'codex.cmd' '@openai/codex'
    Install-Npm 'Gemini CLI (yedek köprü; yalnızca ücretli Gemini API anahtarıyla)' 'gemini.cmd' '@google/gemini-cli'

    # Ajan/kanca araçları
    Install-Winget 'jq (kanca JSON ayrıştırma)'        'jq'         'jqlang.jq'
    Install-Winget 'gitleaks (sızıntı taraması)'       'gitleaks'   'Gitleaks.Gitleaks'
    Install-Winget 'shellcheck (bash kanca denetimi)'  'shellcheck' 'koalaman.shellcheck'
    Install-Winget 'ripgrep (hızlı içerik arama)'      'rg'         'BurntSushi.ripgrep.MSVC'
    Install-Winget 'fd (hızlı dosya arama)'            'fd'         'sharkdp.fd'
    Install-Npm    'ast-grep (AST tabanlı sembol arama)' 'ast-grep.cmd' '@ast-grep/cli'
}

Write-Host ''
Write-Host 'Kurulum özeti:'
$results | ForEach-Object { Write-Host "  $_" }
Write-Host ''
Write-Host 'Elle yapılacaklar (otomatik yapılmaz):'
Write-Host '  - agy ile ilk girişi yapın (interaktif, Google AI Pro hesabı)'
Write-Host '  - gh auth login'
Write-Host '  - Klasörde claude başlatın: proje ayarındaki pluginleri (LSP, context7, security-guidance...) kurmayı onaylayın'
Write-Host '  - clangd-lsp için clangd ayrıca kurulmalı (LLVM); C/C++ kullanmıyorsanız gerek yok'
if ($Extra) {
    Write-Host '  - codex ile giriş yapın; çapraz denetim için Claude Code içinde:'
    Write-Host '      /plugin marketplace add openai/codex-plugin-cc   ve   /plugin install codex@openai-codex'
    Write-Host '  - gemini.cmd yalnızca ücretli Gemini API anahtarıyla çalışır (tüketici katmanı Haziran 2026da kapandı)'
}

# Commit öncesi sızıntı taraması (.githooks/pre-commit) bu depoda etkinleştirilir; idempotent.
if ((Test-Tool 'git') -and (Test-Path (Join-Path $PSScriptRoot '.githooks'))) {
    git -C $PSScriptRoot config core.hooksPath .githooks
    Write-Host 'Git kancaları etkin: core.hooksPath = .githooks'
}
