# verify.ps1 — รันทุก gate ด้วยคำสั่งเดียว
# ใช้: .\verify.cmd
$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$failed = @()

function Step {
    param([string]$Name, [string]$Workdir, [scriptblock]$Block)
    Write-Host ''
    Write-Host "== $Name" -ForegroundColor Cyan
    Push-Location $Workdir
    try {
        & $Block
        if ($LASTEXITCODE -ne 0) { $script:failed += $Name }
    } finally {
        Pop-Location
    }
}

Step 'backend lint' $backend { uv run ruff check . }
Step 'backend tests' $backend { uv run pytest -q }
Step 'frontend types' $frontend { bun run check }
Step 'frontend build' $frontend { bun run build }

Write-Host ''
Write-Host '== independence' -ForegroundColor Cyan
$hits = Get-ChildItem -Recurse -File (Join-Path $root 'backend'), (Join-Path $root 'frontend') |
    Where-Object { $_.FullName -notmatch '\\.venv\\|node_modules|\\.svelte-kit|\\build\\|__pycache__' } |
    Select-String -Pattern 'worakrit' -SimpleMatch
if ($hits) {
    $hits | ForEach-Object { Write-Host $_.Path }
    $failed += 'independence'
} else {
    Write-Host 'no matches'
}

Write-Host ''
if ($failed.Count -gt 0) {
    Write-Host "FAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host 'ALL CHECKS PASSED' -ForegroundColor Green
exit 0
