#!/usr/bin/env pwsh
# ============================================================
# i3 OTT Platform — OpenBao Vault Provisioning Script
#
# Creates the KV v2 paths and seeds placeholder secrets for
# the OTT namespace. Run ONCE per environment (idempotent).
#
# Prerequisites:
#   - bao CLI installed + BAO_ADDR / BAO_TOKEN set
#   - KV v2 secrets engine enabled at "i3/"
#
# Usage:
#   $env:BAO_ADDR  = "https://openbao.i3-platform.svc.cluster.local:8200"
#   $env:BAO_TOKEN = "<vault-root-or-admin-token>"
#   .\platform\ott\vault-provision-ott.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) { Write-Host "`n── $msg" -ForegroundColor Cyan }
function Write-OK([string]$msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }

function New-RandomToken([int]$bytes = 32) {
    $buf = [byte[]]::new($bytes)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buf)
    return [System.BitConverter]::ToString($buf).Replace("-","").ToLower()
}

# ── Pre-flight ────────────────────────────────────────────────
if (-not $env:BAO_ADDR -or -not $env:BAO_TOKEN) {
    Write-Host "ERROR: BAO_ADDR and BAO_TOKEN must be set." -ForegroundColor Red
    exit 1
}

Write-Host "`n i3 OTT — OpenBao Vault Provisioning" -ForegroundColor Cyan
Write-Host "  Vault: $env:BAO_ADDR`n" -ForegroundColor Gray

# ── Enable KV v2 if not already enabled ──────────────────────
Write-Step "Ensuring KV v2 engine at i3/"
$mounted = bao secrets list -format=json 2>$null | ConvertFrom-Json
if ($mounted."i3/") {
    Write-OK "i3/ secrets engine already mounted"
} else {
    bao secrets enable -path=i3 kv-v2 | Out-Null
    Write-OK "Enabled KV v2 at i3/"
}

# ── Write OTT Vault Policy ────────────────────────────────────
Write-Step "Writing ott vault policy"
$policy = @"
# OTT namespace policy — allows read on all i3/ott/* paths
path "i3/data/ott/*" {
  capabilities = ["read"]
}
path "i3/metadata/ott/*" {
  capabilities = ["read", "list"]
}
"@
$policyFile = [System.IO.Path]::GetTempFileName()
Set-Content $policyFile $policy
bao policy write ott $policyFile | Out-Null
Remove-Item $policyFile
Write-OK "Policy 'ott' written"

# ── Seed i3/ott/directus ─────────────────────────────────────
Write-Step "Seeding i3/ott/directus"
$existing = bao kv get i3/ott/directus 2>$null
if (-not $existing) {
    bao kv put i3/ott/directus `
        db_user="directus" `
        db_password="$(New-RandomToken 16)" `
        key="$(New-RandomToken 32)" `
        secret="$(New-RandomToken 32)" `
        admin_password="$(New-RandomToken 16)" `
        static_token="$(New-RandomToken 32)" `
        keycloak_client_secret="$(New-RandomToken 32)" `
        seaweedfs_access_key="$(New-RandomToken 16)" `
        seaweedfs_secret_key="$(New-RandomToken 32)" | Out-Null
    Write-OK "i3/ott/directus seeded with generated values"
    Write-Warn "UPDATE the real DB credentials after cluster database is provisioned!"
} else {
    Write-Warn "i3/ott/directus already exists — not overwriting. Use 'bao kv patch' to update fields."
}

# ── Seed i3/ott/n8n ──────────────────────────────────────────
Write-Step "Seeding i3/ott/n8n"
$existing = bao kv get i3/ott/n8n 2>$null
if (-not $existing) {
    bao kv put i3/ott/n8n `
        db_user="n8n" `
        db_password="$(New-RandomToken 16)" `
        encryption_key="$(New-RandomToken 32)" | Out-Null
    Write-OK "i3/ott/n8n seeded"
    Write-Warn "UPDATE real DB credentials after n8n database is provisioned!"
} else {
    Write-Warn "i3/ott/n8n already exists — skipping"
}

# ── Seed i3/ott/ome ──────────────────────────────────────────
Write-Step "Seeding i3/ott/ome"
$existing = bao kv get i3/ott/ome 2>$null
if (-not $existing) {
    $omeToken = New-RandomToken 32
    bao kv put i3/ott/ome api_token="$omeToken" | Out-Null
    Write-OK "i3/ott/ome seeded — api_token: $omeToken"
} else {
    Write-Warn "i3/ott/ome already exists — skipping"
}

# ── Seed i3/ott/pipeline ─────────────────────────────────────
Write-Step "Seeding i3/ott/pipeline"
$existing = bao kv get i3/ott/pipeline 2>$null
if (-not $existing) {
    bao kv put i3/ott/pipeline `
        webhook_secret="$(New-RandomToken 32)" `
        aws_access_key_id="REPLACE_WITH_SEAWEEDFS_HMAC_KEY" `
        aws_secret_access_key="REPLACE_WITH_SEAWEEDFS_HMAC_SECRET" | Out-Null
    Write-OK "i3/ott/pipeline seeded"
    Write-Warn "UPDATE aws_access_key_id and aws_secret_access_key with real SeaweedFS HMAC credentials"
} else {
    Write-Warn "i3/ott/pipeline already exists — skipping"
}

# ── Create Kubernetes ServiceAccount + VaultAuth binding ─────
Write-Step "Vault Auth — Kubernetes backend binding for OTT"
Write-Warn "Ensure Kubernetes auth backend is enabled in vault:"
Write-Host "  bao auth enable kubernetes" -ForegroundColor Gray
Write-Warn "Then bind the ott policy to the i3-ott service account:"
Write-Host @"
  bao write auth/kubernetes/role/ott `
    bound_service_account_names="default" `
    bound_service_account_namespaces="i3-ott" `
    policies="ott" `
    ttl="1h"
"@ -ForegroundColor Gray

# ── Summary of all vault paths ───────────────────────────────
Write-Step "Provisioned Vault Paths"
Write-Host ""
Write-Host "  Path                         Fields" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  i3/ott/directus              db_user, db_password, key, secret," -ForegroundColor Green
Write-Host "                               admin_password, static_token," -ForegroundColor Green
Write-Host "                               keycloak_client_secret," -ForegroundColor Green
Write-Host "                               seaweedfs_access_key, seaweedfs_secret_key" -ForegroundColor Green
Write-Host "  i3/ott/n8n                   db_user, db_password, encryption_key" -ForegroundColor Green
Write-Host "  i3/ott/ome                   api_token" -ForegroundColor Green
Write-Host "  i3/ott/pipeline              webhook_secret, aws_access_key_id," -ForegroundColor Green
Write-Host "                               aws_secret_access_key" -ForegroundColor Green
Write-Host ""
Write-Host "✅ Vault provisioning complete. Next: run patch-secrets.ps1" -ForegroundColor Green
