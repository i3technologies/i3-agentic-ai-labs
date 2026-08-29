#!/usr/bin/env pwsh
# ============================================================
# i3 Platform — OpenBao Secret Population Script
# PURPOSE:
#   After OpenBao is unsealed and bootstrapped, this script
#   writes all application secrets into the KV v2 engine.
#   Run ONCE per fresh cluster deployment.
#
# PREREQUISITES:
#   1. OpenBao is unsealed and bootstrapped (RUNBOOK.md §2)
#   2. kubectl / oc is configured against i3-platform cluster
#   3. OPENBAO_ROOT_TOKEN is set (temporarily, revoke after this script)
#   4. All REPLACE_WITH_* values below are filled in
#
# USAGE:
#   . .\platform\scripts\load-env.ps1
#   $env:OPENBAO_ROOT_TOKEN = "<root-token-from-init>"
#   .\platform\scripts\populate-vault.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ns     = "i3-security"
$pod    = "openbao-0"
$oc     = "oc"
$thresh = 0

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

if (-not $env:OPENBAO_ROOT_TOKEN) {
    Write-Error "OPENBAO_ROOT_TOKEN not set. Get it from /tmp/openbao-init.json and set it:
  `$env:OPENBAO_ROOT_TOKEN = '<token>'"
}
OK "OPENBAO_ROOT_TOKEN is set"

# Helper: exec bao kv put
function BaoKVPut([string]$path, [hashtable]$kvPairs) {
    Step "Writing secret: $path"
    $args_list = @("exec", "-n", $ns, $pod, "--", "bao", "kv", "put",
        "-mount=i3", $path)
    foreach ($key in $kvPairs.Keys) {
        $args_list += "$key=$($kvPairs[$key])"
    }
    $env_bak = $env:VAULT_TOKEN
    $env:VAULT_TOKEN = $env:OPENBAO_ROOT_TOKEN

    $result = & $oc @args_list 2>&1
    if ($LASTEXITCODE -ne 0) {
        Warn "kv put failed for $path (exit $LASTEXITCODE)"
        Write-Host $result -ForegroundColor Gray
    } else {
        OK "Written: $path"
    }
    $env:VAULT_TOKEN = $env_bak
}

# Helper — inject token into exec environment via env var override
function BaoExec([string[]]$cmd) {
    & $oc exec -n $ns $pod `
        --env="VAULT_TOKEN=$env:OPENBAO_ROOT_TOKEN" `
        -- @cmd 2>&1
}

# Verify connectivity
Step "Checking OpenBao status..."
$status = BaoExec @("bao", "status", "-format=json") | ConvertFrom-Json
if ($status.sealed) {
    Write-Error "OpenBao is still sealed. Run: .\platform\scripts\unseal-openbao.ps1"
}
OK "OpenBao is unsealed. Version: $($status.version)"

# ---------------------------------------------------------------------------
Banner "1 — LiteLLM Proxy"
# Generate a random 32-char master key if not provided
$litellmMasterKey = $env:LITELLM_MASTER_KEY
if (-not $litellmMasterKey) {
    $litellmMasterKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
    Write-Host "  Generated random LiteLLM master key (save this!): $litellmMasterKey" -ForegroundColor Cyan
}
BaoKVPut "model-gateway/litellm" @{
    master_key  = $litellmMasterKey
    salt        = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | ForEach-Object {[char]$_}))
}

# ---------------------------------------------------------------------------
Banner "2 — Langfuse"
BaoKVPut "model-gateway/langfuse" @{
    nextauth_secret = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_}))
    salt            = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | ForEach-Object {[char]$_}))
    encryption_key  = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_}))
}

# ---------------------------------------------------------------------------
Banner "3 — Directus CMS"
BaoKVPut "ott/directus" @{
    key    = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_}))
    secret = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_}))
    admin_password = "REPLACE_WITH_STRONG_PASSWORD"
}

# ---------------------------------------------------------------------------
Banner "4 — n8n Encryption"
BaoKVPut "ott/n8n" @{
    encryption_key = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_}))
}

# ---------------------------------------------------------------------------
Banner "5 — Grafana Admin"
$grafanaPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 20 | ForEach-Object {[char]$_})
Write-Host "  Generated Grafana admin password (save this!): $grafanaPassword" -ForegroundColor Cyan
BaoKVPut "monitoring/grafana" @{
    admin_password = $grafanaPassword
}

# ---------------------------------------------------------------------------
Banner "6 — PostgreSQL Passwords (pgBouncer pool auth)"
BaoKVPut "data/postgres" @{
    pgbouncer_password = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object {[char]$_}))
    replication_password = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object {[char]$_}))
}

# ---------------------------------------------------------------------------
Banner "7 — Admissions Agent"
BaoKVPut "admissions/agent" @{
    chroma_token = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object {[char]$_}))
    odoo_api_key = "REPLACE_WITH_ODOO_API_KEY"
    n8n_webhook_token = (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object {[char]$_}))
}

# ---------------------------------------------------------------------------
Banner "8 — watsonx.ai Credentials"
BaoKVPut "model-gateway/watsonx" @{
    api_key    = $env:IBMCLOUD_API_KEY
    project_id = "REPLACE_WITH_WATSONX_PROJECT_ID"
    endpoint   = "https://eu-de.ml.cloud.ibm.com"
}

# ---------------------------------------------------------------------------
Banner "9 — IBM Container Registry"
BaoKVPut "gitops/registry" @{
    registry_url = "de.icr.io"
    namespace    = "i3-platform"
    api_key      = $env:IBMCLOUD_API_KEY
}

# ---------------------------------------------------------------------------
Banner "Vault Secret Population Complete"

Write-Host ""
Write-Host "Secrets written to OpenBao KV v2 mount 'i3':" -ForegroundColor White
Write-Host "  i3/model-gateway/litellm" -ForegroundColor Green
Write-Host "  i3/model-gateway/langfuse" -ForegroundColor Green
Write-Host "  i3/model-gateway/watsonx" -ForegroundColor Green
Write-Host "  i3/ott/directus" -ForegroundColor Green
Write-Host "  i3/ott/n8n" -ForegroundColor Green
Write-Host "  i3/monitoring/grafana" -ForegroundColor Green
Write-Host "  i3/data/postgres" -ForegroundColor Green
Write-Host "  i3/admissions/agent" -ForegroundColor Green
Write-Host "  i3/gitops/registry" -ForegroundColor Green
Write-Host ""
Write-Warning "⚠ Replace all 'REPLACE_WITH_*' placeholders:"
Write-Host "  i3/ott/directus         → admin_password" -ForegroundColor Magenta
Write-Host "  i3/admissions/agent     → odoo_api_key" -ForegroundColor Magenta
Write-Host "  i3/model-gateway/watsonx → project_id" -ForegroundColor Magenta
Write-Host ""
Write-Host "NEXT: Run Keycloak post-deploy to populate client secrets:" -ForegroundColor Cyan
Write-Host "  .\platform\scripts\keycloak-post-deploy.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Warning "⚠ REVOKE the root token after this script completes:"
Write-Host "  oc exec -n i3-security openbao-0 -- bao token revoke `$env:OPENBAO_ROOT_TOKEN" -ForegroundColor Yellow
Write-Host "  oc delete secret openbao-root-token -n i3-security" -ForegroundColor Yellow
