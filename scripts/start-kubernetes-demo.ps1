<#
.SYNOPSIS
    One-command Kubernetes (kind) startup for the Corporate Billing Platform demo.
    All storage is in-cluster (PersistentVolumeClaims) -- no cloud storage is used.
#>

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$clusterName = "billing"
$ns = "billing"

foreach ($tool in "docker", "kind", "kubectl") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "'$tool' not found on PATH. Install it and try again."
        exit 1
    }
}

Write-Host "Checking Docker..." -ForegroundColor Cyan
try {
    docker info --format '{{.ServerVersion}}' | Out-Null
} catch {
    Write-Error "Docker doesn't seem to be running. Start Docker Desktop and try again."
    exit 1
}

$existing = kind get clusters
if ($existing -notcontains $clusterName) {
    Write-Host "Creating kind cluster '$clusterName'..." -ForegroundColor Cyan
    kind create cluster --config kubernetes/kind/cluster.yaml
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "kind cluster '$clusterName' already exists - reusing it." -ForegroundColor Green
}
kubectl config use-context "kind-$clusterName" | Out-Null

Write-Host "Building images (backend, worker, frontend)..." -ForegroundColor Cyan
docker build -t billing-backend:local ./backend
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker build -t billing-worker:local -f worker/Dockerfile .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker build -t billing-frontend:local ./frontend
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Loading images into the cluster..." -ForegroundColor Cyan
kind load docker-image billing-backend:local billing-worker:local billing-frontend:local --name $clusterName
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Applying manifests..." -ForegroundColor Cyan
kubectl apply -f kubernetes/namespace.yaml
# Policies come straight from policies/opa so the rego has one source of truth.
kubectl create configmap opa-policies --from-file=policies/opa -n $ns --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f kubernetes/
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Waiting for deployments to become ready..." -ForegroundColor Cyan
foreach ($d in "postgres", "kafka", "opa", "backend", "worker", "frontend") {
    kubectl rollout status deployment/$d -n $ns --timeout=300s
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$d did not become ready in time. Check 'kubectl logs deploy/$d -n $ns'."
    }
}


# First run on this PC: ask for a free Gemini API key (link + steps shown in the window).
& (Join-Path $PSScriptRoot "set-gemini-key.ps1") -OnlyIfMissing

$demoHeaders = @{ "X-Tenant-Id" = "DEMO"; "X-Workspace-Type" = "demo" }
$hasDemoData = $false
try {
    $existingCustomers = Invoke-RestMethod -Uri "http://localhost:8000/customers" -Headers $demoHeaders -TimeoutSec 30
    $hasDemoData = @($existingCustomers).Count -gt 0
} catch { }

if ($hasDemoData) {
    Write-Host "Demo data already saved in the cluster volume - not regenerating." -ForegroundColor Green
} else {
    Write-Host "Seeding demo dataset (first run only)..." -ForegroundColor Cyan
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
Write-Host "Corporate Billing Platform is running on Kubernetes (kind):" -ForegroundColor Green
Write-Host "  Frontend: $url"
Write-Host "  Backend:  http://localhost:8000"
Write-Host ""
Start-Process $url
