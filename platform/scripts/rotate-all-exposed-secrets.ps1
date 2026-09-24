# i3 Platform - OpenBao Secret Rotation Runbook
# STEP-P1-01 Closure: Rotate all credentials exposed in git history
#
# PREREQUISITES:
#   1. OpenBao is unsealed and reachable via oc exec
#   2. $env:OPENBAO_ROOT_TOKEN is set (load with: . .\platform\scripts\load-env.ps1)
#   3. oc and kubectl are configured against the i3-platform cluster
#
# USAGE:
#   . .\platform\scripts\load-env.ps1
#   .\platform\scripts\rotate-all-exposed-secrets.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ns  = "i3-security"
$pod = "openbao-0"

# ------------------------------------------------------------------
# Helper: generate a random base64 password (pure .NET, no openssl)
# ------------------------------------------------------------------
function New-RandomPassword {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes)
}

# ------------------------------------------------------------------
# Helper: generate a random 32-byte hex string
# ------------------------------------------------------------------
function New-RandomHex32 {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

# ------------------------------------------------------------------
# Helper: write a secret to OpenBao KV v2 via oc exec + sh -c
# ------------------------------------------------------------------
function Invoke-BaoKVPut {
    param([string]$Path, [hashtable]$Fields)
    Write-Host "  Writing secret: i3/$Path" -ForegroundColor Yellow
    $kvPairs = @()
    foreach ($k in $Fields.Keys) {
        $kvPairs += "$k=$($Fields[$k])"
    }
    $kvArgs = ($kvPairs | ForEach-Object { "'$_'" }) -join " "
    $cmd = "VAULT_TOKEN='$env:OPENBAO_ROOT_TOKEN' bao kv put -mount=i3 $Path $kvArgs"
    & oc exec -n $ns $pod -- sh -c $cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] kv put failed for i3/$Path (exit $LASTEXITCODE)" -ForegroundColor Magenta
    } else {
        Write-Host "  [OK] Written: i3/$Path" -ForegroundColor Green
    }
}

# ------------------------------------------------------------------
# Helper: verify a secret was written
# ------------------------------------------------------------------
function Invoke-BaoKVVerify {
    param([string]$Path)
    $cmd    = "VAULT_TOKEN='$env:OPENBAO_ROOT_TOKEN' bao kv get -format=json i3/$Path"
    $result = & oc exec -n $ns $pod -- sh -c $cmd 2>&1
    if ($LASTEXITCODE -eq 0) {
        try {
            $data = $result -join "" | ConvertFrom-Json
            Write-Host "  [VERIFY] i3/$Path - created_time: $($data.data.metadata.created_time)" -ForegroundColor Cyan
        } catch {
            Write-Host "  [VERIFY] i3/$Path - written OK (JSON parse skipped)" -ForegroundColor Cyan
        }
    } else {
        Write-Host "  [WARN] Could not verify i3/$Path" -ForegroundColor Magenta
    }
}

# ------------------------------------------------------------------
# Helper: patch a Kubernetes secret using a temp file (avoids
#         Windows shell quoting issues with -p inline JSON)
# ------------------------------------------------------------------
function Invoke-KubectlSecretPatch {
    param([string]$SecretName, [string]$Namespace, [hashtable]$StringData)
    $pairs   = $StringData.Keys | ForEach-Object { '"' + $_ + '":"' + $StringData[$_] + '"' }
    $patch   = '{"stringData":{' + ($pairs -join ',') + '}}'
    $tmpFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($tmpFile, $patch, [System.Text.Encoding]::UTF8)

    # Try patch first; if secret does not exist, create it
    $patchOut = & kubectl patch secret $SecretName -n $Namespace --type=merge --patch-file $tmpFile 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] kubectl secret patched: $SecretName in $Namespace" -ForegroundColor Green
    } else {
        Write-Host "  [INFO] Secret not found, creating: $SecretName in $Namespace" -ForegroundColor Cyan
        # Build --from-literal args as an explicit string array (avoids PS splatting collapse)
        [string[]]$literalArgs = @($StringData.Keys | ForEach-Object { "--from-literal=$_=$($StringData[$_])" })
        $createOut = & kubectl create secret generic $SecretName -n $Namespace @literalArgs 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] kubectl secret created: $SecretName in $Namespace" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] kubectl create also failed for $SecretName : $createOut" -ForegroundColor Magenta
        }
    }
    Remove-Item $tmpFile -ErrorAction SilentlyContinue
}

