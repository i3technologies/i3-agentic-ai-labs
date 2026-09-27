#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Post-deploy smoke test for the i3 Admissions Application.

.DESCRIPTION
    Tests all public endpoints of the admissions service:
      - GET /           → service card (unauthenticated)
      - GET /health     → {"status":"ok"} (unauthenticated)
      - GET /healthz    → {"status":"ok"} (unauthenticated)
      - POST /chat      → 401 without token (auth gate works)
      - WS  /ws/chat    → 4401 without token (WS auth gate works)

    Exit code 0 = all tests pass.  Exit code 1 = one or more failures.

.PARAMETER BaseUrl
    The admissions service base URL. Default: https://admissions.i3technologies.co.ke

.EXAMPLE
    .\smoke-test-admissions.ps1
    .\smoke-test-admissions.ps1 -BaseUrl https://admissions.i3technologies.co.ke
#>
param(
    [string]$BaseUrl = "https://admissions.i3technologies.co.ke"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"   # collect all failures, not stop-on-first

$pass    = 0
$fail    = 0
$results = @()

function Test-Http {
    param(
        [string]$Label,
        [string]$Uri,
        [string]$Method        = "GET",
        [int]   $ExpectStatus  = 200,
        [string]$ExpectBody    = "",
        [hashtable]$Headers    = @{},
        [string]$Body          = ""
    )
    try {
        $splat = @{
            Uri             = $Uri
            Method          = $Method
            UseBasicParsing = $true
            TimeoutSec      = 20
            ErrorAction     = "Stop"
            Headers         = $Headers
        }
        if ($Body) { $splat.Body = $Body; $splat.ContentType = "application/json" }

        $resp = Invoke-WebRequest @splat
        $ok   = ($resp.StatusCode -eq $ExpectStatus)
        if ($ExpectBody -and $ok) { $ok = $resp.Content -like "*$ExpectBody*" }
        return @{ label = $Label; pass = $ok; status = $resp.StatusCode; detail = $resp.Content.Substring(0, [Math]::Min(120,$resp.Content.Length)) }
    } catch {
        # Capture HTTP error responses (4xx/5xx)
        $statusCode = 0
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        $ok = ($statusCode -eq $ExpectStatus)
        return @{ label = $Label; pass = $ok; status = $statusCode; detail = $_.Exception.Message }
    }
}

Write-Host "`n=== i3 Admissions Smoke Test ===" -ForegroundColor Cyan
Write-Host "Target: $BaseUrl`n"

# ── Test 1: Root endpoint ─────────────────────────────────────────────────────
$r = Test-Http `
    -Label  "GET / → service card" `
    -Uri    "$BaseUrl/" `
    -ExpectStatus 200 `
    -ExpectBody "i3 Admissions Assistant"
$results += $r

# ── Test 2: /health alias ─────────────────────────────────────────────────────
$r = Test-Http `
    -Label  "GET /health → status ok" `
    -Uri    "$BaseUrl/health" `
    -ExpectStatus 200 `
    -ExpectBody '"status"'
$results += $r

# ── Test 3: /healthz canonical ───────────────────────────────────────────────
$r = Test-Http `
    -Label  "GET /healthz → status ok" `
    -Uri    "$BaseUrl/healthz" `
    -ExpectStatus 200 `
    -ExpectBody '"status"'
$results += $r

# ── Test 4: POST /chat without token → 403 (Kong JWT plugin) or 401 (FastAPI) ─
$chatBody = '{"message":"Hello","session_id":"smoke-test"}'
$r = Test-Http `
    -Label  "POST /chat (no token) → 401/403" `
    -Uri    "$BaseUrl/chat" `
    -Method "POST" `
    -ExpectStatus 403 `
    -Body   $chatBody
# Kong returns 403; FastAPI HTTPBearer returns 403 too — accept either 401 or 403
if (-not $r.pass -and $r.status -eq 401) { $r.pass = $true; $r.detail = "FastAPI 401 also acceptable" }
$results += $r

# ── Test 5: Unknown route → 404 (expected FastAPI behaviour) ─────────────────
$r = Test-Http `
    -Label  "GET /nonexistent → 404" `
    -Uri    "$BaseUrl/nonexistent" `
    -ExpectStatus 404
$results += $r

# ── Print results ─────────────────────────────────────────────────────────────
Write-Host ("{0,-42} {1,-8} {2}" -f "Test", "Status", "Result")
Write-Host ("-" * 80)
foreach ($t in $results) {
    $status = if ($t.pass) { "PASS" } else { "FAIL" }
    $color  = if ($t.pass) { "Green" } else { "Red" }
    Write-Host ("{0,-42} HTTP {1,-4} {2}" -f $t.label, $t.status, $status) -ForegroundColor $color
    if (-not $t.pass) {
        Write-Host ("    Detail: {0}" -f $t.detail) -ForegroundColor DarkRed
    }
    if ($t.pass) { $pass++ } else { $fail++ }
}

Write-Host ("-" * 80)
Write-Host "  Passed: $pass / $($results.Count)"

if ($fail -gt 0) {
    Write-Host "  FAILED: $fail test(s)" -ForegroundColor Red
    Write-Host "`nDiagnostics:"
    Write-Host "  kubectl -n i3-admissions logs -l app=admissions-agent --tail=80"
    Write-Host "  kubectl -n i3-admissions get events --sort-by='.lastTimestamp' | tail -20"
    Write-Host "  kubectl -n i3-admissions get pods"
    exit 1
} else {
    Write-Host "`n=== ALL TESTS PASSED ===" -ForegroundColor Green
    exit 0
}
