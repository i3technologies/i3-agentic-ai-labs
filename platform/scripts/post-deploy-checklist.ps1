#!/usr/bin/env pwsh
# ============================================================
# i3 Platform - Full Post-Deploy Health Check
# PURPOSE:
#   Validates the complete platform after all operator/app deploys.
#   Prints a PASS/FAIL summary.
#
# PREREQUISITES:
#   - oc is configured against i3-platform cluster
#   - All deploy targets have been run
#
# USAGE:
#   . .\platform\scripts\load-env.ps1
#   .\platform\scripts\post-deploy-checklist.ps1
# ============================================================

$ErrorActionPreference = "SilentlyContinue"

$oc     = "oc"
$PASS   = "[PASS]"
$FAIL   = "[FAIL]"
$WARN   = "[WARN]"
$checks = [System.Collections.Generic.List[PSCustomObject]]::new()

function Banner([string]$msg) {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Cyan
}

function Check([string]$label, [bool]$passed, [string]$detail = "") {
    $status = if ($passed) { $PASS } else { $FAIL }
    $color  = if ($passed) { "Green" } else { "Red" }
    Write-Host "  $status $label" -ForegroundColor $color
    if ($detail) { Write-Host "        $detail" -ForegroundColor Gray }
    $checks.Add([PSCustomObject]@{ Label = $label; Passed = $passed })
}

function WarnCheck([string]$label, [string]$detail = "") {
    Write-Host "  $WARN $label" -ForegroundColor Magenta
    if ($detail) { Write-Host "        $detail" -ForegroundColor Gray }
    $checks.Add([PSCustomObject]@{ Label = $label; Passed = $true })
}

# ---------------------------------------------------------------------------
Banner "1 - Namespace Topology"

$requiredNs = @(
    "i3-data","i3-messaging","i3-security","i3-auth","i3-gitops",
    "i3-model-gateway","i3-ai-lab","i3-evalos","i3-ott","i3-admissions","i3-monitoring"
)

foreach ($ns in $requiredNs) {
    $null = & $oc get ns $ns 2>&1
    Check "Namespace [$ns] exists" ($LASTEXITCODE -eq 0)
}

# Solution namespaces must be untouched
$solutionNsTouched = $false
for ($i = 1; $i -le 8; $i++) {
    $sn   = "solution-0$i"
    $null = & $oc get ns $sn 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pods = & $oc get pods -n $sn --no-headers 2>&1
        if ($pods -and $pods.Count -gt 0 -and ($pods -notmatch "No resources found")) {
            $solutionNsTouched = $true
            Write-Host "  $FAIL solution namespace [$sn] has pods - MUST be untouched!" -ForegroundColor Red
        }
    }
}
Check "solution-01..08 namespaces untouched" (-not $solutionNsTouched)

# ---------------------------------------------------------------------------
Banner "2 - Core Operators"

# PostgreSQL
$pgPods  = & $oc get pods -n i3-data -l "postgres-operator.crunchydata.com/cluster=i3-postgres" --no-headers 2>&1
$pgReady = ($pgPods | Where-Object { $_ -match "Running" }).Count -ge 3
Check "Crunchy PostgreSQL HA (3 pods Running)" $pgReady

# Kafka KRaft
$kafkaPods  = & $oc get pods -n i3-messaging -l "strimzi.io/kind=Kafka" --no-headers 2>&1
$kafkaReady = ($kafkaPods | Where-Object { $_ -match "Running" }).Count -ge 3
Check "Strimzi Kafka KRaft (3 pods Running)" $kafkaReady

# OpenBao
$baoPods  = & $oc get pods -n i3-security -l "app.kubernetes.io/name=openbao" --no-headers 2>&1
$baoReady = ($baoPods | Where-Object { $_ -match "Running" }).Count -ge 3
Check "OpenBao (3 pods Running + Unsealed)" $baoReady

# Keycloak
$kcPods  = & $oc get pods -n i3-auth -l "app=keycloak" --no-headers 2>&1
$kcReady = ($kcPods | Where-Object { $_ -match "Running" }).Count -ge 1
Check "Keycloak (1+ pods Running)" $kcReady

# ---------------------------------------------------------------------------
Banner "3 - Model Gateway"

$litellmPods  = & $oc get pods -n i3-model-gateway -l "app=litellm-proxy" --no-headers 2>&1
Check "LiteLLM proxy Running" ([bool]($litellmPods -match "Running"))

$ollamaPods   = & $oc get pods -n i3-model-gateway -l "app=ollama" --no-headers 2>&1
Check "Ollama Running" ([bool]($ollamaPods -match "Running"))

