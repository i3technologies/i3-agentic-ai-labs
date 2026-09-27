#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Rebuild and redeploy the admissions-agent and mcp-connectors images.

.DESCRIPTION
    1. Builds both container images from the workspace root (correct COPY context).
    2. Pushes to IBM Container Registry (de.icr.io/i3-platform/).
    3. Applies the updated admissions-deploy.yaml to the cluster.
    4. Performs a rolling restart of the admissions-agent Deployment.
    5. Waits for rollout to complete and runs a smoke test.

.PARAMETER Registry
    ICR registry prefix. Default: de.icr.io/i3-platform

.PARAMETER Tag
    Image tag. Default: latest

.PARAMETER Namespace
    Kubernetes namespace. Default: i3-admissions

.EXAMPLE
    .\deploy-admissions.ps1
    .\deploy-admissions.ps1 -Tag "$(git rev-parse --short HEAD)"
#>
param(
    [string]$Registry  = "de.icr.io/i3-platform",
    [string]$Tag       = "latest",
    [string]$Namespace = "i3-admissions"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AGENT_IMAGE     = "${Registry}/admissions-agent:${Tag}"
$MCP_IMAGE       = "${Registry}/mcp-connectors:${Tag}"
$WORKSPACE_ROOT  = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent  # go up to repo root

Write-Host "`n=== i3 Admissions Agent — Rebuild & Redeploy ===" -ForegroundColor Cyan
Write-Host "Registry  : $Registry"
Write-Host "Tag       : $Tag"
Write-Host "Namespace : $Namespace"
Write-Host "Workspace : $WORKSPACE_ROOT`n"

# ── 0. Pre-flight checks ──────────────────────────────────────────────────────
Write-Host "[0/6] Pre-flight checks..." -ForegroundColor Yellow
foreach ($cmd in @("docker", "oc", "kubectl")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "$cmd is not installed or not in PATH. Aborting."
    }
}

# Verify OC is logged in
$ocWhoami = oc whoami 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not logged into OpenShift. Run: oc login <cluster-url> --token=<token>"
}
Write-Host "  OC logged in as: $ocWhoami" -ForegroundColor Green

# ── 1. Syntax check ───────────────────────────────────────────────────────────
Write-Host "`n[1/6] Python syntax check..." -ForegroundColor Yellow
python -c "import ast; ast.parse(open('platform/admissions/admissions_agent.py').read()); print('  admissions_agent.py: OK')"
python -c "import ast; ast.parse(open('platform/admissions/mcp/mcp_connectors.py').read()); print('  mcp_connectors.py:   OK')"

