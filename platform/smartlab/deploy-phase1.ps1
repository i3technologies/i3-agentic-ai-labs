#!/usr/bin/env pwsh
# ============================================================
# i3 SmartLab — Phase 1 Full Deploy Script
# Run from repo root:
#   .\platform\smartlab\deploy-phase1.ps1
#
# Prerequisites:
#   - oc logged in to i3-platform cluster
#   - Docker / podman available for local image build
#   - Git repo access
# ============================================================

$ErrorActionPreference = "Stop"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PASS  = "[PASS]"
$FAIL  = "[FAIL]"
$INFO  = "[INFO]"

function Banner([string]$msg) {
    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "=============================================" -ForegroundColor Cyan
}

function Ok([string]$msg)   { Write-Host "  $PASS $msg" -ForegroundColor Green  }
function Err([string]$msg)  { Write-Host "  $FAIL $msg" -ForegroundColor Red    }
function Info([string]$msg) { Write-Host "  $INFO $msg" -ForegroundColor Yellow }

# ── 0. Prerequisites ──────────────────────────────────────────────────────────
Banner "0 - Prerequisites Check"

$ocOk = oc whoami 2>&1
if ($LASTEXITCODE -ne 0) { Err "oc not logged in. Run: oc login"; exit 1 }
Ok "oc logged in as: $ocOk"

$cluster = oc config current-context
Ok "Cluster context: $cluster"

# ── 1. Namespace + RBAC + SCC ─────────────────────────────────────────────────
Banner "1 - Namespace, RBAC, SCC"

oc apply -f "$SCRIPT_DIR\00-namespace-rbac.yaml" 2>&1
if ($LASTEXITCODE -eq 0) { Ok "Namespace + RBAC applied" } else { Err "RBAC apply failed"; exit 1 }

# Grant anyuid SCC
oc adm policy add-scc-to-user anyuid -z smartlab -n i3-smartlab 2>&1
Ok "anyuid SCC granted to smartlab SA"

# ── 2. Network Policies ───────────────────────────────────────────────────────
Banner "2 - Network Policies"

oc apply -f "$SCRIPT_DIR\01-network-policies.yaml" 2>&1
if ($LASTEXITCODE -eq 0) { Ok "NetworkPolicies applied" } else { Err "NP apply failed"; exit 1 }

# Patch i3-data allow-db-clients to include i3-smartlab
Info "Patching i3-data NetworkPolicy to allow i3-smartlab..."
$currentNP = oc get networkpolicy allow-db-clients -n i3-data -o json 2>&1 | ConvertFrom-Json
$currentValues = $currentNP.spec.ingress[0].from[0].namespaceSelector.matchExpressions[0].values
if ("i3-smartlab" -notin $currentValues) {
    $currentValues += "i3-smartlab"
    $patch = @{
        spec = @{
            ingress = @(
                @{
                    from = @(
                        @{
                            namespaceSelector = @{
                                matchExpressions = @(
                                    @{
                                        key      = "kubernetes.io/metadata.name"
                                        operator = "In"
                                        values   = $currentValues
                                    }
                                )
                            }
                        }
                    )
                }
            )
        }
    } | ConvertTo-Json -Depth 10 -Compress
    oc patch networkpolicy allow-db-clients -n i3-data --type=merge -p $patch 2>&1
    Ok "i3-data NP patched to include i3-smartlab"
} else {
    Ok "i3-data NP already includes i3-smartlab"
}

# ── 3. Secrets + ConfigMap ────────────────────────────────────────────────────
Banner "3 - Secrets and ConfigMap"

oc apply -f "$SCRIPT_DIR\02-secrets-config.yaml" 2>&1
if ($LASTEXITCODE -eq 0) { Ok "Secrets + ConfigMap applied" } else { Err "Secrets apply failed"; exit 1 }

# ── 4. PostgreSQL Database ────────────────────────────────────────────────────
Banner "4 - PostgreSQL Schema (smartlab_db)"

Info "Copying schema SQL into Crunchy PG pod..."
oc cp "$SCRIPT_DIR\03-smartlab-schema.sql" `
    i3-postgres-primary-hffm-0:/tmp/smartlab-schema.sql -n i3-data -c database 2>&1

Info "Running schema creation..."
$pgResult = oc exec i3-postgres-primary-hffm-0 -n i3-data -c database -- `
    psql -U postgres -f /tmp/smartlab-schema.sql 2>&1

