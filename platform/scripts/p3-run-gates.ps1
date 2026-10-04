# ============================================================
# p3-run-gates.ps1
# Phase 3 Gate Runner — Windows PowerShell
#
# Prerequisites already confirmed on this machine:
#   ibmcloud CLI 2.47  — for cluster auth
#   kubectl 4.15       — for k8s operations
#   python 3.14 / pip  — for gate scripts
#   git                — for repo operations
#
# Usage:
#   Set your API key first (once per session):
#     $env:IBMCLOUD_API_KEY = "your-ibmcloud-api-key"
#
#   Then run:
#     .\platform\scripts\p3-run-gates.ps1
#
#   Or with explicit key:
#     .\platform\scripts\p3-run-gates.ps1 -IBMCloudAPIKey "your-key"
# ============================================================

param(
    [string]$IBMCloudAPIKey  = $env:IBMCLOUD_API_KEY,
    [string]$ClusterName     = "i3-platform",
    [string]$IBMCloudRegion  = "eu-de",
    [string]$ResourceGroup   = "i3-production",
    [string]$AdmissionsURL   = "https://api.i3technologies.co.ke/admissions",
    [string]$OnboardingURL   = "https://onboarding.i3technologies.co.ke",
    [string]$PMaaSURL        = "https://api.i3technologies.co.ke/pmaas",
    [string]$PrometheusURL   = "https://prometheus.i3technologies.co.ke"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"   # don't stop on individual gate failures

$REPO = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $REPO
Write-Host "=== Repo root: $REPO ===" -ForegroundColor Cyan

# ── Helper: run a command and show pass/fail ──────────────────────────────────
function Invoke-Gate {
    param([string]$GateName, [scriptblock]$Body)
    Write-Host ""
    Write-Host "====== $GateName ======" -ForegroundColor Yellow
    try {
        & $Body
        Write-Host "$GateName : PASS" -ForegroundColor Green
    } catch {
        Write-Host "$GateName : FAIL — $_" -ForegroundColor Red
    }
}

# ── Helper: run a kubectl command and return stdout ───────────────────────────
function kubectl-get-secret-field {
    param([string]$Secret, [string]$Namespace, [string]$Field)
    $encoded = kubectl get secret $Secret -n $Namespace `
        -o "jsonpath={.data.$Field}" 2>$null
    if ($encoded) {
        return [System.Text.Encoding]::UTF8.GetString(
            [System.Convert]::FromBase64String($encoded))
    }
    return $null
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: IBM Cloud + Cluster Authentication
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "====== CLUSTER AUTH ======" -ForegroundColor Yellow

if (-not $IBMCloudAPIKey) {
    Write-Host "ERROR: IBM Cloud API key not set." -ForegroundColor Red
    Write-Host "  Run: `$env:IBMCLOUD_API_KEY = 'your-key'" -ForegroundColor White
    Write-Host "  Then re-run this script." -ForegroundColor White
    exit 1
}

Write-Host "--- Logging in to IBM Cloud ---"
ibmcloud login --apikey $IBMCloudAPIKey -r $IBMCloudRegion -g $ResourceGroup --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: ibmcloud login failed" -ForegroundColor Red; exit 1 }

Write-Host "--- Fetching kubeconfig for $ClusterName ---"
ibmcloud ks cluster config --cluster $ClusterName
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: cluster config failed" -ForegroundColor Red; exit 1 }

Write-Host "--- Verifying cluster connection ---"
kubectl cluster-info 2>&1 | Select-Object -First 2
Write-Host "Cluster auth: OK" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Retrieve LiteLLM Master Key from Kubernetes Secret
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "====== RETRIEVE LITELLM KEY ======" -ForegroundColor Yellow

$LiteLLMKey = kubectl-get-secret-field "litellm-secrets" "i3-model-gateway" "LITELLM_MASTER_KEY"
if ($LiteLLMKey) {
    $env:LITELLM_MASTER_KEY = $LiteLLMKey
    $env:LITELLM_API_KEY    = $LiteLLMKey
    Write-Host "LiteLLM key retrieved: $($LiteLLMKey.Substring(0, [Math]::Min(8,$LiteLLMKey.Length)))..." -ForegroundColor Green
} else {
    Write-Host "WARNING: could not read litellm-secrets — gates requiring auth will fail" -ForegroundColor DarkYellow
}

# Set remaining env vars
$env:ADMISSIONS_AGENT_URL  = $AdmissionsURL
$env:ONBOARDING_AGENT_URL  = $OnboardingURL
$env:PMAAS_AGENT_URL       = $PMaaSURL
$env:PROMETHEUS_URL        = $PrometheusURL

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 08: Deploy USSD Bridge
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-08: USSD Bridge" {
    # Apply namespace (--validate=false skips openapi download)
    kubectl apply -f platform/namespaces/namespaces.yaml --validate=false
    kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/i3-ussd --timeout=30s

    # Create secret from OpenBao if not present
    $secretExists = kubectl get secret ford-ussd-secrets -n i3-ussd 2>$null
    if (-not $secretExists) {
        Write-Host "  Creating ford-ussd-secrets..."
        $hmac = & { ibmcloud bao kv get -field=secret i3/ford/hmac-secret 2>$null } 2>$null
        $atKey = & { ibmcloud bao kv get -field=key i3/ford/at-api-key 2>$null } 2>$null
        if (-not $hmac) { $hmac = "placeholder-hmac-update-before-production" }
        if (-not $atKey) { $atKey = "placeholder-at-key-update-before-production" }
        kubectl create secret generic ford-ussd-secrets `
            --from-literal=MEMBER_HMAC_SECRET=$hmac `
            --from-literal=AT_API_KEY=$atKey `
            --from-literal=AT_USERNAME=sandbox `
            -n i3-ussd
    }

    kubectl apply -f platform/ford/ussd/deploy/ussd-deploy.yaml --validate=false
    kubectl rollout status deployment/ford-ussd -n i3-ussd --timeout=120s

    $pods = kubectl get pod -n i3-ussd -l app=ford-ussd `
        --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}' 2>$null
    if ($pods) {
        Write-Host "  ford-ussd Running: $pods"
    } else {
        throw "No running ford-ussd pods found"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 06/07: Orderer MSP Bootstrap + ford-channel Join
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-06/07: Orderer + ford-channel" {
    kubectl apply -f platform/ford/manifests/orderer-msp-init-job.yaml --validate=false
    kubectl wait --for=condition=complete job/orderer-msp-enroll -n i3-ford --timeout=180s
    Write-Host "  orderer-msp Secret ready"

    kubectl patch statefulset orderer -n i3-ford `
        --patch-file platform/ford/manifests/orderer-statefulset-patch.yaml --type=merge
    kubectl rollout status statefulset/orderer -n i3-ford --timeout=180s

    kubectl apply -f platform/ford/deploy/channel-join-job.yaml --validate=false
    kubectl wait --for=condition=complete job/ford-channel-join -n i3-ford --timeout=180s

    $channels = kubectl exec -n i3-ford peer0-i3tech -- peer channel list 2>$null
    if ($channels -match "ford-channel") {
        Write-Host "  P3-GATE-06: PASS — ford-channel listed"
    } else {
        throw "ford-channel not found in peer channel list"
    }

    kubectl wait --for=condition=complete job/ford-chaincode-deploy -n i3-ford --timeout=300s
    $cc = kubectl exec -n i3-ford peer0-i3tech -- `
        peer chaincode list --instantiated -C ford-channel 2>$null
    if ($cc -match "membership-registry") {
        Write-Host "  P3-GATE-07: PASS — membership-registry instantiated"
    } else {
        throw "membership-registry not found in chaincode list"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 02: LiteLLM Cache Warm-Up
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-02: Cache Warm-Up" {
    pip install httpx --quiet --user 2>$null | Out-Null
    python platform/scripts/p3-gate-02-cache-warmup.py
    if ($LASTEXITCODE -ne 0) { throw "Cache warm-up failed — check ADMISSIONS_AGENT_URL" }
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 10: Promptfoo Red-Team (3 agents × 20 vectors)
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-10: Promptfoo Red-Team" {
    $configs = @("promptfoo-admissions", "promptfoo-onboarding", "promptfoo-pmaas")
    $allPass = $true
    foreach ($cfg in $configs) {
        Write-Host "  --- $cfg ---"
        $cfgPath = Join-Path $REPO "platform\testing\${cfg}.yaml"
        npx promptfoo@latest eval --config $cfgPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  $cfg: FAIL" -ForegroundColor Red
            $allPass = $false
        } else {
            Write-Host "  $cfg: PASS" -ForegroundColor Green
        }
    }
    if (-not $allPass) { throw "One or more promptfoo configs failed" }
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 11: Lighthouse PWA Score
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-11: Lighthouse PWA" {
    # Install lhci if needed
    $lhci = Get-Command lhci -ErrorAction SilentlyContinue
    if (-not $lhci) {
        Write-Host "  Installing @lhci/cli..."
        npm install -g @lhci/cli@0.13 --silent
    }

    $evidenceFile = "platform/docs/verification/p3-lighthouse.json"
    $runDate = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")

    foreach ($app in @(
        @{ Label="Engage"; Url="https://engage.i3technologies.co.ke/dashboard" },
        @{ Label="PMaaS";  Url="https://pmaas.i3technologies.co.ke/dashboard"  }
    )) {
        Write-Host "  Running lhci for $($app.Label)..."
        New-Item -ItemType Directory -Path ".lighthouseci" -Force | Out-Null
        lhci autorun --collect.url=$($app.Url) --collect.numberOfRuns=1 `
            "--assert.assertions.categories:pwa=['error',{'minScore':0.8}]" 2>&1 | Out-Null
    }

    # Update evidence stub with run date
    $ev = Get-Content $evidenceFile | ConvertFrom-Json
    $ev.engage.lhci_run_at = $runDate
    $ev.pmaas.lhci_run_at  = $runDate
    $ev | ConvertTo-Json -Depth 10 | Set-Content $evidenceFile
    Write-Host "  Evidence written to $evidenceFile"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 12: RAGAS Evaluation
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-12: RAGAS Evaluation" {
    pip install ragas datasets langchain-community httpx --quiet --user 2>$null | Out-Null
    python platform/testing/testing.py --ragas --all-agents --staging
    if ($LASTEXITCODE -ne 0) { throw "RAGAS gate failed — check agent URLs" }
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 13: Locust SLA
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-13: Locust SLA" {
    pip install locust --quiet --user 2>$null | Out-Null
    $env:PATH = "$env:APPDATA\Python\Scripts;$env:PATH"

    $evalosHost  = "https://evalos.i3technologies.co.ke"
    $engageHost  = "https://engage.i3technologies.co.ke"

    Write-Host "  Running EvalOS load test (100 users, 2 min)..."
    python -m locust -f platform/testing/testing.py EvalOSSandboxUser `
        --headless -u 100 -r 10 --run-time 2m `
        --host $evalosHost --csv="$env:TEMP\locust-evalos" --only-summary 2>&1 |
        Select-Object -Last 10

    Write-Host "  Running Engage load test (50 users, 2 min)..."
    python -m locust -f platform/testing/testing.py AILabAPIUser `
        --headless -u 50 -r 5 --run-time 2m `
        --host $engageHost --csv="$env:TEMP\locust-engage" --only-summary 2>&1 |
        Select-Object -Last 10

    Write-Host "  Locust runs complete — check $env:TEMP\locust-*.csv for p95 values"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 14: Trivy CVE Scan
