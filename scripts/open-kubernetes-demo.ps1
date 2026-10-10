<#
.SYNOPSIS
    Resumes the existing Kubernetes (kind) demo and opens it in the browser.
    Unlike start-kubernetes-demo.ps1 this never re-applies manifests, so settings made
    on the cluster (including the Gemini API key) are left untouched.
#>

$ErrorActionPreference = "Stop"
$clusterName = "billing"
$node = "$clusterName-control-plane"
$ns = "billing"
$ctx = "kind-$clusterName"

Write-Host "Checking Docker..." -ForegroundColor Cyan
try {
    docker info --format '{{.ServerVersion}}' | Out-Null
} catch {
    Write-Error "Docker doesn't seem to be running. Start Docker Desktop and try again."
    exit 1
}

$clusters = kind get clusters
if ($clusters -notcontains $clusterName) {
    Write-Error "No '$clusterName' cluster found. Run scripts/start-kubernetes-demo.ps1 first (one-time setup), then scripts/set-gemini-key.ps1."
    exit 1
}

$running = docker inspect -f '{{.State.Running}}' $node
if ($running -ne "true") {
    Write-Host "Starting the cluster node..." -ForegroundColor Cyan
    docker start $node | Out-Null
}

Write-Host "Waiting for the cluster API..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    kubectl --context $ctx get nodes 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $ok) { Write-Error "Cluster API did not come up."; exit 1 }

# Scale back up (a no-op if already running).
Write-Host "Starting services..." -ForegroundColor Cyan
foreach ($d in "postgres", "kafka", "opa", "backend", "worker", "frontend") {
    kubectl --context $ctx scale deployment/$d --replicas=1 -n $ns | Out-Null
}
foreach ($d in "postgres", "kafka", "opa", "backend", "worker", "frontend") {
    kubectl --context $ctx rollout status deployment/$d -n $ns --timeout=300s | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$d did not become ready in time. Check 'kubectl get pods -n $ns'." }
}

Write-Host "Waiting for the backend to become healthy..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        if ((Invoke-RestMethod -Uri "http://localhost:8000/ready" -TimeoutSec 3).status -eq "ready") { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if ($ready) { Write-Host "Backend is ready." -ForegroundColor Green }
else { Write-Warning "Backend did not report healthy in time. Check 'kubectl get pods -n $ns'." }

$url = "http://localhost:5173"
Write-Host ""
Write-Host "Corporate Billing Platform is running on Kubernetes: $url" -ForegroundColor Green
Start-Process $url
