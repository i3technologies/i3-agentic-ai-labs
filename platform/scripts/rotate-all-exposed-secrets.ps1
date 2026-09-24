# i3 Platform — OpenBao Secret Rotation Runbook
# STEP-P1-01 Closure: Rotate all credentials exposed in git history
#
# PREREQUISITES:
#   1. OpenBao is unsealed:  vault status
#   2. VAULT_TOKEN is set:   export VAULT_TOKEN=<root-or-rotation-token>
#   3. oc/kubectl configured against the i3-platform cluster
#
# EXECUTION ORDER: run each section sequentially.
# After all rotations, re-deploy affected pods (see §6).
#
# HC-6: All passwords generated with openssl rand — never reuse old values.
# HC-7: Verify no old values remain in code after rotation (SC-P1-01-a sweep at §7).

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Helpers ─────────────────────────────────────────────────────────────────
function VaultPut([string]$path, [hashtable]$fields) {
    $args = @("kv", "put", "-mount=i3", $path)
    foreach ($k in $fields.Keys) { $args += "$k=$($fields[$k])" }
    vault @args
    Write-Host "  [OK] Written: i3/$path" -ForegroundColor Green
}

function VaultVerify([string]$path) {
    $out = vault kv get -format=json "i3/$path" 2>&1 | ConvertFrom-Json
    Write-Host "  [VERIFY] i3/$path — created_time: $($out.data.metadata.created_time)" -ForegroundColor Cyan
}

function NewPassword { openssl rand -base64 24 }
function NewHex32    { openssl rand -hex 32 }

# ─────────────────────────────────────────────────────────────────────────────
# §1 — LiteLLM Master Key (EXPOSED: sk-litellm-i3-f951…)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §1 LiteLLM Master Key ===" -ForegroundColor Yellow
$newLiteLLMKey = "sk-i3-$(NewHex32)"
VaultPut "model-gateway/litellm" @{ master_key = $newLiteLLMKey }
VaultVerify "model-gateway/litellm"
# Patch the Kubernetes secret
$liteLLMPatch = @{ stringData = @{ LITELLM_MASTER_KEY = $newLiteLLMKey } } | ConvertTo-Json -Compress
kubectl patch secret litellm-secrets -n i3-model-gateway --type=merge -p $liteLLMPatch
Write-Host "  [OK] kubectl secret patched" -ForegroundColor Green

# ─────────────────────────────────────────────────────────────────────────────
# §2 — MariaDB Root Password (EXPOSED: REDACTED-mariadb-root)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §2 MariaDB Root Password ===" -ForegroundColor Yellow
$newMariaRoot = NewPassword
VaultPut "mariadb/root" @{ password = $newMariaRoot }
VaultVerify "mariadb/root"
Write-Host "  ACTION: Connect to MariaDB pod and run:"
Write-Host "    ALTER USER 'root'@'%' IDENTIFIED BY '<new-value-from-vault>';"
Write-Host "  Then patch afroerp/erpnext secrets that reference this value."

# ─────────────────────────────────────────────────────────────────────────────
# §3 — ERPNext Admin Password (EXPOSED: REDACTED-erp-admin)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §3 ERPNext Admin Password ===" -ForegroundColor Yellow
$newErpAdmin = NewPassword
VaultPut "erpnext/admin" @{ password = $newErpAdmin }
VaultVerify "erpnext/admin"
Write-Host "  ACTION: Log into ERPNext and reset the Administrator password via:"
Write-Host "    bench --site afroerp.i3technologies.co.ke set-admin-password '<value>'"

# ─────────────────────────────────────────────────────────────────────────────
# §4 — Keycloak Admin Password (EXPOSED: REDACTED-keycloak-admin)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §4 Keycloak Admin Password ===" -ForegroundColor Yellow
$newKcAdmin = NewPassword
VaultPut "keycloak/admin" @{ password = $newKcAdmin }
VaultVerify "keycloak/admin"
Write-Host "  ACTION: Update Keycloak admin password via:"
Write-Host "    kubectl exec -n i3-auth deployment/keycloak -- /opt/keycloak/bin/kcadm.sh"
Write-Host "    set-password --username admin --new-password '<value>' --realm master"

# ─────────────────────────────────────────────────────────────────────────────
# §5 — n8n DB Password (EXPOSED: REDACTED-n8n-db)
#       n8n Admin Password (EXPOSED: REDACTED-n8n-admin)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §5 n8n Credentials ===" -ForegroundColor Yellow
$newN8nDb    = NewPassword
$newN8nAdmin = NewPassword
VaultPut "n8n/db"    @{ password = $newN8nDb }
VaultPut "n8n/admin" @{ password = $newN8nAdmin }
VaultVerify "n8n/db"
VaultVerify "n8n/admin"
Write-Host "  ACTION: Patch PostgreSQL n8n role password and Kubernetes secret."
Write-Host "  Then run platform/scripts/n8n_setpass.py with N8N_ADMIN_PASS set."

# ─────────────────────────────────────────────────────────────────────────────
# §6 — EduBridge DB Password (EXPOSED: REDACTED-edbridge-db)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §6 EduBridge DB Password ===" -ForegroundColor Yellow
$newEdbridge = NewPassword
VaultPut "edbridge/db" @{ password = $newEdbridge }
VaultVerify "edbridge/db"
Write-Host "  ACTION: Patch PostgreSQL edbridge role password and Kubernetes secret."

# ─────────────────────────────────────────────────────────────────────────────
# §7 — Pod restart after rotation
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §7 Rolling restart affected pods ===" -ForegroundColor Yellow
$restarts = @(
  @("i3-model-gateway", "deployment/litellm-proxy"),
  @("i3-afroerp",       "deployment/erpnext"),
  @("i3-auth",          "deployment/keycloak")
)
foreach ($r in $restarts) {
  kubectl rollout restart $r[1] -n $r[0]
  Write-Host "  [RESTARTED] $($r[0])/$($r[1])"
}

# ─────────────────────────────────────────────────────────────────────────────
# §8 — SC-P1-01-a sensor sweep (verify no old values remain)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== §8 SC-P1-01-a final sweep ===" -ForegroundColor Yellow
Write-Host "Run this after all rotations and restarts:"
Write-Host ""
Write-Host @'
git grep -rE \
  "sk-litellm-i3-f951|i3-Mariadb-R00t-2026|i3-ERP-Admin-2026|REDACTED-keycloak-admin|EvalOS@Admin2026|REDACTED-n8n-db|i3-EduBridge-DB-2026|i3-PMaaS-DB-2026" \
  -- '*.sh' '*.js' '*.py' '*.json' '*.yaml' '*.ts' '*.html' '*.md'
# Expected: zero matches
'@

Write-Host "`n=== Rotation Runbook Complete ===" -ForegroundColor Green
Write-Host "IMPORTANT: Run 'git filter-repo' (or BFG Repo Cleaner) to purge old credential" -ForegroundColor Red
Write-Host "  values from git HISTORY before pushing this branch to any remote." -ForegroundColor Red
Write-Host "  Example (BFG):" -ForegroundColor Red
Write-Host "    bfg --replace-text replacements.txt ." -ForegroundColor Red
Write-Host "  Where replacements.txt lists each old credential value on a line." -ForegroundColor Red
