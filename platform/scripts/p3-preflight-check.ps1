<#
.SYNOPSIS
    Phase 3 Pre-flight Cluster Status Check
.DESCRIPTION
    Checks the current state of all P3-GATE resources on the cluster
    BEFORE running p3-run-gates.ps1. Use this to see what is already
    deployed and what still needs to be applied.
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

function Check([string]$Label, [scriptblock]$Test) {
    $result = & $Test 2>$null
    if ($LASTEXITCODE -eq 0 -and $result) {
        Write-Host "  OK   $Label" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  MISS $Label" -ForegroundColor DarkYellow
        return $false
    }
}

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  PHASE 3 PRE-FLIGHT CHECK" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

# ── IBM Cloud Auth ────────────────────────────────────────────
Write-Host "CLUSTER AUTH" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Opening IBM Cloud SSO passcode page ..."
Start-Process "https://iam.cloud.ibm.com/identity/passcode"
$passcodeSecure = Read-Host "  Paste SSO passcode" -AsSecureString
$passcode = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($passcodeSecure))

ibmcloud login --sso -p $passcode -r $CloudRegion -g $ResourceGroup --quiet
ibmcloud ks cluster config --cluster $ClusterName

$nodes = kubectl get nodes --no-headers 2>$null
if ($LASTEXITCODE -eq 0 -and $nodes) {
    $n = ($nodes -split "`n" | Where-Object { $_ -match '\S' }).Count
    Write-Host "  Cluster: $ClusterName ($n nodes)" -ForegroundColor Green
} else {
    Write-Host "  WARNING: kubectl get nodes inconclusive" -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-01 — LiteLLM Redis Cache" -ForegroundColor Yellow
kubectl get configmap litellm-config -n i3-model-gateway `
    -o jsonpath='{.data.config\.yaml}' 2>$null |
    Select-String "cache" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-04 — Kafka Topics" -ForegroundColor Yellow
kubectl get kafkatopic -n i3-kafka 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-05 — peer0-i3tech" -ForegroundColor Yellow
kubectl get pod -n i3-ford -l app=peer0-i3tech 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-06 — Orderer + ford-channel" -ForegroundColor Yellow
Write-Host "  StatefulSet/orderer:" -ForegroundColor DarkGray
kubectl get statefulset orderer -n i3-ford 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host "  Secret/orderer-msp:" -ForegroundColor DarkGray
kubectl get secret orderer-msp -n i3-ford 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host "  ford-channel-join Job:" -ForegroundColor DarkGray
kubectl get job ford-channel-join -n i3-ford 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host "  ford-chaincode-deploy Job:" -ForegroundColor DarkGray
kubectl get job ford-chaincode-deploy -n i3-ford 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host "  ford-chaincode-files-raw CM:" -ForegroundColor DarkGray
kubectl get configmap ford-chaincode-files-raw -n i3-ford 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-07 — ford-api Fabric wiring" -ForegroundColor Yellow
kubectl get deployment ford-api -n i3-ford 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-08 — ford-ussd USSD Bridge" -ForegroundColor Yellow
kubectl get namespace i3-ussd 2>$null | ForEach-Object { Write-Host "  namespace: $_" -ForegroundColor Gray }
kubectl get deployment ford-ussd -n i3-ussd 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
kubectl get pod -n i3-ussd -l app=ford-ussd 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-09 — Tekton Pipeline" -ForegroundColor Yellow
kubectl get pipeline i3-build-pipeline -n i3-tekton 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
kubectl get pipelinerun -n i3-tekton --sort-by=.metadata.creationTimestamp 2>$null |
    Select-Object -Last 3 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "P3-GATE-14 — Image Registry" -ForegroundColor Yellow
$images = @("admissions-agent","engage-web","pmaas-web","ford-api","ford-ussd","litellm-proxy")
foreach ($img in $images) {
    $tag = kubectl get imagestream $img -n i3-admissions 2>$null
    Write-Host "  $img -> $($tag ? 'found' : 'not found in default ns')" -ForegroundColor Gray
}

Write-Host ""
Write-Host ("═" * 60) -ForegroundColor Cyan
Write-Host "  Gates that are code-PASS (no cluster action needed):" -ForegroundColor White
Write-Host "    P3-GATE-01 P3-GATE-03 P3-GATE-04 P3-GATE-05 P3-GATE-09 P3-GATE-15" -ForegroundColor Green
Write-Host ""
Write-Host "  Gates that need cluster execution:" -ForegroundColor White
Write-Host "    P3-GATE-06/07  orderer + ford-channel + chaincode" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-08     ford-ussd USSD bridge deployment" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-02     LiteLLM cache warm-up" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-10     promptfoo red-team (needs npx)" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-11     Lighthouse PWA audit (needs Node/lhci)" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-12     RAGAS evaluation (needs Python deps)" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-13     Locust SLA test (needs Python locust)" -ForegroundColor DarkYellow
Write-Host "    P3-GATE-14     Trivy CVE scan (needs trivy installed)" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "  Run gates:  .\platform\scripts\p3-run-gates.ps1" -ForegroundColor Cyan
Write-Host ("═" * 60) -ForegroundColor Cyan
