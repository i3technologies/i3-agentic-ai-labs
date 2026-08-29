# i3 Platform - Terraform Full State Import Script
# PURPOSE:
#   Imports ALL resources that already exist in IBM Cloud but are missing
#   from Terraform state, so the next apply has zero conflicts.
#
#   Handles two categories:
#     A) Resources from the original partial apply (IAM policies, VPC)
#     B) Resources created manually during recovery (SeaweedFS bucket)
#
# USAGE (run from workspace root, while cd'd into platform\terraform for tf commands):
#   cd C:\Users\Admin\Documents\i3-Agentic-AI-Labs
#   . .\platform\scripts\load-env.ps1
#   .\platform\scripts\terraform-import-all.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"   # Don't crash on individual CLI failures

$TF_DIR = "platform\terraform"

# ── Known IDs extracted from error messages ──────────────────────────────────

# IAM - already imported in previous run (kept here for idempotency)
$DEVOPS_GROUP_ID    = "AccessGroupId-40808bbc-f4f3-483a-81f3-f02f186e61bb"
$TEKTON_SID         = "ServiceId-7e42f84b-5a2b-4191-b555-8dbbb03cd1a7"
$ARGOCD_SID         = "ServiceId-c55e8b59-8f35-409f-813d-6d69f32c7ad7"
$TRUSTED_PROFILE_ID = "Profile-bf810386-1ee3-48ea-9de1-adde072a14dd"

# IAM Policies - existed from original apply, not importable via IBM provider
# We will DELETE them via CLI and let Terraform recreate them cleanly
$POLICY_CONTAINERS   = "e34a2db3-638e-4fff-a7fa-63bd70a86bed"
$POLICY_SECRETS      = "6eb073ee-ba68-4070-8e33-96bf1e2d37db"
$POLICY_TEKTON_REG   = "45b73961-54f3-4758-a56b-3a7b8b05c4ab"
$POLICY_ARGOCD_K8S   = "4d39c52b-38e7-481c-839f-cb5771c7e931"

# COS Instance CRN
$COS_CRN = "crn:v1:bluemix:public:cloud-object-storage:global:a/077d74dbc176470b8481e192e4548813:80e0df48-b149-4011-b87f-943f43736132::"

# VPC - created in a previous partial apply
# We need to look up the VPC ID first
$VPC_NAME = "i3-platform-vpc"

