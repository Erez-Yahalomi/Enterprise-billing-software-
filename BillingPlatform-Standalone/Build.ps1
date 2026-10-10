<#
.SYNOPSIS
    Builds BillingPlatform.exe (no Docker needed to run it).

    Everything lands inside this folder: tools\ (portable Node.js + a private Python venv),
    build\ (intermediate files) and dist\BillingPlatform\ (the finished app). The original
    project folders (backend, frontend, ...) are only read, never modified.
#>

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$project = Split-Path -Parent $here
Set-Location $here

$nodeVersion = "v24.21.0"
$toolsDir = Join-Path $here "tools"
$nodeDir = Join-Path $toolsDir "node-$nodeVersion-win-x64"
$venvDir = Join-Path $toolsDir "venv"
$buildDir = Join-Path $here "build"
$feSrc = Join-Path $buildDir "frontend-src"
$feOut = Join-Path $buildDir "frontend"
$seedDir = Join-Path $buildDir "seed_data"
New-Item -ItemType Directory -Force $toolsDir, $buildDir | Out-Null

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# ---- 1. Portable Node.js (only used to build the web UI) --------------------------------
if (-not (Test-Path (Join-Path $nodeDir "node.exe"))) {
    Step "Downloading portable Node.js $nodeVersion (build-time only)"
    $zipName = "node-$nodeVersion-win-x64.zip"
    $zip = Join-Path $toolsDir $zipName
    $base = "https://nodejs.org/dist/$nodeVersion"
    Invoke-WebRequest "$base/$zipName" -OutFile $zip -UseBasicParsing
    $sums = (Invoke-WebRequest "$base/SHASUMS256.txt" -UseBasicParsing).Content
    $expected = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($zipName) } | Select-Object -First 1).Split(" ")[0].Trim()
    $actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $expected) { Remove-Item $zip; throw "Node.js download failed its SHA-256 check." }
    Expand-Archive $zip -DestinationPath $toolsDir -Force
    Remove-Item $zip
}
$env:PATH = "$nodeDir;$env:PATH"

# ---- 2. Private Python venv with PyInstaller --------------------------------------------
$py = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Step "Creating private Python environment"
    python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "Python 3 is required to build (python.org). Not needed to RUN the finished app." }
}
Step "Installing Python packages"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r (Join-Path $here "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# ---- 3. Build the React frontend into build\frontend -------------------------------------
Step "Building the web UI"
if (Test-Path $feSrc) { Remove-Item -Recurse -Force $feSrc }
New-Item -ItemType Directory -Force $feSrc | Out-Null
$srcFrontend = Join-Path $project "frontend"
foreach ($item in "src", "index.html", "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts") {
    Copy-Item (Join-Path $srcFrontend $item) $feSrc -Recurse
}
Push-Location $feSrc
try {
    & (Join-Path $nodeDir "npm.cmd") ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    if (Test-Path $feOut) { Remove-Item -Recurse -Force $feOut }
    & (Join-Path $nodeDir "npx.cmd") vite build --outDir $feOut --emptyOutDir
    if ($LASTEXITCODE -ne 0) { throw "vite build failed" }
} finally { Pop-Location }

# ---- 4. Pre-generate the demo database so first launch is instant ------------------------
Step "Generating the demo database (a few minutes, done once at build time)"
if (Test-Path $seedDir) { Remove-Item -Recurse -Force $seedDir }
$env:BILLING_DATA_DIR = $seedDir
& $py (Join-Path $here "launcher.py") --make-seed
if ($LASTEXITCODE -ne 0) { throw "demo data generation failed" }
Remove-Item Env:\BILLING_DATA_DIR
# Don't ship the settings template/WAL leftovers; the app recreates them.
Remove-Item (Join-Path $seedDir ".env"), (Join-Path $seedDir "billing.db-wal"), (Join-Path $seedDir "billing.db-shm") -ErrorAction SilentlyContinue

# ---- 5. Package with PyInstaller ---------------------------------------------------------
Step "Packaging BillingPlatform.exe"
& $py -m PyInstaller --noconfirm --clean --distpath (Join-Path $here "dist") --workpath (Join-Path $buildDir "pyi") (Join-Path $here "BillingPlatform.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $here "dist\BillingPlatform\BillingPlatform.exe"
Write-Host "`nDone: $exe" -ForegroundColor Green
Write-Host "Double-click it (or Start-BillingPlatform.bat) to run. No Docker required." -ForegroundColor Green