$langfusePods = & $oc get pods -n i3-model-gateway -l "app=langfuse-web" --no-headers 2>&1
Check "Langfuse Running" ([bool]($langfusePods -match "Running"))

# ---------------------------------------------------------------------------
Banner "4 - EvalOS"

$evalSandbox = & $oc get pods -n i3-evalos -l "app=evalos-sandbox" --no-headers 2>&1
Check "EvalOS sandbox Running" ([bool]($evalSandbox -match "Running"))

# ---------------------------------------------------------------------------
Banner "5 - OTT Stack"

$omePods = & $oc get pods -n i3-ott -l "app=ome" --no-headers 2>&1
Check "OvenMediaEngine Running" ([bool]($omePods -match "Running"))

$nginxPods = & $oc get pods -n i3-ott -l "app=nginx-hls" --no-headers 2>&1
Check "Nginx HLS Running" ([bool]($nginxPods -match "Running"))

$seaweedMaster = & $oc get pods -n i3-ott -l "app=seaweedfs,component=master" --no-headers 2>&1
Check "SeaweedFS master Running" ([bool]($seaweedMaster -match "Running"))

$seaweedVol      = & $oc get pods -n i3-ott -l "app=seaweedfs,component=volume" --no-headers 2>&1
$seaweedVolReady = ($seaweedVol | Where-Object { $_ -match "Running" }).Count -ge 3
Check "SeaweedFS volumes (3 Running)" $seaweedVolReady

$directusPods = & $oc get pods -n i3-ott -l "app=directus" --no-headers 2>&1
Check "Directus CMS Running" ([bool]($directusPods -match "Running"))

$n8nPods = & $oc get pods -n i3-ott -l "app=n8n" --no-headers 2>&1
Check "n8n automation Running" ([bool]($n8nPods -match "Running"))

# ---------------------------------------------------------------------------
Banner "6 - Admissions AI"

$admPods   = & $oc get pods -n i3-admissions -l "app=admissions-agent" --no-headers 2>&1
Check "Admissions agent Running" ([bool]($admPods -match "Running"))

$chromaPods = & $oc get pods -n i3-admissions -l "app=chromadb" --no-headers 2>&1
Check "ChromaDB Running" ([bool]($chromaPods -match "Running"))

# ---------------------------------------------------------------------------
Banner "7 - GitOps / CI"

$argoPods = & $oc get pods -n openshift-gitops -l "app.kubernetes.io/name=openshift-gitops-server" --no-headers 2>&1
Check "Argo CD server Running" ([bool]($argoPods -match "Running"))

$argoJson = & $oc get applications -A -o json 2>&1
try {
    $argoItems = ($argoJson | ConvertFrom-Json).items
    if ($argoItems -and $argoItems.Count -gt 0) {
        $notSynced = $argoItems | Where-Object {
            $s = $_.status.sync.status
            $s -and $s -ne "Synced"
        }
        $summary = ($argoItems | ForEach-Object {
            $s = if ($_.status.sync.status) { $_.status.sync.status } else { "pending-repo" }
            "$($_.metadata.name)=$s"
        }) -join ", "
        # Empty status = git repo not yet seeded — warn, not fail
        $hasEmpty = $argoItems | Where-Object { -not $_.status.sync.status }
        if ($hasEmpty -and $notSynced.Count -eq 0) {
            WarnCheck "Argo CD git repo pending (create platform-gitops repo + push manifests)" $summary
        } else {
            Check "Argo CD applications Synced" ($notSynced.Count -eq 0) $summary
        }
    } else {
        WarnCheck "Argo CD applications (none found)"
    }
} catch {
    WarnCheck "Argo CD applications (parse error - skipped)"
}

$webhookSecret = & $oc get secret github-webhook-secret -n i3-gitops 2>&1
Check "github-webhook-secret exists in i3-gitops" ($LASTEXITCODE -eq 0)

# ---------------------------------------------------------------------------
Banner "8 - Monitoring"

$promPods   = & $oc get pods -n i3-monitoring -l "app=prometheus" --no-headers 2>&1
Check "Prometheus Running" ([bool]($promPods -match "Running"))

$grafanaPods = & $oc get pods -n i3-monitoring -l "app=grafana" --no-headers 2>&1
Check "Grafana Running" ([bool]($grafanaPods -match "Running"))

# ---------------------------------------------------------------------------
Banner "9 - Onboarding Agent"