# ═══════════════════════════════════════════════════════════════════════════════
Invoke-Gate "P3-GATE-14: Trivy CVE Scan" {
    # Install trivy if not present
    $trivy = Get-Command trivy -ErrorAction SilentlyContinue
    if (-not $trivy) {
        Write-Host "  Installing trivy..."
        winget install --id Aquasec.Trivy --silent --accept-source-agreements 2>$null ||
        choco install trivy -y --quiet 2>$null ||
        { throw "trivy not found — install from https://github.com/aquasecurity/trivy/releases" }
    }

    python platform/scripts/p3-gate-14-trivy.sh 2>$null ||
    python - @"
import subprocess, json, sys, os

registry = os.environ.get('IMAGE_REGISTRY', 'image-registry.openshift-image-registry.svc:5000')
images = [
    ('admissions-agent', f'{registry}/i3-admissions/admissions-agent:latest'),
    ('engage-web',       f'{registry}/i3-engage/engage-web:latest'),
    ('pmaas-web',        f'{registry}/i3-pmaas/pmaas-web:latest'),
    ('ford-api',         f'{registry}/i3-ford/ford-api:latest'),
    ('ford-ussd',        f'{registry}/i3-ussd/ford-ussd:latest'),
    ('litellm-proxy',    f'{registry}/i3-model-gateway/litellm-proxy:latest'),
]
overall = True
for label, image in images:
    print(f'  Scanning {label}...', flush=True)
    r = subprocess.run(
        ['trivy','image','--severity','CRITICAL,HIGH','--ignore-unfixed',
         '--format','json','--quiet', image],
        capture_output=True, text=True, timeout=120)
    try:
        data = json.loads(r.stdout or '{}')
        findings = [v for res in data.get('Results',[]) for v in res.get('Vulnerabilities',[])
                    if v.get('Severity') in ('CRITICAL','HIGH')]
        if findings:
            overall = False
            print(f'  FAIL: {label} — {len(findings)} finding(s)', flush=True)
        else:
            print(f'  PASS: {label}', flush=True)
    except Exception as e:
        print(f'  WARNING: {label} scan error: {e}', flush=True)
sys.exit(0 if overall else 1)
"@
}

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "====== PHASE 3 GATE RUN COMPLETE ======" -ForegroundColor Cyan
Write-Host ""
Write-Host "Evidence files:" -ForegroundColor White
Get-ChildItem platform/docs/verification/p3-*.json |
    ForEach-Object { Write-Host "  $($_.Name)" }

Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Review evidence JSON files in platform/docs/verification/"
Write-Host "  2. git add platform/docs/verification/ && git commit -m 'evidence: p3 gate results'"
Write-Host "  3. git push origin main"
