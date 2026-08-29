# i3 Platform - COS Recovery Script
# PURPOSE:
#   Recreates the COS instance, buckets, and HMAC keys destroyed by Terraform.
#   1. Creates/finds COS service instance  : i3-cos-production
#   2. Creates bucket                      : i3-tfstate-eu-de
#   3. Creates bucket                      : i3-platform-data
#   4. Creates bucket                      : i3-seaweedfs-dr-eu-de
#   5. Creates new HMAC service credential
#   6. Patches .env with new access/secret keys
#
# USAGE (run from workspace root):
#   . .\platform\scripts\load-env.ps1
#   .\platform\scripts\recover-cos.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RESOURCE_GROUP    = "i3-production"
$COS_INSTANCE_NAME = "i3-cos-production"
$COS_PLAN          = "lite"
$REGION            = "eu-de"
$HMAC_KEY_NAME     = "i3-cos-hmac-key"
$ENV_FILE          = Join-Path (Get-Location) ".env"

$BUCKETS = @(
    "i3-tfstate-eu-de",
    "i3-platform-data",
    "i3-seaweedfs-dr-eu-de"
)

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
Banner "Preflight checks"

Step "Verifying IBM Cloud CLI login..."
$rawAccount = ibmcloud account show --output json 2>$null
if ($LASTEXITCODE -ne 0 -or -not $rawAccount) {
    Write-Error "Not logged in. Run: ibmcloud login --apikey `$env:IBMCLOUD_API_KEY -r eu-de -g i3-production"
}
$accountInfo = $rawAccount | ConvertFrom-Json
OK "Logged in: $($accountInfo.Name)"

Step "Targeting region $REGION and resource group $RESOURCE_GROUP..."
ibmcloud target -r $REGION -g $RESOURCE_GROUP | Out-Null
OK "Targeted"

# ---------------------------------------------------------------------------
Banner "Step 1 - Find or create COS instance"

$rawInstances = ibmcloud resource service-instances --service-name cloud-object-storage --output json 2>$null
$instances     = $rawInstances | ConvertFrom-Json
$existingCOS   = $instances | Where-Object { $_.name -eq $COS_INSTANCE_NAME }

if ($existingCOS) {
    $COS_CRN = $existingCOS.crn
    OK "COS instance '$COS_INSTANCE_NAME' already exists."
    OK "CRN: $COS_CRN"
} else {
    Step "Creating COS instance '$COS_INSTANCE_NAME' (plan: $COS_PLAN)..."
    $rawCreate = ibmcloud resource service-instance-create $COS_INSTANCE_NAME `
        cloud-object-storage $COS_PLAN global `
        -g $RESOURCE_GROUP --output json 2>&1

    $strCreate = $rawCreate -join ""

    if ($LASTEXITCODE -ne 0) {
        # Creation failed - most likely a Lite plan conflict (only 1 per account).
        # Search ALL resource groups for any existing COS instance and reuse it.
        Warn "Creation failed (exit $LASTEXITCODE). Searching for any existing COS instance..."
        Write-Host $strCreate -ForegroundColor Gray

        $rawAll  = ibmcloud resource service-instances --service-name cloud-object-storage --output json 2>&1
        $allCOS  = ($rawAll -join "") | ConvertFrom-Json

        if (-not $allCOS -or $allCOS.Count -eq 0) {
            Write-Host "No COS instances found in any resource group." -ForegroundColor Red
            Write-Error "Cannot proceed. Create a COS instance manually in the IBM Cloud console and re-run."
        }

        Write-Host ""
        Write-Host "Found COS instances:" -ForegroundColor Cyan
        $allCOS | ForEach-Object { Write-Host "  name=$($_.name)  state=$($_.state)  crn=$($_.crn)" }
        Write-Host ""

        # Pick the first active instance
        $fallback = $allCOS | Where-Object { $_.state -eq "active" } | Select-Object -First 1
        if (-not $fallback) {
            $fallback = $allCOS | Select-Object -First 1
        }

        $COS_CRN           = $fallback.crn
        $COS_INSTANCE_NAME = $fallback.name
        Warn "Reusing existing instance: '$COS_INSTANCE_NAME'"
        Warn "CRN: $COS_CRN"
        Warn "Updating TF_VAR_cos_instance_name in .env to match..."

        # Patch .env cos_instance_name too so Terraform data source finds it
        if (Test-Path $ENV_FILE) {
            $tmp = Get-Content $ENV_FILE -Raw
            $tmp = $tmp -replace '(?m)^TF_VAR_cos_instance_name=.*$', "TF_VAR_cos_instance_name=$COS_INSTANCE_NAME"
            Set-Content -Path $ENV_FILE -Value $tmp -NoNewline
            [System.Environment]::SetEnvironmentVariable("TF_VAR_cos_instance_name", $COS_INSTANCE_NAME, "Process")
            OK ".env updated: TF_VAR_cos_instance_name=$COS_INSTANCE_NAME"
        }
    } else {
        $created = $strCreate | ConvertFrom-Json
        $COS_CRN = $created.crn
        OK "Created COS instance. CRN: $COS_CRN"
    }
}

$env:COS_INSTANCE_CRN = $COS_CRN

# ---------------------------------------------------------------------------
Banner "Step 2 - Configure COS plugin"

Step "Setting COS plugin CRN..."
ibmcloud cos config crn --crn $COS_CRN | Out-Null
OK "COS plugin configured"

# ---------------------------------------------------------------------------
Banner "Step 3 - Create buckets"