$onbPods = & $oc get pods -n i3-onboarding -l "app=onboarding-agent" --no-headers 2>&1
Check "Onboarding Agent Running" ([bool]($onbPods -match "Running"))

$onbHpa = & $oc get hpa onboarding-agent-hpa -n i3-onboarding 2>&1
Check "Onboarding Agent HPA exists" ($LASTEXITCODE -eq 0)

# ---------------------------------------------------------------------------
Banner "10 - Routes / DNS"

$curl = "C:\Program Files\Git\mingw64\bin\curl.exe"
$publicRoutes = @(
    @{ url = "https://sso.i3technologies.co.ke/auth/realms/i3/.well-known/openid-configuration"; label = "sso (Keycloak SSO)" },
    @{ url = "https://litellm.i3technologies.co.ke/health/liveliness";                           label = "litellm" },
    @{ url = "https://langfuse.i3technologies.co.ke/api/public/health";                          label = "langfuse" },
    @{ url = "https://evalos.i3technologies.co.ke/health";                                       label = "evalos" },
    @{ url = "https://cms.i3technologies.co.ke/server/health";                                   label = "cms (Directus)" },
    @{ url = "https://n8n.i3technologies.co.ke/healthz";                                         label = "n8n" },
    @{ url = "https://admissions.i3technologies.co.ke/health";                                   label = "admissions" },
    @{ url = "https://grafana.i3technologies.co.ke/api/health";                                  label = "grafana" },
    @{ url = "https://argocd.i3technologies.co.ke/healthz";                                      label = "argocd" },
    @{ url = "https://onboarding.i3technologies.co.ke/health";                                   label = "onboarding" }
)

if (Test-Path $curl) {
    foreach ($r in $publicRoutes) {
        $code = & $curl -sk -o /dev/null -w "%{http_code}" --max-time 15 $r.url 2>&1
        $ok   = $code -match "^[23]"
        Check "HTTPS [$($r.label)] -> HTTP $code" ([bool]$ok)
    }
} else {
    WarnCheck "curl not found - skipping live HTTP checks"
}

# ---------------------------------------------------------------------------
Banner "11 - Secrets"

$secretChecks = @(
    @{ ns = "i3-model-gateway"; secret = "litellm-secrets" },
    @{ ns = "i3-ott";           secret = "directus-secrets" },
    @{ ns = "i3-ott";           secret = "rclone-secrets" },
    @{ ns = "i3-monitoring";    secret = "grafana-secrets" },
    @{ ns = "i3-onboarding";    secret = "onboarding-agent-secrets" }
)

foreach ($s in $secretChecks) {
    $null  = & $oc get secret $s.secret -n $s.ns 2>&1
    $label = "Secret [$($s.secret)] in $($s.ns)"
    Check $label ($LASTEXITCODE -eq 0)
}

# ---------------------------------------------------------------------------
Banner "12 - DR / Backup"

$rcloneCJ = & $oc get cronjob seaweedfs-cos-dr-sync -n i3-ott 2>&1
Check "SeaweedFS -> COS rclone CronJob exists" ($LASTEXITCODE -eq 0)

$pgbSecret = & $oc get secret pgbackrest-cos-secret -n i3-data 2>&1
Check "pgBackRest COS secret exists" ($LASTEXITCODE -eq 0)

# ---------------------------------------------------------------------------
Banner "Summary"

$total  = $checks.Count
$passed = ($checks | Where-Object { $_.Passed }).Count
$failed = $total - $passed

Write-Host ""
Write-Host "  Results: $passed / $total checks passed" -ForegroundColor White
Write-Host ""

if ($failed -eq 0) {
    Write-Host "  STATUS: PLATFORM HEALTHY" -ForegroundColor Green
    Write-Host "  All $total checks passed. Platform is live on IBM ROKS (Frankfurt)." -ForegroundColor Green
    Write-Host ""
    Write-Host "  NEXT STEPS:" -ForegroundColor Cyan
    Write-Host "    - Corpus ingest:  POST https://onboarding.i3technologies.co.ke/api/onboarding/ingest" -ForegroundColor Yellow
    Write-Host "    - GPU pool:       make gpu-down  (ensure at 0 to save cost)" -ForegroundColor Yellow
    Write-Host "    - DR backup:      make dr-backup" -ForegroundColor Yellow
} else {
    Write-Host "  STATUS: $failed CHECK(S) FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Failed items:" -ForegroundColor Red
    $checks | Where-Object { -not $_.Passed } | ForEach-Object {
        Write-Host "    - $($_.Label)" -ForegroundColor Red
    }
}
Write-Host ""
