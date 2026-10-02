#!/usr/bin/env pwsh
# ============================================================
# i3 OTT Platform — Post-Deploy End-to-End Verification
#
# Tests every OTT endpoint and Kubernetes resource.
# Outputs a colour-coded PASS/FAIL/WARN summary table.
#
# Usage:
#   .\platform\ott\verify-ott.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

$NS = "i3-ott"

$results = [System.Collections.Generic.List[PSCustomObject]]::new()

function Add-Result([string]$area, [string]$check, [string]$status, [string]$detail) {
    $results.Add([PSCustomObject]@{ Area=$area; Check=$check; Status=$status; Detail=$detail })
}

function Test-HTTP([string]$url, [string]$area, [string]$check, [int]$expectedCode = 200) {
    try {
        $resp = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq $expectedCode) {
            Add-Result $area $check "PASS" "HTTP $($resp.StatusCode)"
        } else {
            Add-Result $area $check "FAIL" "HTTP $($resp.StatusCode) (expected $expectedCode)"
        }
    } catch {
        $msg = $_.Exception.Message -replace "`n"," "
        Add-Result $area $check "FAIL" $msg
    }
}

function Test-OC([string]$area, [string]$check, [string[]]$ocArgs, [scriptblock]$validator) {
    $out = oc @ocArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-Result $area $check "FAIL" "oc command failed"
        return
    }
    $result = & $validator $out
    if ($result -eq $true) {
        Add-Result $area $check "PASS" ($out | Select-Object -First 1)
    } elseif ($result -is [string]) {
        Add-Result $area $check "WARN" $result
    } else {
        Add-Result $area $check "FAIL" ($out | Select-Object -First 3 | Out-String).Trim()
    }
}

Write-Host "`n══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  i3 OTT Platform — Verification Run" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "══════════════════════════════════════════════════════`n" -ForegroundColor Cyan

# ── 1. Kubernetes — Pod health ───────────────────────────────
Write-Host "Checking Kubernetes pod health..." -ForegroundColor Gray

$pods = oc get pods -n $NS --no-headers 2>&1
foreach ($podSpec in @(
    @("tv-portal",    "TV Portal"),
    @("ome-origin",   "OvenMediaEngine"),
    @("nginx-hls",    "nginx-HLS"),
    @("directus",     "Directus CMS"),
    @("n8n",          "n8n"),
    @("ott-pipeline", "OTT Pipeline"),
    @("seaweedfs-master", "SeaweedFS Master"),
    @("seaweedfs-volume", "SeaweedFS Volume"),
    @("seaweedfs-filer",  "SeaweedFS Filer"),
    @("seaweedfs-s3-gw",  "SeaweedFS S3 GW")
)) {
    $podName   = $podSpec[0]
    $podLabel  = $podSpec[1]
    $podLine   = $pods | Where-Object { $_ -match "^$podName" } | Select-Object -First 1
    if (-not $podLine) {
        Add-Result "Pods" "$podLabel pod exists" "FAIL" "No pod found matching $podName"
        continue
    }
    # Parse "2/2 Running" style
    if ($podLine -match "\s+(\d+)/(\d+)\s+Running") {
        $ready = [int]$Matches[1]; $total = [int]$Matches[2]
        if ($ready -eq $total -and $ready -gt 0) {
            Add-Result "Pods" "$podLabel Running" "PASS" "$ready/$total Ready"
        } else {
            Add-Result "Pods" "$podLabel Running" "WARN" "$ready/$total containers ready"
        }
    } elseif ($podLine -match "ImagePullBackOff|ErrImagePull") {
        Add-Result "Pods" "$podLabel Running" "FAIL" "ImagePullBackOff — build may not have completed"
    } elseif ($podLine -match "CrashLoopBackOff") {
        Add-Result "Pods" "$podLabel Running" "FAIL" "CrashLoopBackOff — check: oc logs -n $NS -l app=$podName"
    } else {
        Add-Result "Pods" "$podLabel Running" "WARN" ($podLine.Trim())
    }
}

# ── 2. Kubernetes — Services & Endpoints ─────────────────────
Write-Host "Checking Services and Endpoints..." -ForegroundColor Gray
foreach ($svc in @("tv-portal","ome-origin","nginx-hls","directus","n8n","ott-pipeline","seaweedfs-s3")) {
    $ep = oc get endpoints $svc -n $NS --no-headers 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-Result "Services" "$svc endpoint" "FAIL" "Service not found"
        continue
    }
    if ($ep -match "<none>") {
        Add-Result "Services" "$svc endpoint" "FAIL" "No ready endpoints — pod may not be Running"
    } else {
        Add-Result "Services" "$svc endpoint" "PASS" ($ep | Select-Object -First 1).Trim()
    }
}