# ── 2. Build admissions-agent image ──────────────────────────────────────────
Write-Host "`n[2/6] Building admissions-agent image..." -ForegroundColor Yellow
Write-Host "  Image: $AGENT_IMAGE"
# Build MUST run from workspace root so COPY platform/admissions/... paths resolve.
Push-Location $WORKSPACE_ROOT
try {
    docker build `
        --file platform/admissions/Dockerfile `
        --tag $AGENT_IMAGE `
        --label "git.commit=$(git rev-parse HEAD 2>$null)" `
        --label "build.date=$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')" `
        .
    if ($LASTEXITCODE -ne 0) { Write-Error "Docker build failed for admissions-agent" }
    Write-Host "  Build: OK" -ForegroundColor Green
} finally {
    Pop-Location
}

# ── 3. Build mcp-connectors image ────────────────────────────────────────────
Write-Host "`n[3/6] Building mcp-connectors image..." -ForegroundColor Yellow
Write-Host "  Image: $MCP_IMAGE"
Push-Location $WORKSPACE_ROOT
try {
    docker build `
        --file platform/admissions/mcp/Dockerfile `
        --tag $MCP_IMAGE `
        --label "git.commit=$(git rev-parse HEAD 2>$null)" `
        --label "build.date=$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')" `
        .
    if ($LASTEXITCODE -ne 0) { Write-Error "Docker build failed for mcp-connectors" }
    Write-Host "  Build: OK" -ForegroundColor Green
} finally {
    Pop-Location
}

# ── 4. Push images to ICR ─────────────────────────────────────────────────────
Write-Host "`n[4/6] Pushing images to ICR..." -ForegroundColor Yellow
docker push $AGENT_IMAGE
if ($LASTEXITCODE -ne 0) { Write-Error "Push failed for $AGENT_IMAGE" }
Write-Host "  Pushed: $AGENT_IMAGE" -ForegroundColor Green

docker push $MCP_IMAGE
if ($LASTEXITCODE -ne 0) { Write-Error "Push failed for $MCP_IMAGE" }
Write-Host "  Pushed: $MCP_IMAGE" -ForegroundColor Green

# ── 5. Apply manifests and rolling restart ────────────────────────────────────
Write-Host "`n[5/6] Applying manifests and rolling restart..." -ForegroundColor Yellow

# Apply updated deployment YAML (KEYCLOAK_JWKS_URI + KEYCLOAK_ISSUER + MCP_GATEWAY_URL now present)
kubectl apply -f platform/admissions/admissions-deploy.yaml -n $Namespace
if ($LASTEXITCODE -ne 0) { Write-Error "kubectl apply failed" }

# Force a rolling restart to pull the new image (imagePullPolicy: Always)
kubectl rollout restart deployment/admissions-agent  -n $Namespace
kubectl rollout restart deployment/mcp-connectors    -n $Namespace

Write-Host "  Waiting for admissions-agent rollout..." -ForegroundColor DarkGray
kubectl rollout status deployment/admissions-agent -n $Namespace --timeout=300s
if ($LASTEXITCODE -ne 0) { Write-Error "admissions-agent rollout failed. Check: kubectl -n $Namespace get events" }

Write-Host "  Waiting for mcp-connectors rollout..." -ForegroundColor DarkGray
kubectl rollout status deployment/mcp-connectors -n $Namespace --timeout=120s
if ($LASTEXITCODE -ne 0) { Write-Error "mcp-connectors rollout failed. Check: kubectl -n $Namespace get events" }

Write-Host "  Rollout: COMPLETE" -ForegroundColor Green

# ── 6. Smoke test ─────────────────────────────────────────────────────────────
Write-Host "`n[6/6] Smoke tests..." -ForegroundColor Yellow

$smokeUrls = @(
    @{ url = "https://admissions.i3technologies.co.ke/";       expect = "i3 Admissions Assistant"; label = "root /" },
    @{ url = "https://admissions.i3technologies.co.ke/health";  expect = '"status":"ok"';           label = "/health" },
    @{ url = "https://admissions.i3technologies.co.ke/healthz"; expect = '"status":"ok"';           label = "/healthz" }
)

$allPassed = $true
foreach ($check in $smokeUrls) {
    try {
        $resp = Invoke-WebRequest -Uri $check.url -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        if ($resp.StatusCode -eq 200 -and $resp.Content -like "*$($check.expect)*") {
            Write-Host "  [PASS] $($check.label) — HTTP $($resp.StatusCode)" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] $($check.label) — HTTP $($resp.StatusCode) — unexpected body" -ForegroundColor Red
            $allPassed = $false
        }
    } catch {
        Write-Host "  [FAIL] $($check.label) — $($_.Exception.Message)" -ForegroundColor Red
        $allPassed = $false
    }
}

if ($allPassed) {
    Write-Host "`n=== Deployment SUCCEEDED ===" -ForegroundColor Green
    Write-Host "  admissions-agent : $AGENT_IMAGE"
    Write-Host "  mcp-connectors   : $MCP_IMAGE"
    Write-Host "  All smoke tests  : PASS`n"
} else {
    Write-Host "`n=== Deployment completed with SMOKE TEST FAILURES ===" -ForegroundColor Red
    Write-Host "  Check pod logs: kubectl -n $Namespace logs -l app=admissions-agent --tail=50"
    Write-Host "  Check events:   kubectl -n $Namespace get events --sort-by='.lastTimestamp'`n"
    exit 1
}