foreach ($bucket in $BUCKETS) {
    Step "Checking bucket: $bucket"
    ibmcloud cos bucket-head --bucket $bucket --region $REGION 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        OK "Bucket '$bucket' already exists - skipping"
    } else {
        Step "Creating bucket '$bucket'..."
        ibmcloud cos bucket-create `
            --bucket $bucket `
            --ibm-service-instance-id $COS_CRN `
            --region $REGION `
            --class smart 2>&1 | Out-Null

        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create bucket $bucket. Check CRN and region."
        }
        OK "Created: $bucket"
    }
}

# ---------------------------------------------------------------------------
Banner "Step 4 - Enable versioning on tfstate bucket"

Step "Enabling versioning on i3-tfstate-eu-de..."
ibmcloud cos bucket-versioning-put `
    --bucket i3-tfstate-eu-de `
    --versioning-configuration Status=Enabled `
    --region $REGION 2>&1 | Out-Null
OK "Versioning enabled"

# ---------------------------------------------------------------------------
Banner "Step 5 - Create HMAC service credential"

Step "Checking for old HMAC key '$HMAC_KEY_NAME'..."
$rawKeys  = ibmcloud resource service-keys --output json 2>$null
$allKeys  = $rawKeys | ConvertFrom-Json
$oldKey   = $allKeys | Where-Object { $_.name -eq $HMAC_KEY_NAME }

if ($oldKey) {
    Step "Deleting old key '$HMAC_KEY_NAME'..."
    ibmcloud resource service-key-delete $HMAC_KEY_NAME --force 2>&1 | Out-Null
    OK "Old key deleted"
}

Step "Creating new HMAC credential '$HMAC_KEY_NAME'..."
$rawKey = ibmcloud resource service-key-create $HMAC_KEY_NAME Writer `
    --instance-name $COS_INSTANCE_NAME `
    --parameters '{"HMAC":true}' `
    --output json 2>&1

$keyObj    = ($rawKey -join "") | ConvertFrom-Json
$accessKey = $keyObj.credentials.cos_hmac_keys.access_key_id
$secretKey = $keyObj.credentials.cos_hmac_keys.secret_access_key

if (-not $accessKey -or -not $secretKey) {
    Write-Host "Raw key output for debugging:" -ForegroundColor Red
    Write-Host $rawKey
    Write-Error "Could not extract HMAC keys. See output above."
}

OK "Access key: $($accessKey.Substring(0, [Math]::Min(8,$accessKey.Length)))...[redacted]"
OK "Secret key: $($secretKey.Substring(0, [Math]::Min(8,$secretKey.Length)))...[redacted]"

# ---------------------------------------------------------------------------
Banner "Step 6 - Patch .env with new HMAC keys"

if (-not (Test-Path $ENV_FILE)) {
    Write-Error ".env not found at $ENV_FILE. Run: Copy-Item .env.example .env"
}

$envContent = Get-Content $ENV_FILE -Raw

$envContent = $envContent -replace '(?m)^TF_COS_ACCESS_KEY=.*$',          "TF_COS_ACCESS_KEY=$accessKey"
$envContent = $envContent -replace '(?m)^TF_COS_SECRET_KEY=.*$',          "TF_COS_SECRET_KEY=$secretKey"
$envContent = $envContent -replace '(?m)^TF_VAR_cos_hmac_access_key=.*$', "TF_VAR_cos_hmac_access_key=$accessKey"
$envContent = $envContent -replace '(?m)^TF_VAR_cos_hmac_secret_key=.*$', "TF_VAR_cos_hmac_secret_key=$secretKey"

Set-Content -Path $ENV_FILE -Value $envContent -NoNewline
OK ".env patched"

[System.Environment]::SetEnvironmentVariable("TF_COS_ACCESS_KEY",          $accessKey, "Process")
[System.Environment]::SetEnvironmentVariable("TF_COS_SECRET_KEY",          $secretKey, "Process")
[System.Environment]::SetEnvironmentVariable("TF_VAR_cos_hmac_access_key", $accessKey, "Process")
[System.Environment]::SetEnvironmentVariable("TF_VAR_cos_hmac_secret_key", $secretKey, "Process")
OK "Keys injected into current session"

# ---------------------------------------------------------------------------
Banner "Recovery Complete"

Write-Host ""
Write-Host "COS Instance CRN: $COS_CRN"
Write-Host ""
Write-Host "Buckets ready:" -ForegroundColor White
foreach ($b in $BUCKETS) {
    Write-Host "  [OK] $b" -ForegroundColor Green
}
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Reload env (new HMAC keys are already in session, but reload to be safe):"
Write-Host "     . .\platform\scripts\load-env.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Re-init Terraform backend:"
Write-Host "     cd platform\terraform" -ForegroundColor Yellow
Write-Host "     terraform init -backend-config=""access_key=`$env:TF_COS_ACCESS_KEY"" -backend-config=""secret_key=`$env:TF_COS_SECRET_KEY"" -reconfigure" -ForegroundColor Yellow
Write-Host "     cd ..\.." -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Import orphaned IAM resources:"
Write-Host "     .\platform\scripts\terraform-import-iam.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  4. Plan + Apply:"
Write-Host "     cd platform\terraform" -ForegroundColor Yellow
Write-Host "     terraform plan -var=""ibmcloud_api_key=`$env:IBMCLOUD_API_KEY"" -out=tfplan.out" -ForegroundColor Yellow
Write-Host "     terraform apply tfplan.out" -ForegroundColor Yellow
Write-Host ""
