<#
.SYNOPSIS
    Phase 3 Pre-flight Cluster Status Check
.DESCRIPTION
    Authenticates to IBM Cloud via API key, downloads a static admin kubeconfig
    (no exec-plugin, no credential prompts, no hangs), then checks all P3-GATE
    resources on the cluster.
.EXAMPLE
    $env:IBMCLOUD_API_KEY="<key>"
    .\platform\scripts\p3-preflight-check.ps1
#>

param(
    [string]$ClusterName   = "i3-platform",
    [string]$CloudRegion   = "eu-de",
    [string]$ResourceGroup = "i3-production",
    [int]$KubectlTimeout   = 15
)

$ErrorActionPreference = "Continue"
$REPO = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $REPO

$SEP = "-" * 60

# Helper: run kubectl with a hard timeout so it never hangs
function kc {
    $job = Start-Job -ScriptBlock {
        param($a, $t)
        kubectl --request-timeout="${t}s" @a 2>$null
    } -ArgumentList @(,$args), $using:KubectlTimeout
    $done = Wait-Job $job -Timeout $KubectlTimeout
    if ($done) {
        $out = Receive-Job $job
        Remove-Job $job -Force
        return $out
    } else {
        Stop-Job $job
        Remove-Job $job -Force
        return $null
    }
}

# Helper: show a labelled resource or "(not found)"
function Show-Resource([string]$Label, [string[]]$KubectlArgs) {
    Write-Host "  $Label" -ForegroundColor DarkGray
    $out = kc @KubectlArgs
    if ($out) {
        $out -split "`n" | Where-Object { $_ -match '\S' } |
            ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Host "    (not found or timed out)" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  PHASE 3 PRE-FLIGHT CHECK" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

# =============================================================
# STEP 1 -- IBM Cloud API Key Login
# =============================================================
Write-Host "CLUSTER AUTH" -ForegroundColor Yellow
Write-Host ""

if (-not $env:IBMCLOUD_API_KEY) {
    Write-Host "  IBMCLOUD_API_KEY not set." -ForegroundColor DarkYellow
    Write-Host '  Run:  $env:IBMCLOUD_API_KEY="<your-api-key>"  then re-run this script.' -ForegroundColor Cyan
    exit 1
}

Write-Host "  Logging in with API key ..."
ibmcloud login --apikey $env:IBMCLOUD_API_KEY -r $CloudRegion -g $ResourceGroup --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: ibmcloud login failed." -ForegroundColor Red
    exit 1
}
Write-Host "  OK -- logged in as $(ibmcloud account show --output json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty owner_userid 2>$null)" -ForegroundColor Green

# =============================================================
# STEP 2 -- Download static admin kubeconfig (no exec-plugin)
# =============================================================
Write-Host ""
Write-Host "  Downloading admin kubeconfig (static token, no exec-plugin) ..."

# Write to a temp file so we don't pollute the default kubeconfig
$tmpKube = Join-Path $env:TEMP "i3-platform-admin.yaml"
$env:KUBECONFIG = $tmpKube

ibmcloud ks cluster config --cluster $ClusterName --admin --output yaml 2>$null |
    Out-File -FilePath $tmpKube -Encoding utf8

if (-not (Test-Path $tmpKube) -or (Get-Item $tmpKube).Length -lt 100) {
    # Fallback: standard (non-admin) config
    Write-Host "  --admin flag not available, falling back to standard config ..." -ForegroundColor DarkYellow
    Remove-Item $tmpKube -ErrorAction SilentlyContinue
    $env:KUBECONFIG = ""
    ibmcloud ks cluster config --cluster $ClusterName
    # Manually inject IAM token to replace exec-plugin entry
    $tok = ibmcloud iam oauth-tokens --output json 2>$null | ConvertFrom-Json
    if ($tok -and $tok.iam_token) {
        $raw = $tok.iam_token -replace '^Bearer\s+',''
        # Find the user entry name from current context and overwrite its token
        $ctx  = kubectl config current-context 2>$null
        $user = kubectl config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.user}" 2>$null
        if ($user) {
            kubectl config set-credentials $user --token=$raw 2>$null | Out-Null
            Write-Host "  IAM token injected for user: $user" -ForegroundColor Green
        }
    }
} else {
    Write-Host "  Admin kubeconfig written to $tmpKube" -ForegroundColor Green
}

