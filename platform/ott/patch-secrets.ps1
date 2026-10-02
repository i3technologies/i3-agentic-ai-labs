#!/usr/bin/env pwsh
# ============================================================
# i3 OTT Platform — Pre-Deploy Secret Patcher
# Run this BEFORE applying any Kubernetes manifests.
#
# What it does:
#   1. Fetches every secret from OpenBao (i3/ott/*)
#   2. Patches each Kubernetes Secret object in the i3-ott namespace
#   3. Generates a cryptographically random OME API token if vault
#      doesn't have one yet, and writes it back to vault
#   4. Triggers a rollout restart of all affected deployments
#
# Prerequisites:
#   - oc login already done
#   - bao CLI configured (BAO_ADDR + BAO_TOKEN env vars set)
#   - Namespace i3-ott exists
#
# Usage:
#   $env:BAO_ADDR  = "https://openbao.i3-platform.svc.cluster.local:8200"
#   $env:BAO_TOKEN = "<your-vault-token>"
#   .\platform\ott\patch-secrets.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$NS = "i3-ott"

function Write-Step([string]$msg) {
    Write-Host "`n── $msg" -ForegroundColor Cyan
}

function Write-OK([string]$msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}

function Write-Fail([string]$msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
}

# ── Helper: read a field from OpenBao KV v2 ──────────────────
function Get-VaultField([string]$path, [string]$field) {
    $raw = bao kv get -format=json $path 2>$null | ConvertFrom-Json
    if (-not $raw) { return $null }
    return $raw.data.data.$field
}

# ── Helper: generate a cryptographically random hex string ───
function New-RandomToken([int]$bytes = 32) {
    $buf = [byte[]]::new($bytes)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buf)
    return [System.BitConverter]::ToString($buf).Replace("-","").ToLower()
}

# ── 0. Pre-flight checks ──────────────────────────────────────
Write-Step "Pre-flight checks"

$ocWho = oc whoami 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Not logged in to OpenShift. Run: oc login --token=<TOKEN> --server=<API_URL>"
    exit 1
}
Write-OK "oc logged in as: $ocWho"

$nsExists = oc get ns $NS --no-headers 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Namespace $NS not found — creating it"
    oc create ns $NS | Out-Null
}
Write-OK "Namespace $NS ready"

if (-not $env:BAO_ADDR -or -not $env:BAO_TOKEN) {
    Write-Warn "BAO_ADDR or BAO_TOKEN not set — secrets will be patched with placeholder prompts"
    $vaultAvailable = $false
} else {
    $vaultAvailable = $true
    Write-OK "OpenBao configured: $env:BAO_ADDR"
}

# ── 1. TV Portal — DIRECTUS_TOKEN ────────────────────────────
Write-Step "Patching tv-portal-secrets (DIRECTUS_TOKEN)"
if ($vaultAvailable) {
    $dirToken = Get-VaultField "i3/ott/directus" "static_token"
    if (-not $dirToken) { $dirToken = Get-VaultField "i3/ott/directus" "admin_token" }
} else {
    $dirToken = Read-Host "  Enter DIRECTUS_TOKEN (or press Enter to skip)"
}
if ($dirToken) {
    $patch = @{ stringData = @{ DIRECTUS_TOKEN = $dirToken } } | ConvertTo-Json -Compress
    oc patch secret tv-portal-secrets -n $NS -p $patch | Out-Null
    Write-OK "tv-portal-secrets patched"
} else {
    Write-Warn "tv-portal-secrets DIRECTUS_TOKEN not patched — tv-portal VOD will show empty catalogue"
}

# ── 2. Directus CMS — all 8 fields ───────────────────────────
Write-Step "Patching directus-secrets (8 fields)"
if ($vaultAvailable) {
    $dVault = @{
        DB_USER               = Get-VaultField "i3/ott/directus" "db_user"
        DB_PASSWORD           = Get-VaultField "i3/ott/directus" "db_password"
        KEY                   = Get-VaultField "i3/ott/directus" "key"
        SECRET                = Get-VaultField "i3/ott/directus" "secret"
        ADMIN_PASSWORD        = Get-VaultField "i3/ott/directus" "admin_password"
        KEYCLOAK_CLIENT_SECRET= Get-VaultField "i3/ott/directus" "keycloak_client_secret"
        SEAWEEDFS_ACCESS_KEY  = Get-VaultField "i3/ott/directus" "seaweedfs_access_key"
        SEAWEEDFS_SECRET_KEY  = Get-VaultField "i3/ott/directus" "seaweedfs_secret_key"
    }
    $missingFields = $dVault.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key }
    if ($missingFields) {
        Write-Warn "Missing vault fields: $($missingFields -join ', ') — patch these manually"
    }
    $patch = @{ stringData = $dVault } | ConvertTo-Json -Compress
    oc patch secret directus-secrets -n $NS -p $patch | Out-Null
    Write-OK "directus-secrets patched"
} else {
    Write-Warn "Skipping directus-secrets — set BAO_ADDR/BAO_TOKEN or patch manually:"
    Write-Host '  oc patch secret directus-secrets -n i3-ott -p '"'"'{"stringData":{"DB_USER":"...","DB_PASSWORD":"...","KEY":"...","SECRET":"...","ADMIN_PASSWORD":"...","KEYCLOAK_CLIENT_SECRET":"...","SEAWEEDFS_ACCESS_KEY":"...","SEAWEEDFS_SECRET_KEY":"..."}}'"'" -ForegroundColor Gray
}

