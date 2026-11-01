# Release imza anahtarını bir kez oluşturur (depo dışında) ve mobile/android/key.properties yazar.
# Çalıştırma: powershell -ExecutionPolicy Bypass -File scripts/android-imza.ps1
# Anahtar dosyasını YEDEKLE: kaybolursa testçiler güncelleme yerine kaldır-yeniden kur yapmak zorunda kalır.
$ErrorActionPreference = 'Stop'
$keytool = 'C:\src\android-studio\jbr\bin\keytool.exe'
$dir = Join-Path $env:USERPROFILE 'tini-gizli'
$jks = Join-Path $dir 'tini-release.jks'
$props = Join-Path $PSScriptRoot '..\mobile\android\key.properties'
if (Test-Path $jks) { throw "$jks zaten var; üzerine yazılmadı." }
New-Item -ItemType Directory -Force $dir | Out-Null
$pw = -join ((48..57 + 65..90 + 97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
& $keytool -genkeypair -storetype JKS -keystore $jks -alias tini -keyalg RSA -keysize 2048 `
  -validity 10000 -storepass $pw -keypass $pw -dname 'CN=Tini, O=Tini, C=TR'
if ($LASTEXITCODE -ne 0) { throw 'keytool basarisiz' }
@"
storePassword=$pw
keyPassword=$pw
keyAlias=tini
storeFile=$($jks -replace '\\','/')
"@ | Set-Content -Encoding ascii $props
Write-Host "Tamam: $jks ve mobile/android/key.properties (ikisi de depoya girmez)."