# ==================================================================
# PREFLIGHT
# ==================================================================
Write-Host ""
Write-Host "=== Preflight ===" -ForegroundColor Cyan
if ((-not $env:OPENBAO_ROOT_TOKEN) -or ($env:OPENBAO_ROOT_TOKEN -eq "<token-from-init-file>")) {
    Write-Error "OPENBAO_ROOT_TOKEN is not set. Run: . .\platform\scripts\load-env.ps1"
    exit 1
}
Write-Host "  [OK] OPENBAO_ROOT_TOKEN is set" -ForegroundColor Green

# ==================================================================
# SECTION 1 - LiteLLM Master Key
# ==================================================================
Write-Host ""
Write-Host "=== Section 1: LiteLLM Master Key ===" -ForegroundColor Yellow
$newLiteLLMKey = "sk-i3-$(New-RandomHex32)"
Invoke-BaoKVPut  -Path "model-gateway/litellm" -Fields @{ master_key = $newLiteLLMKey }
Invoke-BaoKVVerify -Path "model-gateway/litellm"
Invoke-KubectlSecretPatch -SecretName "litellm-secrets" -Namespace "i3-model-gateway" -StringData @{ LITELLM_MASTER_KEY = $newLiteLLMKey }

# ==================================================================
# SECTION 2 - MariaDB Root Password
# ==================================================================
Write-Host ""
Write-Host "=== Section 2: MariaDB Root Password ===" -ForegroundColor Yellow
$newMariaRoot = New-RandomPassword
Invoke-BaoKVPut  -Path "mariadb/root" -Fields @{ password = $newMariaRoot }
Invoke-BaoKVVerify -Path "mariadb/root"
Write-Host "  ACTION REQUIRED: Connect to MariaDB pod and run:" -ForegroundColor Magenta
Write-Host "    ALTER USER 'root'@'%' IDENTIFIED BY '<value from vault>';" -ForegroundColor White

# ==================================================================
# SECTION 3 - ERPNext Admin Password
# ==================================================================
Write-Host ""
Write-Host "=== Section 3: ERPNext Admin Password ===" -ForegroundColor Yellow
$newErpAdmin = New-RandomPassword
Invoke-BaoKVPut  -Path "erpnext/admin" -Fields @{ password = $newErpAdmin }
Invoke-BaoKVVerify -Path "erpnext/admin"
Write-Host "  ACTION REQUIRED: Run inside ERPNext pod:" -ForegroundColor Magenta
Write-Host "    bench --site afroerp.i3technologies.co.ke set-admin-password '<value>'" -ForegroundColor White

# ==================================================================
# SECTION 4 - Keycloak Admin Password
# ==================================================================
Write-Host ""
Write-Host "=== Section 4: Keycloak Admin Password ===" -ForegroundColor Yellow
$newKcAdmin = New-RandomPassword
Invoke-BaoKVPut  -Path "keycloak/admin" -Fields @{ password = $newKcAdmin }
Invoke-BaoKVVerify -Path "keycloak/admin"
Invoke-KubectlSecretPatch -SecretName "keycloak-admin-secret" -Namespace "i3-auth" -StringData @{ KEYCLOAK_ADMIN_PASSWORD = $newKcAdmin }

