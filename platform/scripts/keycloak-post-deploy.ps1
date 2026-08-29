#!/usr/bin/env pwsh
# ============================================================
# i3 Platform — Keycloak Post-Deploy Script
# PURPOSE:
#   After Keycloak is running and the i3 realm is imported,
#   this script:
#     1. Regenerates client secrets for all 5 OIDC clients
#     2. Writes each secret into OpenBao at i3/auth/<client>
#     3. Verifies the Keycloak realm health endpoint
#
# PREREQUISITES:
#   - Keycloak pod is running in i3-auth namespace
#   - OpenBao is unsealed (run unseal-openbao.ps1 first)
#   - OPENBAO_ROOT_TOKEN is set (or use an admin token)
#   - oc is configured against i3-platform
#
# USAGE:
#   . .\platform\scripts\load-env.ps1
#   $env:OPENBAO_ROOT_TOKEN = "<token>"
#   .\platform\scripts\keycloak-post-deploy.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$kcNs     = "i3-auth"
$baoNs    = "i3-security"
$baoPod   = "openbao-0"
$oc       = "oc"
$realm    = "i3"

# Keycloak admin credentials (change from default on first run)
$kcAdminUser = "admin"
$kcAdminPass = $env:KEYCLOAK_ADMIN_PASSWORD
if (-not $kcAdminPass) {
    Write-Warning "KEYCLOAK_ADMIN_PASSWORD not set. Using default 'admin' — change this immediately!"
    $kcAdminPass = "admin"
}

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

Step "Finding Keycloak pod..."
$kcPod = (& $oc get pods -n $kcNs -l "app=keycloak" --no-headers 2>&1 |
    Where-Object { $_ -match "Running" } |
    Select-Object -First 1) -split '\s+' | Select-Object -First 1

if (-not $kcPod) {
    Write-Error "No running Keycloak pod found in $kcNs. Deploy Keycloak first."
}
OK "Keycloak pod: $kcPod"

# ---------------------------------------------------------------------------
Banner "1 — Obtain Keycloak Admin Token"

$tokenResult = & $oc exec -n $kcNs $kcPod -- `
    curl -s -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" `
    -H "Content-Type: application/x-www-form-urlencoded" `
    -d "username=$kcAdminUser&password=$kcAdminPass&grant_type=password&client_id=admin-cli" `
    2>&1

$tokenJson = ($tokenResult -join "") | ConvertFrom-Json
$adminToken = $tokenJson.access_token
if (-not $adminToken) {
    Write-Host "Token response: $tokenResult" -ForegroundColor Red
    Write-Error "Could not obtain Keycloak admin token. Check admin credentials."
}
OK "Admin token acquired (expires in $($tokenJson.expires_in)s)"

# ---------------------------------------------------------------------------
Banner "2 — Regenerate Client Secrets"

$clients = @(
    "evalos-spa",
    "admissions-widget",
    "ai-lab-workbench",
    "directus-cms",
    "litellm-service"
)

$clientSecrets = @{}

foreach ($clientId in $clients) {
    Step "Getting internal ID for client: $clientId"

    $clientListRaw = & $oc exec -n $kcNs $kcPod -- `
        curl -s "http://localhost:8080/admin/realms/$realm/clients?clientId=$clientId" `
        -H "Authorization: Bearer $adminToken" 2>&1

    $clientList = ($clientListRaw -join "") | ConvertFrom-Json
    if (-not $clientList -or $clientList.Count -eq 0) {
        Warn "Client '$clientId' not found in realm '$realm'. Skipping."
        continue
    }

    $internalId = $clientList[0].id

    # Regenerate secret
    $secretRaw = & $oc exec -n $kcNs $kcPod -- `
        curl -s -X POST "http://localhost:8080/admin/realms/$realm/clients/$internalId/client-secret" `
        -H "Authorization: Bearer $adminToken" `
        -H "Content-Type: application/json" 2>&1

    $secretObj = ($secretRaw -join "") | ConvertFrom-Json
    $secret = $secretObj.value

    if (-not $secret) {
        Warn "Could not regenerate secret for $clientId (response: $secretRaw)"
        continue
    }

    $clientSecrets[$clientId] = $secret
    OK "Client '$clientId' secret regenerated"
}

# ---------------------------------------------------------------------------
Banner "3 — Write Client Secrets to OpenBao"

foreach ($clientId in $clientSecrets.Keys) {
    $secret = $clientSecrets[$clientId]
    Step "Writing secret for $clientId to OpenBao..."

    & $oc exec -n $baoNs $baoPod `
        --env="VAULT_TOKEN=$env:OPENBAO_ROOT_TOKEN" `
        -- bao kv put -mount=i3 "auth/keycloak-clients" `
        "${clientId}_secret=$secret" 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    OK "Written: i3/auth/keycloak-clients/${clientId}_secret"
}

# ---------------------------------------------------------------------------
Banner "4 — Verify Realm Health"

$health = & $oc exec -n $kcNs $kcPod -- `
    curl -s "http://localhost:8080/realms/$realm/.well-known/openid-configuration" 2>&1

$healthJson = ($health -join "") | ConvertFrom-Json
if ($healthJson.issuer) {
    OK "Realm '$realm' is live. Issuer: $($healthJson.issuer)"
} else {
    Warn "Could not verify realm health. Response: $health"
}

# ---------------------------------------------------------------------------
Banner "Keycloak Post-Deploy Complete"

Write-Host ""
Write-Host "Client secrets written to OpenBao at: i3/auth/keycloak-clients" -ForegroundColor White
foreach ($c in $clientSecrets.Keys) {
    Write-Host "  [OK] ${c}_secret" -ForegroundColor Green
}
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Change the Keycloak admin password from the console:" -ForegroundColor Yellow
Write-Host "     https://keycloak.i3technologies.co.ke → Manage → Users → admin → Credentials" -ForegroundColor Yellow
Write-Host "  2. Store the new admin password in OpenBao:" -ForegroundColor Yellow
Write-Host "     oc exec -n i3-security openbao-0 -- bao kv put -mount=i3 auth/keycloak admin_password=<new-password>" -ForegroundColor Yellow
Write-Host "  3. Run rclone-secret.ps1 to configure SeaweedFS DR sync:" -ForegroundColor Yellow
Write-Host "     .\platform\scripts\rclone-secret.ps1" -ForegroundColor Yellow