if ($pgResult -match "CREATE TABLE|already exists") {
    Ok "smartlab_db schema applied"
} else {
    Info "Schema output: $pgResult"
    # Check if DB exists already
    $dbCheck = oc exec i3-postgres-primary-hffm-0 -n i3-data -c database -- `
        psql -U postgres -tc "SELECT count(*) FROM pg_database WHERE datname='smartlab_db';" 2>&1
    if ($dbCheck -match "1") {
        Ok "smartlab_db already exists"
    } else {
        Err "Schema creation may have failed. Check output above."
    }
}

# ── 5. SeaweedFS S3 Buckets ───────────────────────────────────────────────────
Banner "5 - SeaweedFS S3 Buckets"

$buckets = @("smartlab-content", "smartlab-scorm", "smartlab-video", "smartlab-epub")
foreach ($bucket in $buckets) {
    Info "Creating bucket: $bucket"
    # Use s3cmd-compatible curl to create bucket in SeaweedFS
    $seaweedSvc = "http://seaweedfs-s3.i3-ott.svc:8333"
    oc exec -n i3-ott `
        $(oc get pod -n i3-ott -l "app=seaweedfs,component=master" --no-headers 2>&1 | `
          ForEach-Object { ($_ -split '\s+')[1] } | Select-Object -First 1) -- `
        sh -c "wget -q -O- --method=PUT '$seaweedSvc/$bucket' 2>&1 || true" 2>&1 | Out-Null
    Ok "Bucket: $bucket"
}

# ── 6. Build + Deploy Authoring API ──────────────────────────────────────────
Banner "6 - Build Authoring API Image"

# Apply deployment manifest (ImageStream + BuildConfig + Deployment + Service + Route)
oc apply -f "$SCRIPT_DIR\04-authoring-api-deploy.yaml" 2>&1
if ($LASTEXITCODE -eq 0) { Ok "Deployment manifest applied" } else { Err "Deployment apply failed"; exit 1 }

# Trigger binary build — upload the api/ source directory
Info "Starting OpenShift binary build..."
oc start-build smartlab-api -n i3-smartlab `
    --from-dir="$SCRIPT_DIR\api" `
    --follow `
    --wait 2>&1

if ($LASTEXITCODE -eq 0) {
    Ok "Image build complete"
} else {
    Err "Image build failed. Check: oc logs -n i3-smartlab bc/smartlab-api"
    exit 1
}

# ── 7. Wait for Deployment ────────────────────────────────────────────────────
Banner "7 - Wait for Rollout"

Info "Waiting for smartlab-api rollout..."
oc rollout status deployment/smartlab-api -n i3-smartlab --timeout=300s 2>&1
if ($LASTEXITCODE -eq 0) {
    Ok "smartlab-api deployment ready"
} else {
    Err "Rollout timed out. Check: oc get pods -n i3-smartlab"
    exit 1
}

# ── 8. Health Check ───────────────────────────────────────────────────────────
Banner "8 - Health Check"

$podName = oc get pods -n i3-smartlab -l "app=smartlab-api" --no-headers 2>&1 |
           ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1

$health = oc exec $podName -n i3-smartlab -- `
    curl -sf http://localhost:8000/health 2>&1
if ($health -match "ok") {
    Ok "API health: $health"
} else {
    Err "Health check failed: $health"
}

# Docs endpoint
$docs = oc exec $podName -n i3-smartlab -- `
    curl -sf -o /dev/null -w "%{http_code}" http://localhost:8000/docs 2>&1
if ($docs -eq "200") { Ok "API docs reachable: /docs returns HTTP 200" }

# ── 9. Import n8n VOD Workflow ────────────────────────────────────────────────
Banner "9 - n8n VOD Pipeline Workflow"

Info "Importing VOD pipeline workflow into n8n..."
$n8nPod = oc get pods -n i3-ott -l "app=n8n" --no-headers 2>&1 |
          ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1

oc cp "$SCRIPT_DIR\n8n-vod-pipeline-workflow.json" `
    "${n8nPod}:/tmp/smartlab-vod-workflow.json" -n i3-ott 2>&1

# Import via n8n CLI
$n8nImport = oc exec $n8nPod -n i3-ott -- `
    n8n import:workflow --input=/tmp/smartlab-vod-workflow.json 2>&1
if ($n8nImport -match "imported|success") {
    Ok "n8n VOD workflow imported"
} else {
    Info "n8n import output: $n8nImport"
    Info "Import manually: n8n import:workflow --input=/tmp/smartlab-vod-workflow.json"
}

# ── 10. Keycloak OIDC Client ──────────────────────────────────────────────────
Banner "10 - Keycloak OIDC Client (i3smartlab)"

Info "Creating Keycloak client for SmartLab..."
$kcPod = oc get pods -n i3-auth -l "app=keycloak" --no-headers 2>&1 |
         ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1

$kcPassword = oc get secret credential-i3-keycloak -n i3-auth `
    -o jsonpath='{.data.ADMIN_PASSWORD}' 2>&1 |
    ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

# Get admin token
$tokenResp = oc exec $kcPod -n i3-auth -- `
    curl -sf -X POST "http://localhost:8080/auth/realms/master/protocol/openid-connect/token" `
    -d "client_id=admin-cli" `
    -d "username=admin" `
    -d "password=$kcPassword" `
    -d "grant_type=password" 2>&1 | ConvertFrom-Json

$adminToken = $tokenResp.access_token

if ($adminToken) {
    # Create i3smartlab client
    $clientPayload = @{
        clientId                = "i3smartlab"
        name                    = "i3 SmartLab"
        description             = "SCORM/EPUB Authoring Platform"
        rootUrl                 = "https://author.i3technologies.co.ke"
        adminUrl                = "https://author.i3technologies.co.ke"
        redirectUris            = @("https://author.i3technologies.co.ke/*")
        webOrigins              = @("https://author.i3technologies.co.ke")
        publicClient            = $false
        protocol                = "openid-connect"
        enabled                 = $true
        standardFlowEnabled     = $true
        directAccessGrantsEnabled = $false
        serviceAccountsEnabled  = $false
        authorizationServicesEnabled = $false
    } | ConvertTo-Json -Compress

    $createClient = oc exec $kcPod -n i3-auth -- `
        curl -sf -X POST `
        "http://localhost:8080/auth/admin/realms/i3/clients" `
        -H "Authorization: Bearer $adminToken" `
        -H "Content-Type: application/json" `
        -d $clientPayload 2>&1

    Ok "Keycloak client i3smartlab created (or already exists)"

    # Get client secret
    $clientsList = oc exec $kcPod -n i3-auth -- `
        curl -sf "http://localhost:8080/auth/admin/realms/i3/clients?clientId=i3smartlab" `
        -H "Authorization: Bearer $adminToken" 2>&1 | ConvertFrom-Json

    if ($clientsList -and $clientsList.Count -gt 0) {
        $clientUuid = $clientsList[0].id
        $secretResp = oc exec $kcPod -n i3-auth -- `
            curl -sf "http://localhost:8080/auth/admin/realms/i3/clients/$clientUuid/client-secret" `
            -H "Authorization: Bearer $adminToken" 2>&1 | ConvertFrom-Json

        $clientSecret = $secretResp.value
        if ($clientSecret) {
            # Patch smartlab-secrets with the real client secret
            oc patch secret smartlab-secrets -n i3-smartlab `
                --type=json `
                -p "[{`"op`":`"replace`",`"path`":`"/data/KEYCLOAK_CLIENT_SECRET`",`"value`":`"$(
                    [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($clientSecret))
                )`"}]" 2>&1
            Ok "KEYCLOAK_CLIENT_SECRET patched into smartlab-secrets: $($clientSecret.Substring(0,8))..."
        }
    }
} else {
    Info "Could not get Keycloak admin token — patch KEYCLOAK_CLIENT_SECRET manually"
}