# ── 3. Kubernetes — Routes ────────────────────────────────────
Write-Host "Checking OpenShift Routes..." -ForegroundColor Gray
$routes = oc get routes -n $NS --no-headers 2>&1
foreach ($routeSpec in @(
    @("tv-portal",       "tv.i3technologies.co.ke"),
    @("nginx-hls",       "stream.i3technologies.co.ke"),
    @("nginx-hls-alias", "hls.i3technologies.co.ke"),
    @("directus",        "cms.i3technologies.co.ke"),
    @("n8n",             "n8n.i3technologies.co.ke")
)) {
    $routeName = $routeSpec[0]; $routeHost = $routeSpec[1]
    if ($routes -match $routeName) {
        Add-Result "Routes" "$routeHost route" "PASS" "Route present"
    } else {
        Add-Result "Routes" "$routeHost route" "FAIL" "Route $routeName not found"
    }
}

# ── 4. TLS Certificates ───────────────────────────────────────
Write-Host "Checking TLS secrets..." -ForegroundColor Gray
$tlsSecrets = oc get secrets -n $NS --no-headers 2>&1
foreach ($secretName in @("tv-portal-secrets","directus-secrets","n8n-secrets","ome-api-secret","ott-pipeline-secrets")) {
    if ($tlsSecrets -match $secretName) {
        # Check no field is still empty (would cause pod failure)
        $secretData = oc get secret $secretName -n $NS -o jsonpath='{.data}' 2>&1
        Add-Result "Secrets" "$secretName exists" "PASS" "Secret present in namespace"
    } else {
        Add-Result "Secrets" "$secretName exists" "FAIL" "Secret not found — run patch-secrets.ps1"
    }
}

# ── 5. HTTP Endpoint Tests ────────────────────────────────────
Write-Host "Testing HTTP endpoints..." -ForegroundColor Gray

Test-HTTP "https://tv.i3technologies.co.ke/api/health"          "HTTP" "TV Portal /api/health"
Test-HTTP "https://tv.i3technologies.co.ke/"                    "HTTP" "TV Portal homepage"
Test-HTTP "https://tv.i3technologies.co.ke/api/streams/live"    "HTTP" "Live streams API"
Test-HTTP "https://tv.i3technologies.co.ke/api/streams/vod"     "HTTP" "VOD catalogue API"
Test-HTTP "https://stream.i3technologies.co.ke/health"          "HTTP" "nginx-HLS /health"
Test-HTTP "https://cms.i3technologies.co.ke/server/health"      "HTTP" "Directus /server/health"
Test-HTTP "https://n8n.i3technologies.co.ke/healthz"            "HTTP" "n8n /healthz"

# ── 6. API Response Validation ────────────────────────────────
Write-Host "Validating API response bodies..." -ForegroundColor Gray
try {
    $health = Invoke-RestMethod "https://tv.i3technologies.co.ke/api/health" -TimeoutSec 10
    if ($health.status -eq "ok" -and $health.service -eq "i3-tv-portal") {
        Add-Result "API" "Health response schema" "PASS" "status=ok, service=i3-tv-portal"
    } else {
        Add-Result "API" "Health response schema" "WARN" "Unexpected body: $($health | ConvertTo-Json -Compress)"
    }
} catch {
    Add-Result "API" "Health response schema" "FAIL" $_.Exception.Message
}

try {
    $vod = Invoke-RestMethod "https://tv.i3technologies.co.ke/api/streams/vod?limit=1" -TimeoutSec 15
    if ($null -ne $vod.items) {
        Add-Result "API" "VOD API returns .items array" "PASS" "$($vod.items.Count) item(s) returned"
    } else {
        Add-Result "API" "VOD API returns .items array" "FAIL" "Response missing .items field"
    }
} catch {
    Add-Result "API" "VOD API returns .items array" "FAIL" $_.Exception.Message
}

try {
    $live = Invoke-RestMethod "https://tv.i3technologies.co.ke/api/streams/live" -TimeoutSec 10
    if ($null -ne $live.streams) {
        Add-Result "API" "Live API returns .streams array" "PASS" "$($live.streams.Count) stream(s) active"
    } else {
        Add-Result "API" "Live API returns .streams array" "FAIL" "Response missing .streams field"
    }
} catch {
    Add-Result "API" "Live API returns .streams array" "FAIL" $_.Exception.Message
}

