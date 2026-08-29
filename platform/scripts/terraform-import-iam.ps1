# i3 Platform - Terraform IAM Import Script
# PURPOSE:
#   Imports the 4 IAM resources that were created during the partial
#   terraform apply (before COS was destroyed) into fresh Terraform state.
#
#   Resources imported:
#     module.iam.ibm_iam_access_group.devops         -> AccessGroupId-40808bbc-...
#     module.iam.ibm_iam_service_id.tekton_ci        -> ServiceId-7e42f84b-...
#     module.iam.ibm_iam_service_id.argocd_deploy    -> ServiceId-c55e8b59-...
#     module.iam.ibm_iam_trusted_profile.workload_identity -> Profile-bf810386-...
#
#   Access group policies and service API keys are NOT importable via the IBM
#   provider - they will show as "+ create" in the plan. That is expected.
#
# USAGE (run from workspace root, AFTER terraform init -reconfigure):
#   .\platform\scripts\terraform-import-iam.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TF_DIR = "platform\terraform"

$DEVOPS_GROUP_ID    = "AccessGroupId-40808bbc-f4f3-483a-81f3-f02f186e61bb"
$TEKTON_SID         = "ServiceId-7e42f84b-5a2b-4191-b555-8dbbb03cd1a7"
$ARGOCD_SID         = "ServiceId-c55e8b59-8f35-409f-813d-6d69f32c7ad7"
$TRUSTED_PROFILE_ID = "Profile-bf810386-1ee3-48ea-9de1-adde072a14dd"

function Banner([string]$msg) {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Cyan
}

function Step([string]$msg) {
    Write-Host "[>] $msg" -ForegroundColor Yellow
}

function OK([string]$msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Warn([string]$msg) {
    Write-Host "  [WARN] $msg" -ForegroundColor Magenta
}

# ---------------------------------------------------------------------------
Banner "Preflight"

if (-not (Test-Path "$TF_DIR\.terraform")) {
    Write-Error ".terraform directory not found in $TF_DIR. Run terraform init first."
}
OK ".terraform directory found"

if (-not $env:IBMCLOUD_API_KEY) {
    Write-Error "IBMCLOUD_API_KEY not set. Run: . .\platform\scripts\load-env.ps1"
}
OK "IBMCLOUD_API_KEY is set"

# ---------------------------------------------------------------------------
function TFImport([string]$resource, [string]$id) {
    Step "Importing $resource"
    Write-Host "        ID: $id" -ForegroundColor Gray

    Push-Location $TF_DIR
    try {
        $result = terraform import `
            -var="ibmcloud_api_key=$env:IBMCLOUD_API_KEY" `
            $resource $id 2>&1

        $resultStr = $result -join "`n"

        if ($LASTEXITCODE -eq 0) {
            OK "Imported successfully"
        } elseif ($resultStr -match "Resource already managed|already exists in the state") {
            OK "Already in state - skipping"
        } else {
            Warn "Import exited $LASTEXITCODE - output:"
            Write-Host $resultStr -ForegroundColor Gray
            # Non-fatal: the apply will handle reconciliation
        }
    } finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
Banner "Importing IAM Resources"

TFImport "module.iam.ibm_iam_access_group.devops"                 $DEVOPS_GROUP_ID
TFImport "module.iam.ibm_iam_service_id.tekton_ci"                $TEKTON_SID
TFImport "module.iam.ibm_iam_service_id.argocd_deploy"            $ARGOCD_SID
TFImport "module.iam.ibm_iam_trusted_profile.workload_identity"   $TRUSTED_PROFILE_ID

# ---------------------------------------------------------------------------
Banner "Verifying Terraform State"

Step "Running terraform state list..."
Push-Location $TF_DIR
$stateList = terraform state list 2>&1
$stateExit = $LASTEXITCODE
Pop-Location

if ($stateExit -eq 0) {
    Write-Host $stateList
    OK "State is accessible"
} else {
    Warn "terraform state list failed - backend may still be unreachable"
    Write-Host $stateList -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
Banner "Import Complete"

Write-Host ""
Write-Host "Imported resources:" -ForegroundColor White
Write-Host "  [OK] module.iam.ibm_iam_access_group.devops          -> $DEVOPS_GROUP_ID" -ForegroundColor Green
Write-Host "  [OK] module.iam.ibm_iam_service_id.tekton_ci         -> $TEKTON_SID" -ForegroundColor Green
Write-Host "  [OK] module.iam.ibm_iam_service_id.argocd_deploy     -> $ARGOCD_SID" -ForegroundColor Green
Write-Host "  [OK] module.iam.ibm_iam_trusted_profile.workload_identity -> $TRUSTED_PROFILE_ID" -ForegroundColor Green
Write-Host ""
Write-Host "NOTE: Access group policies and API keys are NOT importable." -ForegroundColor Magenta
Write-Host "They will show as '+ create' in the plan. This is expected and safe." -ForegroundColor Magenta
Write-Host ""
Write-Host "NEXT: Run terraform plan" -ForegroundColor Cyan
Write-Host "  cd platform\terraform" -ForegroundColor Yellow
Write-Host "  terraform plan -var=""ibmcloud_api_key=`$env:IBMCLOUD_API_KEY"" -out=tfplan.out" -ForegroundColor Yellow
Write-Host ""
