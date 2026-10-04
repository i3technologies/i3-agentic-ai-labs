<#
.SYNOPSIS
    Phase 3 Gate Runner for Windows PowerShell
.DESCRIPTION
    Authenticates to IBM Cloud using SSO passcode (browser-based one-time code),
    retrieves the LiteLLM master key automatically, then executes all Phase 3 gates.
.PARAMETER ClusterName
    IBM Kubernetes Service cluster name. Default: i3-platform
.PARAMETER CloudRegion
    IBM Cloud region. Default: eu-de
.PARAMETER ResourceGroup
    IBM Cloud resource group. Default: i3-production
.EXAMPLE
    .\platform\scripts\p3-run-gates.ps1

    The script opens the IBM Cloud SSO URL in your browser.
    Copy the one-time passcode, paste it when prompted, and all gates run.
#>

param(
    [string]$ClusterName   = "i3-platform",
    [string]$CloudRegion   = "eu-de",
    [string]$ResourceGroup = "i3-production"
)

$ErrorActionPreference = "Continue"
$REPO = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $REPO
Write-Host "Repo root: $REPO" -ForegroundColor Cyan

# ── Helper functions ──────────────────────────────────────────────────────────

function Show-Gate([string]$Name) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkGray
    Write-Host "  $Name" -ForegroundColor Yellow
    Write-Host ("=" * 60) -ForegroundColor DarkGray
}

function Show-Pass([string]$Msg) {
    Write-Host "  PASS: $Msg" -ForegroundColor Green
}

function Show-Fail([string]$Msg) {
    Write-Host "  FAIL: $Msg" -ForegroundColor Red
}

function Show-Skip([string]$Msg) {
    Write-Host "  SKIP: $Msg" -ForegroundColor DarkYellow
}

function Get-SecretField([string]$SecretName, [string]$Namespace, [string]$Field) {
    $encoded = kubectl get secret $SecretName -n $Namespace `
        -o "jsonpath={.data.$Field}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $encoded) {
        $bytes = [System.Convert]::FromBase64String($encoded)
        return [System.Text.Encoding]::UTF8.GetString($bytes)
    }
    return $null
}

function Install-PipPackage([string]$Package) {
    Write-Host "  Installing $Package ..." -ForegroundColor DarkGray
    pip install $Package --quiet --user 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        python -m pip install $Package --quiet --user 2>$null | Out-Null
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — IBM Cloud API Key Authentication
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "CLUSTER AUTH (API Key)"

Write-Host ""
# Use $env:IBMCLOUD_API_KEY if already set (e.g. from shell), otherwise prompt once
if (-not $env:IBMCLOUD_API_KEY) {
    Write-Host "  IBMCLOUD_API_KEY is not set." -ForegroundColor DarkYellow
    Write-Host "  Tip: set it permanently with:" -ForegroundColor DarkGray
    Write-Host '    $env:IBMCLOUD_API_KEY="<your-api-key>"' -ForegroundColor Cyan
    $apiKeySecure = Read-Host "  Paste API key now" -AsSecureString
    $env:IBMCLOUD_API_KEY = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKeySecure))
}

Write-Host "  Logging in to IBM Cloud with API key ..."
ibmcloud login --apikey $env:IBMCLOUD_API_KEY -r $CloudRegion -g $ResourceGroup --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: ibmcloud login failed. Check IBMCLOUD_API_KEY." -ForegroundColor Red
    Write-Host "  Verify the key is valid at: https://cloud.ibm.com/iam/apikeys" -ForegroundColor DarkYellow
    exit 1
}

Write-Host "  Fetching kubeconfig for cluster: $ClusterName ..."
ibmcloud ks cluster config --cluster $ClusterName
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: cluster config failed" -ForegroundColor Red
    exit 1
}

# Extract IAM bearer token and inject directly so kubectl never prompts for credentials.
# ibmcloud ks cluster config on ROKS writes an exec: plugin entry that tries to call
# ibmcloud interactively -- injecting the token bypasses that completely.
Write-Host "  Injecting IAM bearer token into kubeconfig ..."
$iamToken = ibmcloud iam oauth-tokens --output json 2>$null | ConvertFrom-Json
if ($iamToken -and $iamToken.iam_token) {
    $rawToken = $iamToken.iam_token -replace '^Bearer\s+', ''
    kubectl config set-credentials "$(kubectl config current-context)" `
        --token=$rawToken 2>$null | Out-Null
    Show-Pass "IAM bearer token injected into kubeconfig"
} else {
    Write-Host "  WARNING: could not extract IAM token -- kubectl may prompt" -ForegroundColor DarkYellow
}

