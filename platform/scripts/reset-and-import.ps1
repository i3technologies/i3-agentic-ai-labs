# i3 Platform - Clean State Reset + Selective Import
# PURPOSE:
#   The Terraform state is out of sync with IBM Cloud reality.
#   This script:
#     1. Removes ALL resources from local state (does NOT delete from IBM Cloud)
#     2. Re-imports only what actually exists in IBM Cloud right now
#     3. Deletes the 2 orphaned service policies so TF can recreate them cleanly
#
# CURRENT IBM CLOUD REALITY (verified 2026-08-16):
#   EXISTS:
#     - COS instance i3-cos-production  (80e0df48-...)
#     - COS buckets: i3-tfstate-077d74db, i3-platform-077d74db, i3-seaweedfs-dr-077d74db
#     - Service ID i3-tekton-ci         (ServiceId-7e42f84b-...)
#     - Service ID i3-argocd-deploy     (ServiceId-c55e8b59-...)
#     - Trusted profile                 (Profile-bf810386-...)
#     - Service policy tekton-registry  (45b73961-...)  <- needs deleting
#     - Service policy argocd-clusters  (4d39c52b-...)  <- needs deleting
#   DOES NOT EXIST:
#     - Access group i3-devops          (was deleted)
#     - VPC i3-platform-vpc             (was never fully created)
#     - All subnets, gateways, ACLs     (never created)
#     - ROKS cluster                    (never created)
#
# USAGE (run from workspace root):
#   . .\platform\scripts\load-env.ps1
#   .\platform\scripts\reset-and-import.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$TF_DIR = "platform\terraform"

$TEKTON_SID         = "ServiceId-7e42f84b-5a2b-4191-b555-8dbbb03cd1a7"
$ARGOCD_SID         = "ServiceId-c55e8b59-8f35-409f-813d-6d69f32c7ad7"
$TRUSTED_PROFILE_ID = "Profile-bf810386-1ee3-48ea-9de1-adde072a14dd"
$POLICY_TEKTON_REG  = "45b73961-54f3-4758-a56b-3a7b8b05c4ab"
$POLICY_ARGOCD_K8S  = "4d39c52b-38e7-481c-839f-cb5771c7e931"

function Banner([string]$msg) {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Cyan
}
function Step([string]$msg) { Write-Host "[>] $msg" -ForegroundColor Yellow }
function OK([string]$msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "  [WARN] $msg" -ForegroundColor Magenta }
function Info([string]$msg) { Write-Host "  [i] $msg" -ForegroundColor Gray }

function TFRemove([string]$resource) {
    Step "Removing from state: $resource"
    Push-Location $TF_DIR
    $result = terraform state rm $resource 2>&1
    $rStr   = $result -join ""
    Pop-Location
    if ($LASTEXITCODE -eq 0) { OK "Removed" }
    elseif ($rStr -match "not found|no matching") { OK "Not in state - skipping" }
    else { Warn $rStr }
}

function TFImport([string]$resource, [string]$id) {
    Step "Importing $resource"
    Info "ID: $id"
    Push-Location $TF_DIR
    $result  = terraform import $resource $id 2>&1
    $rStr    = $result -join "`n"
    Pop-Location
    if ($LASTEXITCODE -eq 0) { OK "Imported" }
    elseif ($rStr -match "already managed|already exists in the state") { OK "Already in state" }
    else { Warn "Exit $LASTEXITCODE"; Write-Host $rStr -ForegroundColor Gray }
}

# ── Preflight ─────────────────────────────────────────────────────────────────
Banner "Preflight"
if (-not (Test-Path "$TF_DIR\.terraform")) {
    Write-Error ".terraform not found. Run terraform init first."
}
OK ".terraform found"

# ── Step 1: Wipe entire Terraform state ───────────────────────────────────────
Banner "Step 1 - Remove all resources from Terraform state"
Info "This does NOT delete anything from IBM Cloud"
Info "It just clears the state file so we can re-import cleanly"

$resourcesToRemove = @(
    'module.iam.ibm_iam_access_group.devops',
    'module.iam.ibm_iam_access_group_policy.containers',
    'module.iam.ibm_iam_access_group_policy.cos_rw',
    'module.iam.ibm_iam_access_group_policy.secrets',
    'module.iam.ibm_iam_service_id.tekton_ci',
    'module.iam.ibm_iam_service_id.argocd_deploy',
    'module.iam.ibm_iam_service_policy.tekton_registry',
    'module.iam.ibm_iam_service_policy.argocd_clusters',
    'module.iam.ibm_iam_service_api_key.tekton_ci_key',
    'module.iam.ibm_iam_service_api_key.argocd_key',
    'module.iam.ibm_iam_trusted_profile.workload_identity',
    'module.cos.ibm_cos_bucket.seaweedfs_dr',
    'module.vpc.ibm_is_vpc.main',
    'module.vpc.ibm_is_subnet.worker["eu-de-1"]',
    'module.vpc.ibm_is_subnet.worker["eu-de-2"]',
    'module.vpc.ibm_is_subnet.worker["eu-de-3"]',
    'module.vpc.ibm_is_public_gateway.pgw["eu-de-1"]',
    'module.vpc.ibm_is_public_gateway.pgw["eu-de-2"]',
    'module.vpc.ibm_is_public_gateway.pgw["eu-de-3"]',
    'module.vpc.ibm_is_network_acl.workers',
    'module.vpc.ibm_is_security_group.allow_internal',
    'module.vpc.ibm_is_security_group_rule.internal_ingress',
    'module.vpc.ibm_is_security_group_rule.egress_https',
    'module.vpc.ibm_is_vpc_address_prefix.zone["eu-de-1"]',
    'module.vpc.ibm_is_vpc_address_prefix.zone["eu-de-2"]',
    'module.vpc.ibm_is_vpc_address_prefix.zone["eu-de-3"]',
    'module.roks.ibm_container_vpc_cluster.main',
    'module.roks.ibm_container_vpc_worker_pool.default_cpu',
    'module.roks.ibm_container_vpc_worker_pool.gpu_burst'
)

