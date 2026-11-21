# stop.ps1 — ปิด dev servers ที่ค้างอยู่ (เฉพาะ port 8000 และ 5173)
# ใช้: .\stop.cmd
$ErrorActionPreference = 'Continue'

$ports = 8000, 5173
$killed = @()

foreach ($port in $ports) {
    $lines = netstat -ano | Select-String -Pattern ":$port\s" | Select-String -Pattern 'LISTENING'
    foreach ($line in $lines) {
        $parts = ($line.Line -split '\s+') | Where-Object { $_ }
        $processId = $parts[-1]
        if (-not $processId -or $processId -eq '0') { continue }

        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        $name = if ($proc) { $proc.ProcessName } else { 'unknown' }
        Write-Host "port $port -> killing $name (pid $processId)" -ForegroundColor Yellow
        taskkill /PID $processId /T /F 2>$null | Out-Null
        $killed += "$name:$processId"
    }
}

if ($killed.Count -eq 0) {
    Write-Host 'nothing listening on 8000 or 5173' -ForegroundColor Green
} else {
    Write-Host ("stopped: " + ($killed -join ', ')) -ForegroundColor Green
}
