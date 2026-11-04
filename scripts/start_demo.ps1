param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$runScript = Join-Path $repoRoot 'lead-core\backend\run_app.py'
$envFile = Join-Path $repoRoot '.env'
$dataDir = Join-Path $repoRoot 'lead-core\backend\data'
$pidFile = Join-Path $dataDir 'demo-server.pid'
$stdoutLog = Join-Path $dataDir 'demo-server.stdout.log'
$stderrLog = Join-Path $dataDir 'demo-server.stderr.log'
$port = 5000
$baseUrl = "http://127.0.0.1:$port"
$healthUrl = "$baseUrl/api/x/health"
$demoUrl = "$baseUrl/"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python. Create .venv and install lead-core/backend/requirements.txt first."
}
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw ".env is missing. Copy .env.example to .env and set SECRET_KEY and ADMIN_PASSWORD before starting the demo."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'lead-core\backend\web_dist\index.html') -PathType Leaf)) {
    throw "The built web app is missing. Run .\.venv\Scripts\python.exe deploy\build_web_bundle.py first."
}

$env:HOST = '127.0.0.1'
$env:PORT = "$port"
$env:DATA_MODE = 'live'
$env:COOKIE_SECURE = '0'

try {
    $existingHealth = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($existingHealth.status -ne 'ok') { throw 'The existing server returned an unhealthy response.' }
    if ($existingHealth.data_mode -ne 'live') { throw "Port $port is already serving data_mode '$($existingHealth.data_mode)'. Stop that server before starting the live demo." }
    Write-Host "Precog SOC is already running with all modules on $baseUrl"
    if (-not $NoBrowser) { Start-Process $demoUrl }
    exit 0
} catch [System.Net.WebException] {
    # No server answered on the demo port. Start the local replay process below.
} catch {
    if ($_.Exception.Message -like "Port $port is already serving*") { throw }
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $port is occupied by another process. Stop it or change the port before running the demo." }
}

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$process = Start-Process -FilePath $python -ArgumentList ('"' + $runScript + '"') -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
Set-Content -LiteralPath $pidFile -Value $process.Id -NoNewline

for ($attempt = 0; $attempt -lt 75; $attempt += 1) {
    Start-Sleep -Seconds 1
    $runningProcess = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
    if (-not $runningProcess) {
        throw "The backend stopped during startup. See $stderrLog and $stdoutLog."
    }
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq 'ok' -and $health.data_mode -eq 'live') {
            Write-Host "Precog SOC is ready at $demoUrl"
            Write-Host "Modules: $($health.hooks -join ', ')"
            Write-Host "Stop the demo with: .\scripts\stop_demo.ps1"
            if (-not $NoBrowser) { Start-Process $demoUrl }
            exit 0
        }
    } catch {
        # The server is still starting. Keep polling until its health route answers.
    }
}

throw "The backend did not become ready within 75 seconds. See $stderrLog and $stdoutLog."
