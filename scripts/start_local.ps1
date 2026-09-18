param(
    [int]$Port = 8765,
    [switch]$Open,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
$baseUrl = "http://127.0.0.1:$Port"
$healthUrl = "$baseUrl/api/health"

function Test-HealthyService {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return ($health.status -eq "PASS" -and $health.external_effects -eq "DISABLED")
    } catch {
        return $false
    }
}

if (Test-HealthyService) {
    Write-Output "Syzygy Creative Studio is already healthy at $baseUrl"
    if ($Open) {
        Start-Process $baseUrl
    }
    exit 0
}

if ($CheckOnly) {
    Write-Error "Syzygy Creative Studio is not healthy at $baseUrl"
    exit 1
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python 3.11+ was not found on PATH."
}

Write-Output "Starting loopback-only Syzygy Creative Studio at $baseUrl"
Write-Output "Press Ctrl+C in this terminal to stop the local service."
Push-Location $projectRoot
try {
    & $python.Source "apps/creative-studio/app.py" --host "127.0.0.1" --port $Port
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
