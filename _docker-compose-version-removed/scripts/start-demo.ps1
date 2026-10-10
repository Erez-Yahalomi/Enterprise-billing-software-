<#
.SYNOPSIS
    One-command startup for the Corporate Billing Platform demo.
#>

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Checking Docker..." -ForegroundColor Cyan
try {
    docker info --format '{{.ServerVersion}}' | Out-Null
} catch {
    Write-Error "Docker doesn't seem to be running. Start Docker Desktop and try again."
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
}

Write-Host "Building and starting services (postgres, kafka, opa, ollama, backend, worker, frontend)..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Pulling the local AI model in the background (first run only, a few minutes)..." -ForegroundColor Cyan
Write-Host "  The AI Assistant works immediately either way -- it uses a rule-based fallback" -ForegroundColor DarkGray
Write-Host "  until the model finishes downloading, then switches over automatically." -ForegroundColor DarkGray

Write-Host "Waiting for the backend to become healthy..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8000/ready" -TimeoutSec 3
        if ($resp.status -eq "ready") { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Warning "Backend did not report healthy in time. Check 'docker compose logs backend'."
} else {
    Write-Host "Backend is ready." -ForegroundColor Green
}

$demoHeaders = @{ "X-Tenant-Id" = "DEMO"; "X-Workspace-Type" = "demo" }
$hasDemoData = $false
try {
    $existing = Invoke-RestMethod -Uri "http://localhost:8000/customers" -Headers $demoHeaders -TimeoutSec 30
    $hasDemoData = @($existing).Count -gt 0
} catch { }

if ($hasDemoData) {
    Write-Host "Demo data already saved in the Docker volume - not regenerating." -ForegroundColor Green
} else {
    Write-Host "Seeding demo dataset (first run only; saved in the Docker volume)..." -ForegroundColor Cyan
    try {
        Invoke-RestMethod -Uri "http://localhost:8000/demo/generate" -Method Post -ContentType "application/json" `
            -Body '{"size":"medium","include_uci":false}' -Headers $demoHeaders -TimeoutSec 900 | Out-Null
        Write-Host "Demo data ready." -ForegroundColor Green
    } catch {
        Write-Warning "Could not seed demo data automatically. Use the Demo Data page in the app once it loads."
    }
}

$url = "http://localhost:5173"
Write-Host ""
Write-Host "Corporate Billing Platform is running:" -ForegroundColor Green
Write-Host "  Frontend: $url"
Write-Host "  Backend:  http://localhost:8000"
Write-Host ""
Start-Process $url