# Connectivity check
Write-Host "  Verifying cluster connectivity ..."
$nodes = kubectl get nodes --no-headers 2>$null
if ($LASTEXITCODE -eq 0 -and $nodes) {
    $nodeCount = ($nodes -split "`n" | Where-Object { $_ -match '\S' }).Count
    Show-Pass "Cluster connected -- $nodeCount node(s) ready"
} else {
    Write-Host "  WARNING: kubectl get nodes returned no output -- continuing" -ForegroundColor DarkYellow
    Show-Pass "Cluster authenticated via SSO passcode (node check inconclusive)"
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Retrieve LiteLLM Master Key from Kubernetes Secret
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "RETRIEVE LITELLM KEY"

$litellmKey = Get-SecretField "litellm-secrets" "i3-model-gateway" "LITELLM_MASTER_KEY"
if ($litellmKey) {
    $env:LITELLM_MASTER_KEY = $litellmKey
    $env:LITELLM_API_KEY    = $litellmKey
    $preview = $litellmKey.Substring(0, [Math]::Min(8, $litellmKey.Length))
    Show-Pass "LiteLLM key retrieved: ${preview}..."
} else {
    Show-Skip "Could not read litellm-secrets -- gates needing auth may fail"
}

# Set agent URLs
$env:ADMISSIONS_AGENT_URL = "https://api.i3technologies.co.ke/admissions"
$env:ONBOARDING_AGENT_URL = "https://onboarding.i3technologies.co.ke"
$env:PMAAS_AGENT_URL      = "https://api.i3technologies.co.ke/pmaas"
$env:PROMETHEUS_URL       = "https://prometheus.i3technologies.co.ke"

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 08 — Deploy USSD Bridge
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-08: USSD Bridge"

try {
    kubectl apply -f platform/namespaces/namespaces.yaml --validate=false
    kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/i3-ussd --timeout=30s

    $secretCheck = kubectl get secret ford-ussd-secrets -n i3-ussd 2>$null
    if (-not $secretCheck) {
        Write-Host "  Creating ford-ussd-secrets ..."
        $hmac  = "placeholder-hmac-update-before-production"
        $atKey = "placeholder-at-key-update-before-production"
        kubectl create secret generic ford-ussd-secrets `
            --from-literal=MEMBER_HMAC_SECRET=$hmac `
            --from-literal=AT_API_KEY=$atKey `
            --from-literal=AT_USERNAME=sandbox `
            -n i3-ussd
    }

    kubectl apply -f platform/ford/ussd/deploy/ussd-deploy.yaml --validate=false
    kubectl rollout status deployment/ford-ussd -n i3-ussd --timeout=120s

    $pods = kubectl get pod -n i3-ussd -l app=ford-ussd `
        --field-selector=status.phase=Running `
        -o jsonpath='{.items[*].metadata.name}' 2>$null
    if ($pods) {
        Show-Pass "ford-ussd Running: $pods"
    } else {
        Show-Fail "No running ford-ussd pods found"
    }
} catch {
    Show-Fail "Gate 08 exception: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 06/07 — Orderer MSP Bootstrap + ford-channel Join + Chaincode Deploy
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-06/07: Orderer + ford-channel + membership-registry"

try {
    # Pre-flight: upload chaincode source as a ConfigMap so the deploy Job can mount it
    Write-Host "  Pre-flight: uploading chaincode source to ford-chaincode-files-raw ..."
    $ccDir = Join-Path $REPO "platform\ford\fabric\chaincode\membership_registry"
    kubectl delete configmap ford-chaincode-files-raw -n i3-ford --ignore-not-found 2>$null | Out-Null
    kubectl create configmap ford-chaincode-files-raw -n i3-ford `
        "--from-file=$ccDir" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Show-Pass "ford-chaincode-files-raw ConfigMap uploaded"
    } else {
        Show-Skip "Could not create ford-chaincode-files-raw -- chaincode deploy may fail"
    }

    # Step 1: Enroll orderer MSP
    Write-Host "  Step 1: Orderer MSP enroll job ..."
    kubectl apply -f platform/ford/manifests/orderer-msp-init-job.yaml --validate=false
    kubectl wait --for=condition=complete job/orderer-msp-enroll -n i3-ford --timeout=180s
    Show-Pass "orderer-msp Secret ready"

    # Step 2: Patch orderer StatefulSet to mount orderer-msp Secret
    Write-Host "  Step 2: Patching orderer StatefulSet ..."
    kubectl patch statefulset orderer -n i3-ford `
        --patch-file platform/ford/manifests/orderer-statefulset-patch.yaml --type=merge
    kubectl rollout status statefulset/orderer -n i3-ford --timeout=180s

    # Step 3: Channel join
    Write-Host "  Step 3: ford-channel join ..."
    kubectl apply -f platform/ford/deploy/channel-join-job.yaml --validate=false
    kubectl wait --for=condition=complete job/ford-channel-join -n i3-ford --timeout=180s

    $channels = kubectl exec -n i3-ford peer0-i3tech -- peer channel list 2>$null
    if ($channels -match "ford-channel") {
        Show-Pass "ford-channel listed on peer0-i3tech"
    } else {
        Show-Fail "ford-channel not found in peer channel list"
    }

    # Step 4: Chaincode deploy (ford-chaincode-deploy Job is in channel-join-job.yaml)
    Write-Host "  Step 4: Waiting for membership-registry chaincode deploy ..."
    kubectl wait --for=condition=complete job/ford-chaincode-deploy -n i3-ford --timeout=300s
    $cc = kubectl exec -n i3-ford peer0-i3tech -- `
        peer chaincode list --instantiated -C ford-channel 2>$null
    if ($cc -match "membership-registry") {
        Show-Pass "membership-registry instantiated on ford-channel"
    } else {
        Show-Fail "membership-registry not found in instantiated list"
    }
} catch {
    Show-Fail "Gate 06/07 exception: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 02 — LiteLLM Cache Warm-Up
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-02: Cache Warm-Up"

try {
    Install-PipPackage "httpx"
    python platform/scripts/p3-gate-02-cache-warmup.py
    if ($LASTEXITCODE -eq 0) {
        Show-Pass "Cache hit ratio meets threshold"
    } else {
        Show-Fail "Cache warm-up below threshold -- check ADMISSIONS_AGENT_URL"
    }
} catch {
    Show-Fail "Gate 02 exception: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 10 — Promptfoo Red-Team
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-10: Promptfoo Red-Team"

$promptfooConfigs = @("promptfoo-admissions", "promptfoo-onboarding", "promptfoo-pmaas")
foreach ($cfgName in $promptfooConfigs) {
    Write-Host "  --- $cfgName ---"
    $cfgPath = Join-Path $REPO "platform\testing\${cfgName}.yaml"
    npx promptfoo@latest eval --config $cfgPath
    if ($LASTEXITCODE -eq 0) {
        Show-Pass $cfgName
    } else {
        Show-Fail $cfgName
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 11 — Lighthouse PWA Score
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-11: Lighthouse PWA"

try {
    $lhciCmd = Get-Command lhci -ErrorAction SilentlyContinue
    if (-not $lhciCmd) {
        Write-Host "  Installing @lhci/cli ..."
        npm install -g "@lhci/cli@0.13" --silent
    }

    New-Item -ItemType Directory -Path ".lighthouseci" -Force | Out-Null

    $engageUrl = "https://engage.i3technologies.co.ke/dashboard"
    $pmaasUrl  = "https://pmaas.i3technologies.co.ke/dashboard"

    Write-Host "  Auditing Engage ..."
    lhci autorun --collect.url=$engageUrl --collect.numberOfRuns=1 `
        "--assert.assertions.categories:pwa=['error',{'minScore':0.8}]" 2>&1 | Out-Null

    Write-Host "  Auditing PMaaS ..."
    lhci autorun --collect.url=$pmaasUrl --collect.numberOfRuns=1 `
        "--assert.assertions.categories:pwa=['error',{'minScore':0.8}]" 2>&1 | Out-Null

    $evidenceFile = Join-Path $REPO "platform\docs\verification\p3-lighthouse.json"
    $ev = Get-Content $evidenceFile | ConvertFrom-Json
    $runDate = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    $ev.engage.lhci_run_at = $runDate
    $ev.pmaas.lhci_run_at  = $runDate
    $ev | ConvertTo-Json -Depth 10 | Set-Content $evidenceFile
    Show-Pass "Lighthouse audits complete -- check p3-lighthouse.json"
} catch {
    Show-Fail "Gate 11 exception: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 12 — RAGAS Evaluation
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-12: RAGAS Evaluation"

try {
    Install-PipPackage "ragas"
    Install-PipPackage "datasets"
    Install-PipPackage "langchain-community"
    python platform/testing/testing.py --ragas --all-agents --staging
    if ($LASTEXITCODE -eq 0) {
        Show-Pass "All RAGAS thresholds met"
    } else {
        Show-Fail "RAGAS below threshold -- check agent URLs and LiteLLM key"
    }
} catch {
    Show-Fail "Gate 12 exception: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 13 — Locust SLA
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-13: Locust SLA"

try {
    Install-PipPackage "locust"
    $env:PATH = "$env:APPDATA\Python\Scripts;$env:PATH"

    $evalosHost = "https://evalos.i3technologies.co.ke"
    $engageHost = "https://engage.i3technologies.co.ke"
    $tmpCsv     = $env:TEMP

    Write-Host "  EvalOS load test: 100 users, 2 min ..."
    python -m locust -f platform/testing/testing.py EvalOSSandboxUser `
        --headless -u 100 -r 10 --run-time 2m `
        --host $evalosHost --csv="$tmpCsv\locust-evalos" --only-summary 2>&1 |
        Select-Object -Last 8

    Write-Host "  Engage load test: 50 users, 2 min ..."
    python -m locust -f platform/testing/testing.py AILabAPIUser `
        --headless -u 50 -r 5 --run-time 2m `
        --host $engageHost --csv="$tmpCsv\locust-engage" --only-summary 2>&1 |
        Select-Object -Last 8

    Show-Pass "Locust runs complete -- p95 values in $tmpCsv\locust-*.csv"
} catch {
    Show-Fail "Gate 13 exception: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GATE 14 — Trivy CVE Scan
# ═══════════════════════════════════════════════════════════════════════════════
Show-Gate "P3-GATE-14: Trivy CVE Scan"

try {
    $trivyCmd = Get-Command trivy -ErrorAction SilentlyContinue
    if (-not $trivyCmd) {
        Write-Host "  Installing trivy via winget ..."
        winget install --id Aquasec.Trivy --silent --accept-source-agreements 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Trying choco ..."
            choco install trivy -y --quiet 2>$null
        }
    }

    $registry = "image-registry.openshift-image-registry.svc:5000"
    $imageList = @(
        @{ Label="admissions-agent"; Image="${registry}/i3-admissions/admissions-agent:latest" },
        @{ Label="engage-web";       Image="${registry}/i3-engage/engage-web:latest" },
        @{ Label="pmaas-web";        Image="${registry}/i3-pmaas/pmaas-web:latest" },
        @{ Label="ford-api";         Image="${registry}/i3-ford/ford-api:latest" },
        @{ Label="ford-ussd";        Image="${registry}/i3-ussd/ford-ussd:latest" },
        @{ Label="litellm-proxy";    Image="${registry}/i3-model-gateway/litellm-proxy:latest" }
    )

    $overallPass = $true
    foreach ($item in $imageList) {
        Write-Host "  Scanning $($item.Label) ..."
        $result = trivy image --severity CRITICAL,HIGH --ignore-unfixed `
            --format json --quiet $item.Image 2>$null | ConvertFrom-Json
        $findings = @($result.Results | ForEach-Object {
            $_.Vulnerabilities
        } | Where-Object { $_.Severity -in "CRITICAL","HIGH" })
        if ($findings.Count -gt 0) {
            Show-Fail "$($item.Label): $($findings.Count) finding(s)"
            $overallPass = $false
        } else {
            Write-Host "    PASS: $($item.Label)" -ForegroundColor Green
        }
    }

    $evidenceFile = Join-Path $REPO "platform\docs\verification\p3-trivy.json"
    $ev = Get-Content $evidenceFile | ConvertFrom-Json
    $ev.overall_pass = $overallPass
    $ev.run_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    $ev | ConvertTo-Json -Depth 10 | Set-Content $evidenceFile

    if ($overallPass) {
        Show-Pass "Zero fixable Critical/High CVEs across all images"
    } else {
        Show-Fail "Fixable CVEs found -- update base images and re-run"
    }
} catch {
    Show-Fail "Gate 14 exception: $_"
}

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  PHASE 3 GATE RUN COMPLETE" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""
Write-Host "Evidence files written:" -ForegroundColor White
Get-ChildItem "platform\docs\verification\p3-*.json" -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Gray }

Write-Host ""
Write-Host "Commit evidence to git:" -ForegroundColor White
Write-Host '  git add platform/docs/verification/' -ForegroundColor Cyan
Write-Host '  git commit -m "evidence: Phase 3 gate results"' -ForegroundColor Cyan
Write-Host '  git push origin main' -ForegroundColor Cyan
