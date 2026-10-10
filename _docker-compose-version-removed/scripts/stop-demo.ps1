<#
.SYNOPSIS
    Stops the Corporate Billing Platform demo stack.
.PARAMETER RemoveData
    Also removes the Postgres volume, the Parquet lake, and the downloaded Ollama model
    (fresh start next time, including re-downloading the local AI model).
#>
param(
    [switch]$RemoveData
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ($RemoveData) {
    Write-Host "Stopping services and removing volumes..." -ForegroundColor Cyan
    docker compose down -v
    Write-Host "Removing local data lake and downloaded Ollama model..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force ".\data\lake" -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force ".\data\ollama" -ErrorAction SilentlyContinue
} else {
    Write-Host "Stopping services (data preserved)..." -ForegroundColor Cyan
    docker compose down
}
