# i3 Platform — Phase 1 Step 2 Validation
# Run AFTER completing IBM Cloud console tasks and CLI login (Step 3)
# Usage: . .\platform\scripts\setup-path.ps1; .\platform\scripts\validate-step2.ps1

$ibmcloud = "C:\Program Files\IBM\Cloud\bin\ibmcloud.exe"
$jq       = "C:\tools\jq\jq.exe"
$PASS     = "[PASS]"
$FAIL     = "[FAIL]"
$WARN     = "[WARN]"
$checks   = @()

Write-Host ""
Write-Host "=============================================="
Write-Host " Phase 1 Step 2 — IBM Cloud Account Checks"
Write-Host "=============================================="
Write-Host ""

# ── Check 1: CLI login ────────────────────────────────────────
Write-Host "1. Checking IBM Cloud CLI login..."
$accountInfo = & $ibmcloud account show --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    $account = $accountInfo | & $jq -r '.name // "Unknown"' 2>$null
    Write-Host "   $PASS Logged in. Account: $account"
    $checks += $true
} else {
    Write-Host "   $FAIL Not logged in. Run: ibmcloud login --apikey YOUR_API_KEY -r eu-de"
    $checks += $false
}

# ── Check 2: Resource group ───────────────────────────────────
Write-Host "2. Checking resource group 'i3-production'..."
$rgs = & $ibmcloud resource groups --output json 2>&1
$rgExists = $rgs | & $jq -r '.[] | select(.name=="i3-production") | .state' 2>$null
if ($rgExists -eq "ACTIVE") {
    $rgId = $rgs | & $jq -r '.[] | select(.name=="i3-production") | .id' 2>$null
    Write-Host "   $PASS Resource group exists. ID: $rgId"
    $checks += $true
} else {
    Write-Host "   $FAIL Resource group 'i3-production' not found or not ACTIVE."
    Write-Host "        Create it: ibmcloud resource group-create i3-production"
    $checks += $false
}

# ── Check 3: Account type (must not be Lite) ──────────────────
Write-Host "3. Checking account type (must be Pay-As-You-Go or Subscription)..."
$acctType = & $ibmcloud account show --output json 2>&1 | & $jq -r '.type // "unknown"' 2>$null
if ($acctType -eq "SUBSCRIPTION" -or $acctType -eq "PAYG" -or $acctType -like "*PAY*" -or $acctType -like "*TRIAL*") {
    Write-Host "   $PASS Account type: $acctType"
    $checks += $true
} elseif ($acctType -eq "STANDARD" -or $acctType -like "*LITE*") {
    Write-Host "   $FAIL Account type is $acctType. ROKS requires Pay-As-You-Go or Subscription."
    $checks += $false
} else {
    Write-Host "   $WARN Could not determine account type (got: $acctType). Proceeding cautiously."
    $checks += $true
}

# ── Check 4: Required IAM permissions ────────────────────────
Write-Host "4. Checking if current user has Administrator role..."
$iam = & $ibmcloud iam user-policies 2>&1
if ($iam -match "Administrator" -or $iam -match "account-admin") {
    Write-Host "   $PASS Administrator policy found."
    $checks += $true
} else {
    Write-Host "   $WARN Cannot verify admin role automatically (may require account owner)."
    Write-Host "        Ensure your user has 'Administrator' on 'All Identity and Access' resources."
    $checks += $true  # non-blocking
}

# ── Check 5: API key exists in current session ────────────────
Write-Host "5. Checking IBMCLOUD_API_KEY environment variable..."
if ($env:IBMCLOUD_API_KEY -and $env:IBMCLOUD_API_KEY -ne "REPLACE_WITH_YOUR_API_KEY") {
    Write-Host "   $PASS IBMCLOUD_API_KEY is set (value hidden)."
    $checks += $true
} else {
    Write-Host "   $WARN IBMCLOUD_API_KEY not set as env var yet."
    Write-Host "        This is OK at this stage — you will set it in Step 5."
    $checks += $true  # non-blocking at step 2
}

# ── Summary ───────────────────────────────────────────────────
$passed = ($checks | Where-Object { $_ -eq $true }).Count
$total  = $checks.Count
Write-Host ""
Write-Host "----------------------------------------------"
Write-Host " Result: $passed / $total checks passed"
if ($passed -eq $total) {
    Write-Host " STATUS: READY to proceed to Step 3"
} else {
    Write-Host " STATUS: Fix the FAIL items above before continuing."
}
Write-Host "----------------------------------------------"
Write-Host ""
