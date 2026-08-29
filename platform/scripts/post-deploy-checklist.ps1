#!/usr/bin/env pwsh
# ============================================================
# i3 Platform — Full Post-Deploy Health Check
# PURPOSE:
#   Validates the complete platform after `make deploy-infra`
#   and all operator/app deploys. Prints a PASS/FAIL summary.
#
# PREREQUISITES:
#   - oc is configured against i3-platform cluster
#   - All `make deploy-*` targets have been run
#
# USAGE:
#   . .\platform\scripts\load-env.ps1
#   .\platform\scripts\post-deploy-checklist.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

$oc = "oc"
$PASS = "[PASS]"
$FAIL = "[FAIL]"
$WARN = "[WARN]"
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
Banner "1 — Namespace Topology"

$requiredNs = @(
    "i3-data", "i3-messaging", "i3-security", "i3-auth", "i3-gitops",
    "i3-model-gateway", "i3-ai-lab", "i3-evalos", "i3-ott", "i3-admissions", "i3-monitoring"
)

foreach ($ns in $requiredNs) {
    $result = & $oc get ns $ns 2>&1
    Check "Namespace '$ns' exists" ($LASTEXITCODE -eq 0)
}

# Solution namespaces must be untouched
$solutionNsTouched = $false
for ($i = 1; $i -le 8; $i++) {
    $sn = "solution-0$i"
    & $oc get ns $sn 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        # Exists — verify we haven't added any pods
        $pods = & $oc get pods -n $sn --no-headers 2>&1
        if ($pods -and $pods.Count -gt 0 -and $pods -notmatch "No resources found") {
            $solutionNsTouched = $true
            Write-Host "  $FAIL solution namespace '$sn' has pods — MUST be untouched!" -ForegroundColor Red
        }
    }
}
Check "solution-01..08 namespaces untouched" (-not $solutionNsTouched)

# ---------------------------------------------------------------------------
Banner "2 — Core Operators"

# PostgreSQL
$pgPods = & $oc get pods -n i3-data -l "postgres-operator.crunchydata.com/cluster=i3-postgres" --no-headers 2>&1
$pgReady = ($pgPods | Where-Object { $_ -match "Running" }).Count -ge 3
Check "Crunchy PostgreSQL HA (3 pods Running)" $pgReady $pgPods

# Kafka KRaft
$kafkaPods = & $oc get pods -n i3-messaging -l "strimzi.io/kind=Kafka" --no-headers 2>&1
$kafkaReady = ($kafkaPods | Where-Object { $_ -match "Running" }).Count -ge 3
Check "Strimzi Kafka KRaft (3 pods Running)" $kafkaReady $kafkaPods

# OpenBao
$baoPods = & $oc get pods -n i3-security -l "app.kubernetes.io/name=openbao" --no-headers 2>&1
$baoReady = ($baoPods | Where-Object { $_ -match "Running" }).Count -ge 3
Check "OpenBao (3 pods Running)" $baoReady $baoPods

# Keycloak
$kcPods = & $oc get pods -n i3-auth -l "app=keycloak" --no-headers 2>&1
$kcReady = ($kcPods | Where-Object { $_ -match "Running" }).Count -ge 1
Check "Keycloak (1+ pods Running)" $kcReady $kcPods

# ---------------------------------------------------------------------------
Banner "3 — Model Gateway"

$litellmPods = & $oc get pods -n i3-model-gateway -l "app=litellm-proxy" --no-headers 2>&1
Check "LiteLLM proxy Running" ($litellmPods -match "Running")

$ollamaPods = & $oc get pods -n i3-model-gateway -l "app=ollama" --no-headers 2>&1
Check "Ollama (Granite 3.1 2B) Running" ($ollamaPods -match "Running")

$langfusePods = & $oc get pods -n i3-model-gateway -l "app=langfuse" --no-headers 2>&1
Check "Langfuse Running" ($langfusePods -match "Running")

# ---------------------------------------------------------------------------
Banner "4 — EvalOS"

$evalSandbox = & $oc get pods -n i3-evalos -l "app=evalos-sandbox" --no-headers 2>&1
Check "EvalOS sandbox daemon Running" ($evalSandbox -match "Running")

$evalEngine = & $oc get pods -n i3-evalos -l "app=evalos-engine" --no-headers 2>&1
Check "EvalOS exam engine Running" ($evalEngine -match "Running")

# ---------------------------------------------------------------------------
Banner "5 — OTT Stack"

$omePods = & $oc get pods -n i3-ott -l "app=ovenmediaengine" --no-headers 2>&1
Check "OvenMediaEngine Running" ($omePods -match "Running")

$nginxPods = & $oc get pods -n i3-ott -l "app=nginx-hls" --no-headers 2>&1
Check "Nginx HLS cache Running" ($nginxPods -match "Running")

$seaweedMaster = & $oc get pods -n i3-ott -l "app=seaweedfs-master" --no-headers 2>&1
Check "SeaweedFS master Running" ($seaweedMaster -match "Running")