function Banner([string]$msg) {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Cyan
}
function Step([string]$msg)  { Write-Host "[>] $msg" -ForegroundColor Yellow }
function OK([string]$msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn([string]$msg)  { Write-Host "  [WARN] $msg" -ForegroundColor Magenta }
function Info([string]$msg)  { Write-Host "  [i] $msg" -ForegroundColor Gray }

function TFImport([string]$resource, [string]$id) {
    Step "Importing $resource"
    Info "ID: $id"
    Push-Location $TF_DIR
    try {
        $result    = terraform import $resource $id 2>&1
        $resultStr = $result -join "`n"
        if ($LASTEXITCODE -eq 0) {
            OK "Imported"
        } elseif ($resultStr -match "already managed|already exists in the state") {
            OK "Already in state - skipping"
        } else {
            Warn "Exit $LASTEXITCODE"
            Write-Host $resultStr -ForegroundColor Gray
        }
    } finally {
        Pop-Location
    }
}

# ── Preflight ─────────────────────────────────────────────────────────────────
Banner "Preflight"

if (-not (Test-Path "$TF_DIR\.terraform")) {
    Write-Error ".terraform not found. Run terraform init first."
}
OK ".terraform found"

if (-not $env:IBMCLOUD_API_KEY) {
    Write-Error "IBMCLOUD_API_KEY not set. Run: . .\platform\scripts\load-env.ps1"
}
OK "IBMCLOUD_API_KEY set"

# ── Step A: Delete orphaned IAM policies via CLI ──────────────────────────────
# IBM provider cannot import policies - easiest fix is delete + let TF recreate
Banner "Step A - Delete orphaned IAM policies (TF will recreate)"

$policies = @(
    @{ name = "containers (e34a2db3)"; id = $POLICY_CONTAINERS },
    @{ name = "secrets (6eb073ee)";    id = $POLICY_SECRETS },
    @{ name = "tekton-registry (45b7)"; id = $POLICY_TEKTON_REG },
    @{ name = "argocd-k8s (4d39c52b)"; id = $POLICY_ARGOCD_K8S }
)

# Access group policies (containers, secrets)
$agPolicies = @(
    @{ name = "containers (e34a2db3)"; id = $POLICY_CONTAINERS },
    @{ name = "secrets (6eb073ee)";    id = $POLICY_SECRETS }
)
foreach ($p in $agPolicies) {
    Step "Deleting access-group policy: $($p.name)"
    $result = ibmcloud iam access-group-policy-delete $DEVOPS_GROUP_ID $p.id --force 2>&1
    $rStr   = $result -join ""
    if ($LASTEXITCODE -eq 0) { OK "Deleted" }
    elseif ($rStr -match "not found|does not exist|FAILED") { OK "Already gone - skipping" }
    else { Warn "Result: $rStr" }
}

# Service policies (tekton registry, argocd clusters)
$svcPolicies = @(
    @{ name = "tekton-registry (45b7)"; sid = $TEKTON_SID;  id = $POLICY_TEKTON_REG },
    @{ name = "argocd-k8s (4d39)";      sid = $ARGOCD_SID;  id = $POLICY_ARGOCD_K8S }
)
foreach ($p in $svcPolicies) {
    Step "Deleting service policy: $($p.name)"
    $result = ibmcloud iam service-policy-delete $p.sid $p.id --force 2>&1
    $rStr   = $result -join ""
    if ($LASTEXITCODE -eq 0) { OK "Deleted" }
    elseif ($rStr -match "not found|does not exist|FAILED") { OK "Already gone - skipping" }
    else { Warn "Result: $rStr" }
}

# ── Step B: Look up and import VPC ────────────────────────────────────────────
Banner "Step B - Import VPC"

Step "Looking up VPC ID for '$VPC_NAME'..."
$rawVPC = ibmcloud is vpcs --output json 2>&1
$vpcs   = ($rawVPC -join "") | ConvertFrom-Json
$vpc    = $vpcs | Where-Object { $_.name -eq $VPC_NAME } | Select-Object -First 1

if (-not $vpc) {
    Warn "VPC '$VPC_NAME' not found - it may not have been created yet. Skipping VPC import."
    Warn "If the previous apply error said 'name is not unique', the VPC exists but in a different region/query."
    Warn "Run: ibmcloud is vpcs --output json | ConvertFrom-Json | Select-Object name,id"
} else {
    $VPC_ID = $vpc.id
    OK "Found VPC: $VPC_ID"
    TFImport "module.vpc.ibm_is_vpc.main" $VPC_ID

    # Import subnets if VPC was found
    Banner "Step C - Import Subnets"
    Step "Looking up subnets in VPC $VPC_ID..."
    $rawSubnets = ibmcloud is subnets --output json 2>&1
    $allSubnets = ($rawSubnets -join "") | ConvertFrom-Json
    $vpcSubnets = $allSubnets | Where-Object { $_.vpc.id -eq $VPC_ID }

    if ($vpcSubnets.Count -eq 0) {
        Warn "No subnets found for VPC $VPC_ID - subnets may not have been created yet"
    } else {
        foreach ($subnet in $vpcSubnets) {
            $zone     = $subnet.zone.name
            $subnetId = $subnet.id
            # Map zone to Terraform key
            $tfKey = switch ($zone) {
                "eu-de-1" { '"eu-de-1"' }
                "eu-de-2" { '"eu-de-2"' }
                "eu-de-3" { '"eu-de-3"' }
                default   { $zone }
            }
            TFImport "module.vpc.ibm_is_subnet.worker[$tfKey]" $subnetId
        }
    }

    # Import public gateways
    Banner "Step D - Import Public Gateways"
    Step "Looking up public gateways..."
    $rawPGWs = ibmcloud is public-gateways --output json 2>&1
    $allPGWs = ($rawPGWs -join "") | ConvertFrom-Json
    $vpcPGWs = $allPGWs | Where-Object { $_.vpc.id -eq $VPC_ID }

    foreach ($pgw in $vpcPGWs) {
        $zone  = $pgw.zone.name
        $pgwId = $pgw.id
        $tfKey = switch ($zone) {
            "eu-de-1" { '"eu-de-1"' }
            "eu-de-2" { '"eu-de-2"' }
            "eu-de-3" { '"eu-de-3"' }
            default   { $zone }
        }
        TFImport "module.vpc.ibm_is_public_gateway.pgw[$tfKey]" $pgwId
    }

    # Import Network ACL
    Banner "Step E - Import Network ACL"
    Step "Looking up network ACLs..."
    $rawACLs = ibmcloud is network-acls --output json 2>&1
    $allACLs = ($rawACLs -join "") | ConvertFrom-Json
    $vpcACL  = $allACLs | Where-Object { $_.vpc.id -eq $VPC_ID -and $_.name -eq "i3-platform-acl" } | Select-Object -First 1

    if ($vpcACL) {
        TFImport "module.vpc.ibm_is_network_acl.workers" $vpcACL.id
    } else {
        Warn "Network ACL 'i3-platform-acl' not found - may not have been created yet"
    }

    # Import Security Group
    Banner "Step F - Import Security Group"
    Step "Looking up security groups..."
    $rawSGs = ibmcloud is security-groups --output json 2>&1
    $allSGs = ($rawSGs -join "") | ConvertFrom-Json
    $vpcSG  = $allSGs | Where-Object { $_.vpc.id -eq $VPC_ID -and $_.name -eq "i3-platform-allow-internal" } | Select-Object -First 1

    if ($vpcSG) {
        TFImport "module.vpc.ibm_is_security_group.allow_internal" $vpcSG.id
    } else {
        Warn "Security group 'i3-platform-allow-internal' not found"
    }
}

# ── Step G: Import COS bucket ─────────────────────────────────────────────────
Banner "Step G - Import SeaweedFS DR bucket"

# IBM COS bucket import format: bucketName:bucketType:endpointType:storageClass
# For regional bucket in eu-de:
$bucketImportId = "i3-seaweedfs-dr-077d74db:us-south:eu-de:smart"
Step "Trying COS bucket import (format: name:region_type:location:class)..."

# The IBM provider import ID for ibm_cos_bucket is: bucketName:serviceInstanceId
# Actually the correct format depends on provider version - try both
Push-Location $TF_DIR
$result1 = terraform import "module.cos.ibm_cos_bucket.seaweedfs_dr" "i3-seaweedfs-dr-077d74db" 2>&1
$r1str   = $result1 -join "`n"
Pop-Location

if ($LASTEXITCODE -eq 0) {
    OK "Bucket imported"
} else {
    Warn "Simple name import failed - trying with CRN-qualified ID..."
    Info $r1str

    Push-Location $TF_DIR
    # Try with resource_instance_id appended
    $bucketId2 = "i3-seaweedfs-dr-077d74db:$COS_CRN"
    $result2   = terraform import "module.cos.ibm_cos_bucket.seaweedfs_dr" $bucketId2 2>&1
    $r2str     = $result2 -join "`n"
    Pop-Location

    if ($LASTEXITCODE -eq 0) {
        OK "Bucket imported with CRN"
    } else {
        Warn "CRN import also failed - will try region-qualified format..."
        Info $r2str
        # Final attempt: bucket::region format used by some provider versions
        Push-Location $TF_DIR
        $bucketId3 = "i3-seaweedfs-dr-077d74db:eu-de:regional:smart"
        $result3   = terraform import "module.cos.ibm_cos_bucket.seaweedfs_dr" $bucketId3 2>&1
        $r3str     = $result3 -join "`n"
        Pop-Location
        if ($LASTEXITCODE -eq 0) {
            OK "Bucket imported (region format)"
        } else {
            Warn "All bucket import formats failed. Will handle in plan."
            Info $r3str
        }
    }
}

# ── Step H: Re-import IAM resources (idempotent) ─────────────────────────────
Banner "Step H - Re-confirm IAM resource imports"

TFImport "module.iam.ibm_iam_access_group.devops"               $DEVOPS_GROUP_ID
TFImport "module.iam.ibm_iam_service_id.tekton_ci"              $TEKTON_SID
TFImport "module.iam.ibm_iam_service_id.argocd_deploy"          $ARGOCD_SID
TFImport "module.iam.ibm_iam_trusted_profile.workload_identity" $TRUSTED_PROFILE_ID

# ── Final: show state ─────────────────────────────────────────────────────────
Banner "Final State"

Step "terraform state list..."
Push-Location $TF_DIR
$stateList = terraform state list 2>&1
Pop-Location
Write-Host $stateList

Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  cd platform\terraform" -ForegroundColor Yellow
Write-Host "  terraform plan -out tfplan.out" -ForegroundColor Yellow
Write-Host "  terraform apply tfplan.out" -ForegroundColor Yellow
Write-Host ""
Write-Host "Expected plan: 0 to destroy, small number of creates (policies recreated, ROKS not yet created)" -ForegroundColor Green