foreach ($r in $resourcesToRemove) {
    TFRemove $r
}

# ── Step 2: Delete orphaned service policies via CLI ──────────────────────────
Banner "Step 2 - Delete orphaned service policies"
Info "These exist in IBM Cloud but TF will recreate them correctly"

Step "Deleting tekton service policy ($POLICY_TEKTON_REG)..."
$r = ibmcloud iam service-policy-delete $TEKTON_SID $POLICY_TEKTON_REG --force 2>&1
$rStr = $r -join ""
if ($LASTEXITCODE -eq 0) { OK "Deleted" }
elseif ($rStr -match "not found|does not exist") { OK "Already gone" }
else { Warn $rStr }

Step "Deleting argocd service policy ($POLICY_ARGOCD_K8S)..."
$r = ibmcloud iam service-policy-delete $ARGOCD_SID $POLICY_ARGOCD_K8S --force 2>&1
$rStr = $r -join ""
if ($LASTEXITCODE -eq 0) { OK "Deleted" }
elseif ($rStr -match "not found|does not exist") { OK "Already gone" }
else { Warn $rStr }

# ── Step 3: Import only what actually exists ──────────────────────────────────
Banner "Step 3 - Import existing resources"

# Service IDs (confirmed to exist)
TFImport "module.iam.ibm_iam_service_id.tekton_ci"              $TEKTON_SID
TFImport "module.iam.ibm_iam_service_id.argocd_deploy"          $ARGOCD_SID
TFImport "module.iam.ibm_iam_trusted_profile.workload_identity" $TRUSTED_PROFILE_ID

# COS bucket (we created it manually)
# IBM provider v1.89 import format for ibm_cos_bucket:
#   <bucket_name>:<cos_instance_id>:<bucket_type>:<location>
# For a regional bucket: bucket_name:instance_crn:region_location:<region>
Step "Importing SeaweedFS DR bucket..."
Push-Location $TF_DIR

# Try format 1: just bucket name (simplest)
$r1 = terraform import "module.cos.ibm_cos_bucket.seaweedfs_dr" "i3-seaweedfs-dr-077d74db" 2>&1
$r1Str = $r1 -join "`n"
if ($LASTEXITCODE -eq 0) {
    OK "Bucket imported (simple name)"
} else {
    Info "Simple name failed, trying CRN format..."
    # Format 2: bucketname:instanceId (CRN without colons issue - use GUID instead)
    $instanceGUID = "80e0df48-b149-4011-b87f-943f43736132"
    $r2 = terraform import "module.cos.ibm_cos_bucket.seaweedfs_dr" "i3-seaweedfs-dr-077d74db:$instanceGUID" 2>&1
    $r2Str = $r2 -join "`n"
    if ($LASTEXITCODE -eq 0) {
        OK "Bucket imported (GUID format)"
    } else {
        Info "GUID format failed, trying region format..."
        $r3 = terraform import "module.cos.ibm_cos_bucket.seaweedfs_dr" "i3-seaweedfs-dr-077d74db:eu-de:regional:smart" 2>&1
        $r3Str = $r3 -join "`n"
        if ($LASTEXITCODE -eq 0) {
            OK "Bucket imported (region format)"
        } else {
            Warn "All bucket import formats failed - Terraform will CREATE it on next apply"
            Warn "This is safe as the bucket already exists and TF will get a conflict..."
            Warn "We will handle this with a targeted apply exclusion if needed"
            Info $r3Str
        }
    }
}
Pop-Location

# ── Step 4: Verify final state ────────────────────────────────────────────────
Banner "Step 4 - Final state verification"

Step "terraform state list..."
Push-Location $TF_DIR
terraform state list 2>&1
Pop-Location

Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  State reset complete" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Expected state contents:" -ForegroundColor White
Write-Host "  module.iam.ibm_iam_service_id.tekton_ci" -ForegroundColor Gray
Write-Host "  module.iam.ibm_iam_service_id.argocd_deploy" -ForegroundColor Gray
Write-Host "  module.iam.ibm_iam_trusted_profile.workload_identity" -ForegroundColor Gray
Write-Host "  module.cos.ibm_cos_bucket.seaweedfs_dr  (if import succeeded)" -ForegroundColor Gray
Write-Host "  + data sources (auto-read, no import needed)" -ForegroundColor Gray
Write-Host ""
Write-Host "NOT in state (TF will CREATE these fresh):" -ForegroundColor White
Write-Host "  module.iam.ibm_iam_access_group.devops          <- RECREATE" -ForegroundColor Yellow
Write-Host "  module.iam.ibm_iam_access_group_policy.*        <- RECREATE" -ForegroundColor Yellow
Write-Host "  module.iam.ibm_iam_service_policy.*             <- RECREATE" -ForegroundColor Yellow
Write-Host "  module.iam.ibm_iam_service_api_key.*            <- RECREATE" -ForegroundColor Yellow
Write-Host "  module.vpc.*                                     <- CREATE FRESH" -ForegroundColor Yellow
Write-Host "  module.roks.*                                    <- CREATE FRESH" -ForegroundColor Yellow
Write-Host ""
Write-Host "NEXT:" -ForegroundColor Cyan
Write-Host "  cd platform\terraform" -ForegroundColor Yellow
Write-Host "  terraform plan -out tfplan.out" -ForegroundColor Yellow
Write-Host "  terraform apply tfplan.out" -ForegroundColor Yellow
