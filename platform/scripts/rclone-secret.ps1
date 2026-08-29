#!/usr/bin/env pwsh
# ============================================================
# i3 Platform — SeaweedFS → IBM COS rclone Secret Creator
# PURPOSE:
#   Creates the `rclone-secrets` Kubernetes Secret in the
#   i3-ott namespace, which the seaweedfs-cos-dr-sync CronJob
#   uses to authenticate with both SeaweedFS S3 API and IBM COS.
#
# PREREQUISITES:
#   - SeaweedFS Filer is running (seaweedfs-filer service is up)
#   - IBM COS HMAC keys are available (from .env / TF state)
#   - oc is configured against i3-platform cluster
#   - . .\platform\scripts\load-env.ps1 has been run
#
# USAGE:
#   . .\platform\scripts\load-env.ps1
#   .\platform\scripts\rclone-secret.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ns  = "i3-ott"
$oc  = "oc"

function Banner([string]$msg) {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Cyan
}
function Step([string]$msg) { Write-Host "[>] $msg" -ForegroundColor Yellow }
function OK([string]$msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "  [WARN] $msg" -ForegroundColor Magenta }

# ---------------------------------------------------------------------------
Banner "Preflight"

@("TF_COS_ACCESS_KEY", "TF_COS_SECRET_KEY") | ForEach-Object {
    if (-not (Get-Item "env:$_" -ErrorAction SilentlyContinue)) {
        Write-Error "$_ not set. Run: . .\platform\scripts\load-env.ps1"
    }
    OK "$_ is set"
}

# Resolve SeaweedFS S3 ClusterIP
Step "Resolving seaweedfs-s3 service cluster IP..."
$seaweedIP = & $oc get svc seaweedfs-s3 -n $ns -o jsonpath='{.spec.clusterIP}' 2>&1
if ($LASTEXITCODE -ne 0 -or -not $seaweedIP) {
    Warn "seaweedfs-s3 service not found — using placeholder. Update after SeaweedFS is deployed."
    $seaweedIP = "seaweedfs-s3.i3-ott.svc.cluster.local"
}
OK "SeaweedFS S3 endpoint: http://${seaweedIP}:8333"

# ---------------------------------------------------------------------------
Banner "Building rclone.conf"

# NOTE: SeaweedFS S3 credentials — default is no-auth on cluster network.
# If you enabled SeaweedFS IAM, change access_key_id / secret_access_key below.
$rcloneConf = @"
[seaweedfs]
type = s3
provider = Other
endpoint = http://${seaweedIP}:8333
access_key_id = seaweedfs-internal
secret_access_key = seaweedfs-internal
no_check_bucket = true
force_path_style = true

[cos]
type = s3
provider = IBMCOS
env_auth = false
access_key_id = $($env:TF_COS_ACCESS_KEY)
secret_access_key = $($env:TF_COS_SECRET_KEY)
endpoint = s3.eu-de.cloud-object-storage.appdomain.cloud
location_constraint = eu-de-smart
region = eu-de
"@

Step "Rendered rclone.conf (access keys redacted in this output)"

# ---------------------------------------------------------------------------
Banner "Creating / Updating Kubernetes Secret"

# Delete existing secret if present
$existing = & $oc get secret rclone-secrets -n $ns 2>&1
if ($LASTEXITCODE -eq 0) {
    Warn "Secret 'rclone-secrets' already exists — deleting and recreating..."
    & $oc delete secret rclone-secrets -n $ns | Out-Null
}

# Write conf to a temp file (never committed)
$tmpConf = Join-Path $env:TEMP "rclone.conf"
Set-Content -Path $tmpConf -Value $rcloneConf -Encoding UTF8 -NoNewline

# Create secret
& $oc create secret generic rclone-secrets `
    --from-file=rclone.conf=$tmpConf `
    -n $ns

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create rclone-secrets Secret."
}
OK "Secret 'rclone-secrets' created in namespace '$ns'"

# Clean up temp file
Remove-Item $tmpConf -Force
OK "Temp file cleaned up"

# ---------------------------------------------------------------------------
Banner "Verify"

$secretData = & $oc get secret rclone-secrets -n $ns -o jsonpath='{.data.rclone\.conf}' 2>&1
if ($secretData) {
    OK "Secret exists and contains rclone.conf data"
} else {
    Warn "Could not verify secret data — check: oc describe secret rclone-secrets -n $ns"
}

# ---------------------------------------------------------------------------
Banner "Complete"

Write-Host ""
Write-Host "rclone-secrets created in: $ns" -ForegroundColor White
Write-Host ""
Write-Host "Test the sync manually:" -ForegroundColor Cyan
Write-Host "  make dr-test" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or trigger an immediate DR sync:" -ForegroundColor Cyan
Write-Host "  make dr-backup" -ForegroundColor Yellow
Write-Host ""
Write-Host "The CronJob will run automatically at 02:00 UTC daily." -ForegroundColor Green
