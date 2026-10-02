#!/usr/bin/env pwsh
# ============================================================
# i3 OTT Platform — Full Ordered Deployment Script
#
# Deploy Order (dependency-safe):
#   1. Namespace labels
#   2. SeaweedFS (storage — must be up before Directus)
#   3. Directus CMS (VOD catalogue)
#   4. n8n (workflow automation)
#   5. OME (live streaming origin)
#   6. nginx-hls (CDN edge cache)
#   7. OTT Pipeline (FFmpeg + Whisper post-processing)
#   8. TV Portal ImageStream + BuildConfig
#   9. TV Portal build (oc start-build)
#  10. TV Portal Deployment + Service + Route
#
# Prerequisites:
#   - oc login completed
#   - patch-secrets.ps1 already run (all secrets populated)
#   - Git repo accessible from cluster (for BuildConfig)
#
# Usage:
#   .\platform\ott\deploy-ott.ps1
#   .\platform\ott\deploy-ott.ps1 -SkipBuild   # reuse existing image
# ============================================================

param(
    [switch]$SkipBuild = $false,
    [switch]$DryRun    = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$NS       = "i3-ott"
$REPO_ROOT = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

function Write-Step([string]$msg) {
    Write-Host "`n═══ $msg" -ForegroundColor Cyan
}
function Write-OK([string]$msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "  ✗ $msg" -ForegroundColor Red; exit 1 }

function Invoke-OC {
    param([string[]]$Args, [string]$Description)
    Write-Host "  › oc $($Args -join ' ')" -ForegroundColor Gray
    if (-not $DryRun) {
        & oc @Args
        if ($LASTEXITCODE -ne 0) { Write-Fail "Command failed: oc $($Args -join ' ')" }
    }
    if ($Description) { Write-OK $Description }
}

function Wait-Rollout([string]$deployment, [int]$timeoutSecs = 180) {
    Write-Host "  ⏳ Waiting for $deployment rollout..." -ForegroundColor Gray
    if (-not $DryRun) {
        oc rollout status "deployment/$deployment" -n $NS --timeout="${timeoutSecs}s"
        if ($LASTEXITCODE -ne 0) { Write-Fail "Rollout of $deployment timed out" }
        Write-OK "$deployment ready"
    }
}

function Apply-Manifest([string]$RelPath, [string]$Description) {
    $fullPath = Join-Path $REPO_ROOT $RelPath
    if (-not (Test-Path $fullPath)) { Write-Fail "Manifest not found: $fullPath" }
    Invoke-OC @("apply", "-f", $fullPath, "-n", $NS) -Description $Description
}

# ── Pre-flight ────────────────────────────────────────────────
Write-Step "Pre-flight checks"
$who = oc whoami 2>&1
if ($LASTEXITCODE -ne 0) { Write-Fail "Not logged in to OpenShift" }
Write-OK "Logged in as: $who"

$nsExists = oc get ns $NS --no-headers 2>$null
if ($LASTEXITCODE -ne 0) {
    Invoke-OC @("create", "ns", $NS) -Description "Created namespace $NS"
} else {
    Write-OK "Namespace $NS exists"
}

# ── Step 1: SeaweedFS Storage ─────────────────────────────────
Write-Step "Step 1/10 — SeaweedFS Object Storage"
Apply-Manifest "platform/ott/seaweedfs/seaweedfs-deploy.yaml" "SeaweedFS manifests applied"
Write-Warn "SeaweedFS StatefulSets take 2-3 minutes to reach Ready. Proceeding..."

# ── Step 2: Directus CMS ─────────────────────────────────────
Write-Step "Step 2/10 — Directus CMS"
Apply-Manifest "platform/ott/directus/directus-deploy.yaml" "Directus manifests applied"

# ── Step 3: n8n Workflow Engine ───────────────────────────────
Write-Step "Step 3/10 — n8n Workflow Engine"
Apply-Manifest "platform/ott/n8n/n8n-deploy.yaml" "n8n manifests applied"

# ── Step 4: OvenMediaEngine ───────────────────────────────────
Write-Step "Step 4/10 — OvenMediaEngine (OME) Live Streaming Origin"
Apply-Manifest "platform/ott/ome/ome-deploy.yaml" "OME manifests applied"
Write-Warn "OME NLB (ome-ingest) takes 3-5 min to get external IP."
Write-Warn "Run after deploy: oc get svc ome-ingest -n $NS -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"

# ── Step 5: nginx-HLS CDN Edge ───────────────────────────────
Write-Step "Step 5/10 — nginx-HLS CDN Edge Cache"
Apply-Manifest "platform/ott/nginx/nginx-hls.yaml" "nginx-hls manifests applied"

# ── Step 6: OTT Pipeline ─────────────────────────────────────
Write-Step "Step 6/10 — OTT Content Pipeline (FFmpeg + Whisper)"
Apply-Manifest "platform/ott/pipeline/pipeline-deploy.yaml" "OTT pipeline manifests applied"
Write-Warn "Pipeline image must be built separately. See pipeline-build.yaml."

# ── Step 7: TV Portal ImageStream + BuildConfig ───────────────
Write-Step "Step 7/10 — TV Portal: ImageStream + BuildConfig"
Apply-Manifest "platform/ott/tv-portal/tv-portal-build.yaml" "TV Portal BuildConfig applied"

# ── Step 8: Build the TV Portal image ────────────────────────
if ($SkipBuild) {
    Write-Step "Step 8/10 — TV Portal Build [SKIPPED — -SkipBuild flag set]"
    Write-Warn "Reusing existing image in registry. Make sure it was built from latest commit."
} else {
    Write-Step "Step 8/10 — TV Portal: Docker build (Next.js 15 standalone)"
    Write-Host "  › Starting build (this takes 3-5 minutes)..." -ForegroundColor Gray
    if (-not $DryRun) {
        oc start-build tv-portal -n $NS --follow
        if ($LASTEXITCODE -ne 0) { Write-Fail "TV Portal build failed — check: oc logs -n $NS bc/tv-portal" }
        Write-OK "TV Portal image built and pushed to internal registry"
    }
}

# ── Step 9: TV Portal Deployment + Service + Route ───────────
Write-Step "Step 9/10 — TV Portal: Deployment + Service + Route"
Apply-Manifest "platform/ott/tv-portal/tv-portal-deploy.yaml" "TV Portal deployment applied"

# ── Step 10: Wait for critical pods to be ready ──────────────
Write-Step "Step 10/10 — Waiting for rollouts to complete"
Wait-Rollout "directus"    180
Wait-Rollout "n8n"         180
Wait-Rollout "nginx-hls"   120
Wait-Rollout "tv-portal"   180
Wait-Rollout "ott-pipeline" 120

# ── Final status ─────────────────────────────────────────────
Write-Step "Deployment Summary"
Write-Host ""
Write-Host "  Pods:" -ForegroundColor White
if (-not $DryRun) { oc get pods -n $NS -o wide }

Write-Host ""
Write-Host "  Routes:" -ForegroundColor White
if (-not $DryRun) { oc get routes -n $NS }

Write-Host ""
Write-Host "  Services:" -ForegroundColor White
if (-not $DryRun) { oc get svc -n $NS }

Write-Host "`n✅ OTT Platform deployment complete!" -ForegroundColor Green
Write-Host "   TV Portal:  https://tv.i3technologies.co.ke" -ForegroundColor Green
Write-Host "   Directus:   https://cms.i3technologies.co.ke" -ForegroundColor Green
Write-Host "   n8n:        https://n8n.i3technologies.co.ke" -ForegroundColor Green
Write-Host "   HLS CDN:    https://stream.i3technologies.co.ke" -ForegroundColor Green
Write-Host "`n   Run .\platform\ott\verify-ott.ps1 to validate all endpoints." -ForegroundColor Cyan