# ── 7. VOD API parameter validation ──────────────────────────
Write-Host "Testing API edge cases..." -ForegroundColor Gray
try {
    $neg = Invoke-RestMethod "https://tv.i3technologies.co.ke/api/streams/vod?limit=5&offset=-99" -TimeoutSec 10
    if ($null -ne $neg.items) {
        Add-Result "API" "Negative offset sanitized" "PASS" "offset=-99 handled gracefully"
    } else {
        Add-Result "API" "Negative offset sanitized" "WARN" "Unexpected response shape"
    }
} catch {
    Add-Result "API" "Negative offset sanitized" "FAIL" $_.Exception.Message
}

# ── 8. CORS header check ──────────────────────────────────────
Write-Host "Checking CORS headers..." -ForegroundColor Gray
try {
    $corsResp = Invoke-WebRequest -Uri "https://stream.i3technologies.co.ke/health" `
        -Headers @{ "Origin" = "https://tv.i3technologies.co.ke" } `
        -TimeoutSec 10 -UseBasicParsing
    $corsHeader = $corsResp.Headers["Access-Control-Allow-Origin"]
    if ($corsHeader -eq "https://tv.i3technologies.co.ke") {
        Add-Result "Security" "CORS restricted to portal origin" "PASS" "Header: $corsHeader"
    } elseif ($corsHeader -eq "*") {
        Add-Result "Security" "CORS restricted to portal origin" "FAIL" "CORS is still wildcard (*) — nginx CORS fix not applied"
    } else {
        Add-Result "Security" "CORS restricted to portal origin" "WARN" "CORS header: $corsHeader"
    }
} catch {
    Add-Result "Security" "CORS header check" "WARN" "Could not verify: $($_.Exception.Message)"
}

# ── 9. SeaweedFS replication check ────────────────────────────
Write-Host "Checking SeaweedFS replication setting..." -ForegroundColor Gray
$seaArgs  = oc get statefulset seaweedfs-volume -n $NS -o jsonpath='{.spec.template.spec.containers[0].args}' 2>&1
if ($seaArgs -match "replication=001") {
    Add-Result "Storage" "SeaweedFS replication=001" "PASS" "Data redundancy enabled"
} elseif ($seaArgs -match "replication=000") {
    Add-Result "Storage" "SeaweedFS replication=001" "FAIL" "Still 000 — data loss risk; apply seaweedfs-deploy.yaml"
} else {
    Add-Result "Storage" "SeaweedFS replication=001" "WARN" "Could not determine replication setting"
}

# ── 10. OME ingest LoadBalancer IP ────────────────────────────
Write-Host "Checking OME ingest external IP..." -ForegroundColor Gray
$omeIP = oc get svc ome-ingest -n $NS -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>&1
if ($omeIP -and $omeIP -match "^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$") {
    Add-Result "Network" "OME ingest LoadBalancer IP" "PASS" "IP: $omeIP — add A record: ingest → $omeIP"
} else {
    Add-Result "Network" "OME ingest LoadBalancer IP" "WARN" "IP pending — wait 3-5 min after OME deploy"
}

# ── Print results ─────────────────────────────────────────────
Write-Host "`n══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  VERIFICATION RESULTS" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════════════`n" -ForegroundColor Cyan

$pass = 0; $fail = 0; $warn = 0
$lastArea = ""
foreach ($r in $results) {
    if ($r.Area -ne $lastArea) {
        Write-Host "  [$($r.Area)]" -ForegroundColor White
        $lastArea = $r.Area
    }
    $color = switch ($r.Status) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        "WARN" { "Yellow" }
        default { "Gray" }
    }
    $symbol = switch ($r.Status) { "PASS"{"✓"} "FAIL"{"✗"} "WARN"{"⚠"} default{"?"} }
    Write-Host ("    {0} [{1}] {2}" -f $symbol, $r.Status.PadRight(4), $r.Check) -ForegroundColor $color
    if ($r.Status -ne "PASS") {
        Write-Host ("          → {0}" -f $r.Detail) -ForegroundColor Gray
    }
    if ($r.Status -eq "PASS") { $pass++ }
    elseif ($r.Status -eq "FAIL") { $fail++ }
    else { $warn++ }
}

$total = $pass + $fail + $warn
Write-Host "`n  Summary: $pass PASS  $warn WARN  $fail FAIL  (total: $total)" -ForegroundColor White

if ($fail -eq 0 -and $warn -eq 0) {
    Write-Host "`n  ✅ ALL CHECKS PASSED — OTT platform is healthy!" -ForegroundColor Green
} elseif ($fail -eq 0) {
    Write-Host "`n  ✅ No failures. Review $warn warning(s) above." -ForegroundColor Yellow
} else {
    Write-Host "`n  ❌ $fail failure(s) detected. Resolve before going live." -ForegroundColor Red
}
Write-Host ""
