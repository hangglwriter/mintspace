# mintspace helper background launcher (+ optional browser open)
# Direct call: powershell -ExecutionPolicy Bypass -File start-helper.ps1
# Headless:    powershell -ExecutionPolicy Bypass -File start-helper.ps1 -NoBrowser

param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Continue"
$here = $PSScriptRoot
$server = Join-Path $here "helper\server.py"

# 1. Kill any process listening on 5500
try {
    $conn = Get-NetTCPConnection -LocalPort 5500 -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $conn | ForEach-Object {
            try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
        }
        Start-Sleep -Milliseconds 500
    }
} catch {}

# 2. Find python.exe (pythonw can silent-fail; we use python + Hidden window instead)
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $python = $c; break }
    }
}
if (-not $python) {
    Write-Host "[ERROR] python.exe not found. Check Python installation."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "python: $python"
Write-Host "server: $server"

# 3. Launch helper (window hidden, detached background)
Start-Process -FilePath $python -ArgumentList "`"$server`"" -WindowStyle Hidden

# 4. Wait for helper health endpoint (up to 25s - first start loads fastapi/uvicorn)
$ok = $false
Write-Host "Starting helper..."
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5500/api/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
}

if ($ok) {
    Write-Host "[OK] helper ready: http://localhost:5500"
} else {
    Write-Host "[WARN] helper not responding in 25s. Opening browser anyway (refresh after a few seconds)."
}

# 5. Open browser (unless -NoBrowser passed)
if (-not $NoBrowser) {
    Start-Process "http://localhost:5500"
}