$seaweedVol = & $oc get pods -n i3-ott -l "app=seaweedfs-volume" --no-headers 2>&1
$seaweedVolReady = ($seaweedVol | Where-Object { $_ -match "Running" }).Count -ge 3
Check "SeaweedFS volumes (3 Running)" $seaweedVolReady

$directusPods = & $oc get pods -n i3-ott -l "app=directus" --no-headers 2>&1
Check "Directus CMS Running" ($directusPods -match "Running")

$n8nPods = & $oc get pods -n i3-ott -l "app=n8n" --no-headers 2>&1
Check "n8n automation Running" ($n8nPods -match "Running")

# ---------------------------------------------------------------------------
Banner "6 — Admissions AI"

$admPods = & $oc get pods -n i3-admissions -l "app=admissions-agent" --no-headers 2>&1
Check "Admissions agent Running" ($admPods -match "Running")

$chromaPods = & $oc get pods -n i3-admissions -l "app=chromadb" --no-headers 2>&1
Check "ChromaDB Running" ($chromaPods -match "Running")

# ---------------------------------------------------------------------------
Banner "7 — GitOps / CI"

$argoPods = & $oc get pods -n i3-gitops -l "app.kubernetes.io/name=argocd-server" --no-headers 2>&1
Check "Argo CD server Running" ($argoPods -match "Running")

$argoSync = & $oc get applications -n i3-gitops -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.sync.status}{"\n"}{end}' 2>&1
if ($argoSync) {
    $notSynced = $argoSync | Where-Object { $_ -match "OutOfSync" -or $_ -match "Unknown" }
    Check "Argo CD applications synced" ($notSynced.Count -eq 0) ($argoSync -join "; ")
} else {
    WarnCheck "Argo CD applications (no apps found yet)"
}

# ---------------------------------------------------------------------------
Banner "8 — Monitoring"

$promPods = & $oc get pods -n i3-monitoring -l "app=prometheus" --no-headers 2>&1
Check "Prometheus Running" ($promPods -match "Running")

$grafanaPods = & $oc get pods -n i3-monitoring -l "app=grafana" --no-headers 2>&1
Check "Grafana Running" ($grafanaPods -match "Running")

# ---------------------------------------------------------------------------
Banner "9 — Routes / Ingress"

$routes = @(
    @{ host = "litellm.i3technologies.co.ke";    ns = "i3-model-gateway" },
    @{ host = "langfuse.i3technologies.co.ke";   ns = "i3-model-gateway" },
    @{ host = "evalos.i3technologies.co.ke";     ns = "i3-evalos" },
    @{ host = "directus.i3technologies.co.ke";   ns = "i3-ott" },
    @{ host = "grafana.i3technologies.co.ke";    ns = "i3-monitoring" },
    @{ host = "keycloak.i3technologies.co.ke";   ns = "i3-auth" },
    @{ host = "argocd.i3technologies.co.ke";     ns = "i3-gitops" }
)

foreach ($r in $routes) {
    $routeCheck = & $oc get route -n $r.ns --no-headers 2>&1
    $found = $routeCheck -match $r.host
    if ($found) {
        Check "Route $($r.host) exists" $true
    } else {
        WarnCheck "Route $($r.host) — not yet created (add DNS CNAME after ingress hostname is known)"
    }
}

# ---------------------------------------------------------------------------
Banner "10 — Secret Population"

$vaultSecretPaths = @(
    @{ ns = "i3-model-gateway"; secret = "litellm-secrets" },
    @{ ns = "i3-ott";           secret = "directus-secrets" },
    @{ ns = "i3-ott";           secret = "rclone-secrets" },
    @{ ns = "i3-monitoring";    secret = "grafana-secrets" }
)

foreach ($s in $vaultSecretPaths) {
    $result = & $oc get secret $s.secret -n $s.ns 2>&1
    Check "Secret '$($s.secret)' in $($s.ns)" ($LASTEXITCODE -eq 0)
}

# ---------------------------------------------------------------------------
Banner "Summary"

$total  = $checks.Count
$passed = ($checks | Where-Object { $_.Passed }).Count
$failed = $total - $passed

Write-Host ""
Write-Host "Results: $passed / $total checks passed" -ForegroundColor White

if ($failed -eq 0) {
    Write-Host "" 
    Write-Host "  STATUS: PLATFORM HEALTHY — ready for Month 3 RHOAI install" -ForegroundColor Green
    Write-Host ""
    Write-Host "  NEXT: Run load tests" -ForegroundColor Cyan
    Write-Host "    make test-all" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "  STATUS: $failed CHECK(S) FAILED — review output above" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Failed checks:" -ForegroundColor Red
    $checks | Where-Object { -not $_.Passed } | ForEach-Object {
        Write-Host "    - $($_.Label)" -ForegroundColor Red
    }
}
Write-Host ""