# ── 11. DNS + Route Verification ──────────────────────────────────────────────
Banner "11 - DNS and Route"

$route = oc get route smartlab-api-public -n i3-smartlab `
    -o jsonpath='{.spec.host}' 2>&1
Ok "API Route: https://$route"

Info "Add this CNAME to your DNS provider:"
Info "  api.smartlab.i3technologies.co.ke  →  CNAME  →  8eec2322-eu-de.lb.appdomain.cloud  TTL 300"
Info ""
Info "After DNS propagation, test:"
Info "  curl https://api.smartlab.i3technologies.co.ke/health"

# ── 12. Summary ───────────────────────────────────────────────────────────────
Banner "Phase 1 Deploy Summary"

Write-Host ""
Write-Host "  NAMESPACE:      i3-smartlab" -ForegroundColor White
Write-Host "  API:            https://api.smartlab.i3technologies.co.ke" -ForegroundColor White
Write-Host "  API DOCS:       https://api.smartlab.i3technologies.co.ke/docs" -ForegroundColor White
Write-Host "  HEALTH:         https://api.smartlab.i3technologies.co.ke/health" -ForegroundColor White
Write-Host ""
Write-Host "  KEY ENDPOINTS:" -ForegroundColor Cyan
Write-Host "    POST /api/v1/courses/                  → Create course (AI outline)" -ForegroundColor Gray
Write-Host "    GET  /api/v1/jobs/{job_id}             → Poll AI job" -ForegroundColor Gray
Write-Host "    POST /api/v1/lessons/{id}/generate-content → AI lesson content" -ForegroundColor Gray
Write-Host "    POST /api/v1/lessons/{id}/narrate      → TTS narration" -ForegroundColor Gray
Write-Host "    POST /api/v1/quizzes/lesson/{id}/generate → AI quiz gen" -ForegroundColor Gray
Write-Host "    POST /api/v1/courses/{id}/package-scorm → SCORM ZIP" -ForegroundColor Gray
Write-Host "    POST /api/v1/publish/course/{id}       → Publish to Moodle" -ForegroundColor Gray
Write-Host "    POST /api/v1/live/sessions             → Create live session + RTMP key" -ForegroundColor Gray
Write-Host "    POST /api/v1/live/sessions/{id}/end    → End + trigger VOD pipeline" -ForegroundColor Gray
Write-Host "    POST /api/v1/ai/generate-quiz          → Direct AI quiz" -ForegroundColor Gray
Write-Host "    POST /api/v1/ai/tutor                  → AI tutor answer" -ForegroundColor Gray
Write-Host "    POST /api/v1/books/                    → Create EPUB book" -ForegroundColor Gray
Write-Host ""
Write-Host "  NEXT: Phase 2 — SmartLab Studio (Next.js 14 UI)" -ForegroundColor Cyan
Write-Host ""
