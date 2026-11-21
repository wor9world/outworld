# dev.ps1 — เปิด backend + frontend พร้อมกันด้วยคำสั่งเดียว
# ใช้: .\dev.cmd
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$logDir = Join-Path $root 'data'
$stdoutLog = Join-Path $logDir 'dev-backend.log'
$stderrLog = Join-Path $logDir 'dev-backend.err.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Test-Backend {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        return $health.status -eq 'ok'
    } catch {
        return $false
    }
}

$started = $null
if (Test-Backend) {
    Write-Host 'backend  : already running on :8000' -ForegroundColor Green
} else {
    $python = Join-Path $backend '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        Write-Host 'backend venv missing — run: cd backend; uv sync' -ForegroundColor Red
        exit 1
    }

    $started = Start-Process -FilePath $python `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload' `
        -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Backend) { $ready = $true; break }
    }
    if (-not $ready) {
        Write-Host "backend failed to start — see $stderrLog" -ForegroundColor Red
        taskkill /PID $started.Id /T /F 2>$null | Out-Null
        exit 1
    }
    Write-Host "backend  : http://127.0.0.1:8000   (log: $stdoutLog)" -ForegroundColor Green
}

Write-Host 'frontend : http://127.0.0.1:5173' -ForegroundColor Green
Write-Host 'Ctrl+C stops both.' -ForegroundColor DarkGray

try {
    Push-Location $frontend
    bun run dev
} finally {
    Pop-Location
    if ($null -ne $started) {
        taskkill /PID $started.Id /T /F 2>$null | Out-Null
        Write-Host 'backend stopped' -ForegroundColor DarkGray
    }
}