# Quick connectivity test with timeout
Write-Host "  Testing connectivity (${KubectlTimeout}s timeout) ..."
$nodes = kc get nodes --no-headers
if ($nodes) {
    $n = ($nodes -split "`n" | Where-Object { $_ -match '\S' }).Count
    Write-Host "  CONNECTED -- $n node(s)" -ForegroundColor Green
} else {
    Write-Host "  WARNING: kubectl timed out or returned nothing -- resources below may show (not found)" -ForegroundColor DarkYellow
    Write-Host "  If this persists, run:  ibmcloud ks cluster config --cluster $ClusterName --admin" -ForegroundColor DarkGray
}

# =============================================================
# P3-GATE-01 -- LiteLLM Redis Cache (disk check, no cluster needed)
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-01 -- LiteLLM Redis Cache" -ForegroundColor Yellow
$diskCfg = Get-Content "platform/model-gateway/litellm/litellm-config-oss.yaml" -Raw -ErrorAction SilentlyContinue
if ($diskCfg -match "cache:\s*true") {
    Write-Host "  PASS: cache: true confirmed in litellm-config-oss.yaml" -ForegroundColor Green
} else {
    Write-Host "  MISS: cache: true not found" -ForegroundColor DarkYellow
}

# =============================================================
# P3-GATE-05 -- peer0-i3tech
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-05 -- peer0-i3tech pod" -ForegroundColor Yellow
Show-Resource "pods in i3-ford (app=peer0-i3tech):" @("get","pod","-n","i3-ford","-l","app=peer0-i3tech","--no-headers")

# =============================================================
# P3-GATE-06 -- Fabric prerequisites
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-06 -- Fabric orderer prerequisites" -ForegroundColor Yellow
Show-Resource "statefulset/orderer:"      @("get","statefulset","orderer","-n","i3-ford","--no-headers")
Show-Resource "svc/ford-ca:"              @("get","svc","ford-ca","-n","i3-ford","--no-headers")
Show-Resource "sa/ford-sa:"              @("get","sa","ford-sa","-n","i3-ford","--no-headers")
Show-Resource "pvc/peer0-i3tech-pvc:"    @("get","pvc","peer0-i3tech-pvc","-n","i3-ford","--no-headers")
Show-Resource "secret/orderer-msp:"      @("get","secret","orderer-msp","-n","i3-ford","--no-headers")
Show-Resource "job/ford-channel-join:"   @("get","job","ford-channel-join","-n","i3-ford","--no-headers")
Show-Resource "job/ford-chaincode-deploy:" @("get","job","ford-chaincode-deploy","-n","i3-ford","--no-headers")
Show-Resource "cm/ford-chaincode-files-raw:" @("get","configmap","ford-chaincode-files-raw","-n","i3-ford","--no-headers")

# =============================================================
# P3-GATE-07 -- ford-api
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-07 -- ford-api" -ForegroundColor Yellow
Show-Resource "deployment/ford-api:" @("get","deployment","ford-api","-n","i3-ford","--no-headers")

# =============================================================
# P3-GATE-08 -- ford-ussd
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-08 -- ford-ussd USSD Bridge" -ForegroundColor Yellow
Show-Resource "namespace/i3-ussd:"               @("get","namespace","i3-ussd","--no-headers")
Show-Resource "deployment/ford-ussd in i3-ussd:" @("get","deployment","ford-ussd","-n","i3-ussd","--no-headers")
Show-Resource "pods (app=ford-ussd):"            @("get","pod","-n","i3-ussd","-l","app=ford-ussd","--no-headers")

# =============================================================
# P3-GATE-04 -- Kafka Topics
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-04 -- Kafka Topics" -ForegroundColor Yellow
Show-Resource "kafkatopics in i3-kafka:" @("get","kafkatopic","-n","i3-kafka","--no-headers")

# =============================================================
# P3-GATE-09 -- Tekton Pipeline
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-09 -- Tekton Pipeline" -ForegroundColor Yellow
Show-Resource "pipeline/i3-build-pipeline:" @("get","pipeline","i3-build-pipeline","-n","i3-tekton","--no-headers")

# =============================================================
# Summary
# =============================================================
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  GATES CODE-PASS (no cluster action needed):" -ForegroundColor White
Write-Host "    P3-GATE-01  P3-GATE-03  P3-GATE-04  P3-GATE-09  P3-GATE-15" -ForegroundColor Green
Write-Host ""
Write-Host "  GATES NEEDING CLUSTER EXECUTION:" -ForegroundColor White
Write-Host "    P3-GATE-05/06/07  peer + orderer + ford-channel + chaincode" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-08        ford-ussd USSD bridge" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-02        LiteLLM cache warm-up" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-10/11/12/13/14  testing gates" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "  Next:  .\platform\scripts\p3-run-gates.ps1" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
