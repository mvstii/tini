# Canlı /votes/queue probu: algo_version, remaining, stale, items sayısı ve kaynak dağılımı.
# Kullanım: powershell -File .\scripts\live_algo_check.ps1
# Parola gizli sorulur, hiçbir yere yazılmaz. Oturum jetonu yalnızca bellekte kalır ve sonunda
# çıkış yapılarak geçersiz kılınır.
param([string]$Base = "https://tini-74he.onrender.com")

$ErrorActionPreference = "Stop"
$email = Read-Host "E-posta"
$sec = Read-Host "Parola" -AsSecureString
$pw = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))

Write-Host "Sunucu uyandırılıyor (soğuk başlangıç 30-60 sn sürebilir)..."
$login = Invoke-RestMethod -Method Post -Uri "$Base/auth/login" -ContentType "application/json" `
    -Body (@{ email = $email; password = $pw } | ConvertTo-Json) -TimeoutSec 90
$pw = $null
$h = @{ Authorization = "Bearer $($login.token)" }

try {
    for ($i = 1; $i -le 3; $i++) {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $q = Invoke-RestMethod -Uri "$Base/votes/queue?seed=$i" -Headers $h -TimeoutSec 45
        $sw.Stop()
        $src = ($q.items | Group-Object { if ($_.source) { $_.source } else { "library" } } |
            ForEach-Object { "$($_.Name)=$($_.Count)" }) -join ", "
        $noTitle = @($q.items | Where-Object { -not $_.title }).Count
        $noImage = @($q.items | Where-Object { -not $_.image }).Count
        Write-Host ("[{0}] algo={1} remaining={2} stale={3} items={4} ({5}) basliksiz={6} kapaksiz={7} sure={8} ms" -f `
            $i, $q.algo_version, $q.remaining, $q.stale, $q.items.Count, $src, $noTitle, $noImage,
            $sw.ElapsedMilliseconds)
        Start-Sleep -Seconds 3
    }
}
finally {
    try { Invoke-RestMethod -Method Post -Uri "$Base/auth/logout" -Headers $h -TimeoutSec 20 | Out-Null } catch {}
}
