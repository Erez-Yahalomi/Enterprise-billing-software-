<#
.SYNOPSIS
    Asks for a free Gemini API key in a small window (with the link and steps to get one),
    stores it in the cluster's billing-secrets Secret, and restarts the backend.
    The key is never written to disk or printed.
.PARAMETER OnlyIfMissing
    First-run mode (used by start-kubernetes-demo.ps1): do nothing if a key is already set
    or the user already answered the prompt once on this PC.
#>
param(
    [switch]$OnlyIfMissing
)

$ErrorActionPreference = "Stop"
$ns = "billing"
$url = "https://aistudio.google.com/apikey"
$markerDir = Join-Path $env:LOCALAPPDATA "BillingPlatform"
$marker = Join-Path $markerDir "k8s-gemini-setup-done"

if ($OnlyIfMissing) {
    if (Test-Path $marker) { return }
    $b64 = $null
    try { $b64 = kubectl get secret billing-secrets -n $ns -o "jsonpath={.data.GEMINI_API_KEY}" 2>$null } catch { }
    if ($b64) { return }   # a key is already stored in the cluster
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "Corporate Billing Platform - Gemini API key"
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false; $form.MinimizeBox = $false
$form.ClientSize = New-Object System.Drawing.Size(560, 360)
$form.TopMost = $true
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$title = New-Object System.Windows.Forms.Label
$title.Text = "Set up the AI Assistant (free)"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(16, 14); $title.AutoSize = $true

$steps = New-Object System.Windows.Forms.Label
$steps.Text = "The AI Assistant works best with Google's Gemini model, which has a free tier.`r`n" +
    "To get your free API key:`r`n`r`n" +
    "  1. Open the link below and sign in with any Google account.`r`n" +
    "  2. Click `"Create API key`" (choose any project if asked).`r`n" +
    "  3. Copy the key (it starts with `"AIza`") and paste it in the box below.`r`n`r`n" +
    "You can skip this; the app then uses a simpler built-in assistant. Run`r`n" +
    "scripts\set-gemini-key.ps1 any time to add the key later."
$steps.Location = New-Object System.Drawing.Point(16, 48); $steps.Size = New-Object System.Drawing.Size(528, 170)

$link = New-Object System.Windows.Forms.LinkLabel
$link.Text = $url
$link.Location = New-Object System.Drawing.Point(16, 222); $link.AutoSize = $true
$link.Add_LinkClicked({ Start-Process $url })

$lbl = New-Object System.Windows.Forms.Label
$lbl.Text = "Paste your Gemini API key here:"
$lbl.Location = New-Object System.Drawing.Point(16, 256); $lbl.AutoSize = $true

$box = New-Object System.Windows.Forms.TextBox
$box.Location = New-Object System.Drawing.Point(16, 280); $box.Size = New-Object System.Drawing.Size(528, 26)
$box.Font = New-Object System.Drawing.Font("Consolas", 10)

$save = New-Object System.Windows.Forms.Button
$save.Text = "Save key"; $save.Size = New-Object System.Drawing.Size(110, 32)
$save.Location = New-Object System.Drawing.Point(434, 316)
$skip = New-Object System.Windows.Forms.Button
$skip.Text = "Skip for now"; $skip.Size = New-Object System.Drawing.Size(110, 32)
$skip.Location = New-Object System.Drawing.Point(314, 316)
$skip.DialogResult = [System.Windows.Forms.DialogResult]::Cancel

$save.Add_Click({
    $k = $box.Text.Trim().Trim('"').Trim("'")
    if ($k.Length -lt 20 -or $k -match '\s') {
        [System.Windows.Forms.MessageBox]::Show(
            "A Gemini API key is a single long string of letters and numbers (usually starting with AIza). Please copy it again, or click Skip.",
            "That does not look like a key", "OK", "Warning") | Out-Null
        return
    }
    $form.Tag = $k
    $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
})
$form.AcceptButton = $save; $form.CancelButton = $skip
$form.Controls.AddRange(@($title, $steps, $link, $lbl, $box, $save, $skip))

$result = $form.ShowDialog()
$key = $form.Tag
New-Item -ItemType Directory -Force $markerDir | Out-Null
Set-Content -Path $marker -Value "asked" -Encoding ascii   # don't ask again on this PC

if ($result -ne [System.Windows.Forms.DialogResult]::OK -or -not $key) {
    Write-Host "Skipped - using the built-in assistant. Run scripts\set-gemini-key.ps1 later to add a key." -ForegroundColor Yellow
    return
}

$patch = @{ stringData = @{ GEMINI_API_KEY = $key } } | ConvertTo-Json -Compress
$tmp = New-TemporaryFile
try {
    Set-Content -Path $tmp -Value $patch -Encoding ascii
    kubectl patch secret billing-secrets -n $ns --patch-file $tmp | Out-Null
} finally {
    Remove-Item $tmp -Force
}
if ($LASTEXITCODE -ne 0) { Write-Error "kubectl patch failed."; exit 1 }

kubectl rollout restart deployment/backend -n $ns | Out-Null
kubectl rollout status deployment/backend -n $ns --timeout=300s | Out-Null
Write-Host "Gemini key saved - the AI Assistant will use Gemini." -ForegroundColor Green
