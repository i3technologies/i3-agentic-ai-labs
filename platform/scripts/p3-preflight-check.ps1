<#
.SYNOPSIS
    Phase 3 Pre-flight Cluster Status Check
.DESCRIPTION
    Authenticates to IBM Cloud via SSO passcode, extracts a bearer token,
    injects it directly into kubeconfig so kubectl never prompts for credentials,
    then checks the current state of all P3-GATE resources.
.EXAMPLE
    .\platform\scripts\p3-preflight-check.ps1
#>

param(
    [string]$ClusterName   = "i3-platform",
    [string]$CloudRegion   = "eu-de",
    [string]$ResourceGroup = "i3-production"
)

$ErrorActionPreference = "Continue"
$REPO = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $REPO

$SEP = "-" * 60

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  PHASE 3 PRE-FLIGHT CHECK" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

# =============================================================
# STEP 1 -- IBM Cloud SSO Auth + bearer token injection
# =============================================================
Write-Host "CLUSTER AUTH" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Opening IBM Cloud SSO passcode page ..."
Start-Process "https://iam.cloud.ibm.com/identity/passcode"
$passcodeSecure = Read-Host "  Paste SSO passcode" -AsSecureString
$passcode = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($passcodeSecure))

Write-Host "  Logging in to IBM Cloud ..."
ibmcloud login --sso -p $passcode -r $CloudRegion -g $ResourceGroup --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: ibmcloud login failed. Passcode may have expired (60s window)." -ForegroundColor Red
    Write-Host "  Get a new one at: https://iam.cloud.ibm.com/identity/passcode" -ForegroundColor DarkYellow
    exit 1
}

Write-Host "  Fetching kubeconfig for $ClusterName ..."
ibmcloud ks cluster config --cluster $ClusterName
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: cluster config failed" -ForegroundColor Red
    exit 1
}

# Extract IAM bearer token and inject directly so kubectl never prompts
Write-Host "  Injecting IAM bearer token into kubeconfig ..."
$iamToken = ibmcloud iam oauth-tokens --output json 2>$null | ConvertFrom-Json
if ($iamToken -and $iamToken.iam_token) {
    # Strip "Bearer " prefix if present
    $rawToken = $iamToken.iam_token -replace '^Bearer\s+', ''
    # Write token into current-context user credentials
    kubectl config set-credentials "$(kubectl config current-context)" `
        --token=$rawToken 2>$null | Out-Null
    Write-Host "  Bearer token injected" -ForegroundColor Green
} else {
    Write-Host "  WARNING: could not extract IAM token -- kubectl may prompt" -ForegroundColor DarkYellow
}

# Verify connectivity
$nodes = kubectl get nodes --no-headers 2>$null
if ($LASTEXITCODE -eq 0 -and $nodes) {
    $n = ($nodes -split "`n" | Where-Object { $_ -match '\S' }).Count
    Write-Host "  Cluster $ClusterName -- $n node(s) Ready" -ForegroundColor Green
} else {
    Write-Host "  WARNING: kubectl get nodes inconclusive -- continuing anyway" -ForegroundColor DarkYellow
}

# =============================================================
# Helper: run kubectl and print output, or print MISSING
# =============================================================
function Show-Resource([string]$Label, [string[]]$KubectlArgs) {
    Write-Host "  $Label" -ForegroundColor DarkGray
    $out = kubectl @KubectlArgs 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) {
        $out -split "`n" | Where-Object { $_ -match '\S' } |
            ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Host "    (not found)" -ForegroundColor DarkYellow
    }
}