# ── 3. n8n secrets ───────────────────────────────────────────
Write-Step "Patching n8n-secrets"
if ($vaultAvailable) {
    $n8nVault = @{
        DB_USER        = Get-VaultField "i3/ott/n8n" "db_user"
        DB_PASSWORD    = Get-VaultField "i3/ott/n8n" "db_password"
        ENCRYPTION_KEY = Get-VaultField "i3/ott/n8n" "encryption_key"
    }
    $patch = @{ stringData = $n8nVault } | ConvertTo-Json -Compress
    oc patch secret n8n-secrets -n $NS -p $patch | Out-Null
    Write-OK "n8n-secrets patched"
} else {
    Write-Warn "Skipping n8n-secrets — patch manually with vault values"
}

# ── 4. OME API token — generate if missing ───────────────────
Write-Step "Patching ome-api-secret (OME REST API token)"
$omeToken = $null
if ($vaultAvailable) {
    $omeToken = Get-VaultField "i3/ott/ome" "api_token"
}
if (-not $omeToken) {
    Write-Warn "OME API token not in vault — generating a new 32-byte random token"
    $omeToken = New-RandomToken 32
    if ($vaultAvailable) {
        bao kv put i3/ott/ome api_token=$omeToken | Out-Null
        Write-OK "New OME token written to vault at i3/ott/ome"
    }
}
$patch = @{ stringData = @{ OME_API_TOKEN = $omeToken } } | ConvertTo-Json -Compress
oc patch secret ome-api-secret -n $NS -p $patch | Out-Null
Write-OK "ome-api-secret patched"

# ── 5. OTT Pipeline secrets ───────────────────────────────────
Write-Step "Patching ott-pipeline-secrets"
$pipeSecret = $null
if ($vaultAvailable) {
    $pipeSecret = Get-VaultField "i3/ott/pipeline" "webhook_secret"
}
if (-not $pipeSecret) {
    Write-Warn "Pipeline webhook secret not in vault — generating new 32-byte token"
    $pipeSecret = New-RandomToken 32
    if ($vaultAvailable) {
        bao kv put i3/ott/pipeline webhook_secret=$pipeSecret | Out-Null
        Write-OK "Pipeline webhook secret written to vault at i3/ott/pipeline"
    }
}
if ($vaultAvailable) {
    $pVault = @{
        PIPELINE_WEBHOOK_SECRET = $pipeSecret
        AWS_ACCESS_KEY_ID       = Get-VaultField "i3/ott/pipeline" "aws_access_key_id"
        AWS_SECRET_ACCESS_KEY   = Get-VaultField "i3/ott/pipeline" "aws_secret_access_key"
        DIRECTUS_TOKEN          = Get-VaultField "i3/ott/directus" "static_token"
    }
    $patch = @{ stringData = $pVault } | ConvertTo-Json -Compress
    oc patch secret ott-pipeline-secrets -n $NS -p $patch | Out-Null
    Write-OK "ott-pipeline-secrets patched"
} else {
    $patch = @{ stringData = @{ PIPELINE_WEBHOOK_SECRET = $pipeSecret } } | ConvertTo-Json -Compress
    oc patch secret ott-pipeline-secrets -n $NS -p $patch | Out-Null
    Write-Warn "ott-pipeline-secrets: only PIPELINE_WEBHOOK_SECRET set. Patch AWS keys manually."
}

# ── 6. Restart deployments to pick up new secrets ────────────
Write-Step "Rolling restart of all OTT deployments"
$deployments = @("tv-portal","directus","n8n","ott-pipeline")
foreach ($dep in $deployments) {
    $exists = oc get deployment $dep -n $NS --no-headers 2>&1
    if ($LASTEXITCODE -eq 0) {
        oc rollout restart deployment/$dep -n $NS | Out-Null
        Write-OK "Restarted $dep"
    } else {
        Write-Warn "$dep deployment not found yet — will pick up secrets on first deploy"
    }
}

Write-Host "`n✅ Secret patching complete. Run .\platform\ott\deploy-ott.ps1 to deploy." -ForegroundColor Green
