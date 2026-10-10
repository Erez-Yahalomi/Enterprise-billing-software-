<#
.SYNOPSIS
    Stops the Kubernetes (kind) demo.
.PARAMETER RemoveData
    Deletes the whole kind cluster, including the Postgres and lake volumes
    (fresh start next time). Without it, workloads are scaled to zero and volumes are kept.
#>
param(
    [switch]$RemoveData
)

$ErrorActionPreference = "Stop"
$clusterName = "billing"

if ($RemoveData) {
    Write-Host "Deleting kind cluster '$clusterName' and all its volumes..." -ForegroundColor Cyan
    kind delete cluster --name $clusterName
} else {
    Write-Host "Scaling workloads to zero (volumes preserved)..." -ForegroundColor Cyan
    kubectl scale deployment --all --replicas=0 -n billing --context "kind-$clusterName"
    Write-Host "Re-run scripts/start-kubernetes-demo.ps1 to bring it back (it re-applies replicas)." -ForegroundColor DarkGray
}