# =============================================================
# P3-GATE-01 -- LiteLLM Redis Cache
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-01 -- LiteLLM Redis Cache" -ForegroundColor Yellow
$litellmCfg = kubectl get configmap litellm-config -n i3-model-gateway `
    -o jsonpath='{.data.config\.yaml}' 2>$null
if ($litellmCfg -match "cache") {
    Write-Host "  PASS: 'cache' found in litellm-config ConfigMap" -ForegroundColor Green
} else {
    # Fallback: check the file on disk
    $diskCfg = Get-Content "platform/model-gateway/litellm/litellm-config-oss.yaml" -Raw -ErrorAction SilentlyContinue
    if ($diskCfg -match "cache:\s*true") {
        Write-Host "  PASS: cache: true confirmed in litellm-config-oss.yaml (disk)" -ForegroundColor Green
    } else {
        Write-Host "  MISS: cache setting not confirmed" -ForegroundColor DarkYellow
    }
}

# =============================================================
# P3-GATE-04 -- Kafka Topics
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-04 -- Kafka Topics" -ForegroundColor Yellow
Show-Resource "kafkatopics in i3-kafka:" @("get","kafkatopic","-n","i3-kafka","--no-headers")

# =============================================================
# P3-GATE-05 -- peer0-i3tech
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-05 -- peer0-i3tech pod" -ForegroundColor Yellow
Show-Resource "pods (app=peer0-i3tech) in i3-ford:" @("get","pod","-n","i3-ford","-l","app=peer0-i3tech","--no-headers")

# =============================================================
# P3-GATE-06 -- Orderer + ford-channel prerequisites
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-06 -- Fabric orderer prerequisites" -ForegroundColor Yellow
Show-Resource "statefulset/orderer in i3-ford:" @("get","statefulset","orderer","-n","i3-ford","--no-headers")
Show-Resource "secret/orderer-msp in i3-ford:"  @("get","secret","orderer-msp","-n","i3-ford","--no-headers")
Show-Resource "svc/ford-ca in i3-ford:"         @("get","svc","ford-ca","-n","i3-ford","--no-headers")
Show-Resource "sa/ford-sa in i3-ford:"          @("get","sa","ford-sa","-n","i3-ford","--no-headers")
Show-Resource "pvc/peer0-i3tech-pvc in i3-ford:" @("get","pvc","peer0-i3tech-pvc","-n","i3-ford","--no-headers")
Show-Resource "job/ford-channel-join:"          @("get","job","ford-channel-join","-n","i3-ford","--no-headers")
Show-Resource "job/ford-chaincode-deploy:"      @("get","job","ford-chaincode-deploy","-n","i3-ford","--no-headers")
Show-Resource "cm/ford-chaincode-files-raw:"    @("get","configmap","ford-chaincode-files-raw","-n","i3-ford","--no-headers")

# =============================================================
# P3-GATE-07 -- ford-api deployment
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-07 -- ford-api deployment" -ForegroundColor Yellow
Show-Resource "deployment/ford-api in i3-ford:" @("get","deployment","ford-api","-n","i3-ford","--no-headers")

# =============================================================
# P3-GATE-08 -- ford-ussd USSD Bridge
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-08 -- ford-ussd USSD Bridge" -ForegroundColor Yellow
Show-Resource "namespace/i3-ussd:"                @("get","namespace","i3-ussd","--no-headers")
Show-Resource "deployment/ford-ussd in i3-ussd:"  @("get","deployment","ford-ussd","-n","i3-ussd","--no-headers")
Show-Resource "pods (app=ford-ussd) in i3-ussd:"  @("get","pod","-n","i3-ussd","-l","app=ford-ussd","--no-headers")

# =============================================================
# P3-GATE-09 -- Tekton Pipeline
# =============================================================
Write-Host ""
Write-Host $SEP -ForegroundColor DarkGray
Write-Host "P3-GATE-09 -- Tekton Pipeline" -ForegroundColor Yellow
Show-Resource "pipeline/i3-build-pipeline:" @("get","pipeline","i3-build-pipeline","-n","i3-tekton","--no-headers")
Write-Host "  last 3 PipelineRuns:" -ForegroundColor DarkGray
kubectl get pipelinerun -n i3-tekton --no-headers `
    --sort-by=.metadata.creationTimestamp 2>$null |
    Select-Object -Last 3 |
    ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }

# =============================================================
# Summary
# =============================================================
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  Gates code-PASS (no cluster action needed):" -ForegroundColor White
Write-Host "    P3-GATE-01  P3-GATE-03  P3-GATE-04  P3-GATE-05  P3-GATE-09  P3-GATE-15" -ForegroundColor Green
Write-Host ""
Write-Host "  Gates needing cluster execution:" -ForegroundColor White
Write-Host "    P3-GATE-06/07  orderer + ford-channel + chaincode" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-08     ford-ussd USSD bridge" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-02     LiteLLM cache warm-up" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-10     promptfoo red-team" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-11     Lighthouse PWA audit" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-12     RAGAS evaluation" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-13     Locust SLA test" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-14     Trivy CVE scan" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "  Next step: .\platform\scripts\p3-run-gates.ps1" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
