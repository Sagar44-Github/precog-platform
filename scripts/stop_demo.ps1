$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $repoRoot 'lead-core\backend\data'
$pidFile = Join-Path $dataDir 'demo-server.pid'
$python = (Resolve-Path (Join-Path $repoRoot '.venv\Scripts\python.exe') -ErrorAction SilentlyContinue).Path

if (-not (Test-Path -LiteralPath $pidFile -PathType Leaf)) {
    Write-Host 'No launcher-managed demo server is running.'
    exit 0
}

$serverPid = [int](Get-Content -LiteralPath $pidFile -Raw)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid" -ErrorAction SilentlyContinue
if (-not $process) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Host 'Removed a stale demo process marker; no server was running.'
    exit 0
}

$expectedScript = Join-Path $repoRoot 'lead-core\backend\run_app.py'
if (-not $python -or $process.ExecutablePath -ne $python -or $process.CommandLine -notlike "*$expectedScript*") {
    throw "PID $serverPid no longer identifies this repository's demo server. No process was stopped."
}

Stop-Process -Id $serverPid -Force
Remove-Item -LiteralPath $pidFile -Force
Write-Host 'Precog SOC demo server stopped.'