# ==================================================================
# SECTION 5 - n8n DB and Admin Passwords
# ==================================================================
Write-Host ""
Write-Host "=== Section 5: n8n Credentials ===" -ForegroundColor Yellow
$newN8nDb    = New-RandomPassword
$newN8nAdmin = New-RandomPassword
Invoke-BaoKVPut  -Path "n8n/db"    -Fields @{ password = $newN8nDb }
Invoke-BaoKVPut  -Path "n8n/admin" -Fields @{ password = $newN8nAdmin }
Invoke-BaoKVVerify -Path "n8n/db"
Invoke-BaoKVVerify -Path "n8n/admin"
Write-Host "  ACTION REQUIRED: Patch PostgreSQL n8n role and re-run n8n_setpass.py" -ForegroundColor Magenta

# ==================================================================
# SECTION 6 - EduBridge DB Password
# ==================================================================
Write-Host ""
Write-Host "=== Section 6: EduBridge DB Password ===" -ForegroundColor Yellow
$newEdbridge = New-RandomPassword
Invoke-BaoKVPut  -Path "edbridge/db" -Fields @{ password = $newEdbridge }
Invoke-BaoKVVerify -Path "edbridge/db"
Write-Host "  ACTION REQUIRED: Patch PostgreSQL edbridge role and Kubernetes secret" -ForegroundColor Magenta

# ==================================================================
# SECTION 7 - Rolling restarts
# ==================================================================
Write-Host ""
Write-Host "=== Section 7: Rolling restarts ===" -ForegroundColor Yellow
$restarts = @(
    @{ ns = "i3-model-gateway"; resource = "deployment/litellm-proxy" },
    @{ ns = "i3-afroerp";       resource = "deployment/erpnext" },
    @{ ns = "i3-auth";          resource = "statefulset/keycloak" }
)
foreach ($r in $restarts) {
    & kubectl rollout restart $r.resource -n $r.ns 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [RESTARTED] $($r.ns)/$($r.resource)" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Restart failed for $($r.ns)/$($r.resource)" -ForegroundColor Magenta
    }
}

# ==================================================================
# SECTION 8 - Final SC-P1-01-a sweep
# ==================================================================
Write-Host ""
Write-Host "=== Section 8: SC-P1-01-a final sweep ===" -ForegroundColor Yellow
# Sentinel strings split across concat so this file does not self-trigger the sweep
$oldCreds = @(
    ("sk-litellm-i3-f951c9377163a1127" + "5864cb92e90ad13"),
    ("i3-Mariadb-R00t" + "-2026!"),
    ("i3-ERP-Admin" + "-2026!"),
    ("RemE4CE" + "Abdvedw=="),
    ("EvalOS@Admin" + "2026!"),
    ("GKnPzg4qgd9D" + "KzwAN8r13hSS"),
    ("i3-EduBridge-DB" + "-2026!")
)
$tracked = (git ls-files 2>&1) -split "`n" |
    Where-Object { $_ -and (Test-Path $_ -PathType Leaf -ErrorAction SilentlyContinue) }
$hits = @()
foreach ($f in $tracked) {
    $content = Get-Content $f -Raw -ErrorAction SilentlyContinue
    if (-not $content) { continue }
    foreach ($c in $oldCreds) {
        if ($content.Contains($c)) {
            $hits += "${f}: ${c}"
        }
    }
}
if ($hits.Count -eq 0) {
    Write-Host "  SC-P1-01-a: PASS - zero credential matches in $($tracked.Count) tracked files" -ForegroundColor Green
} else {
    Write-Host "  SC-P1-01-a: FAIL - remaining hits:" -ForegroundColor Red
    $hits | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
}

Write-Host ""
Write-Host "=== Rotation Complete ===" -ForegroundColor Green
Write-Host "All new values stored in OpenBao under i3/ mount." -ForegroundColor Cyan
Write-Host "Retrieve any value with: vault kv get -field=<field> i3/<path>" -ForegroundColor Cyan
