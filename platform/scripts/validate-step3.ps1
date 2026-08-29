# i3 Platform - Phase 1 Step 3 Validation
# Usage: .\platform\scripts\validate-step3.ps1

$ibmcloud = "C:\Program Files\IBM\Cloud\bin\ibmcloud.exe"
$jq       = "C:\tools\jq\jq.exe"

$PASS = "  [PASS]"
$FAIL = "  [FAIL]"
$WARN = "  [WARN]"
$checks = @()

Write-Host ""
Write-Host "=============================================="
Write-Host " Phase 1 Step 3 - IBM Cloud CLI Login Checks"
Write-Host "=============================================="
Write-Host ""

# Check 1: API key length
Write-Host "1. Checking IBMCLOUD_API_KEY is set..."
$keyLen = if ($env:IBMCLOUD_API_KEY) { $env:IBMCLOUD_API_KEY.Length } else { 0 }
if ($keyLen -ge 40) {
    Write-Host "$PASS Key loaded ($keyLen chars): $($env:IBMCLOUD_API_KEY.Substring(0,6))...[redacted]"
    $checks += $true
} else {
    Write-Host "$FAIL Key missing or wrong length ($keyLen chars). Run: . .\platform\scripts\load-env.ps1"
    $checks += $false
}

# Check 2: CLI binary
Write-Host "2. Checking IBM Cloud CLI binary..."
$ver = & $ibmcloud version 2>&1 | Select-Object -First 1
if ($LASTEXITCODE -eq 0) {
    Write-Host "$PASS CLI reachable: $ver"
    $checks += $true
} else {
    Write-Host "$FAIL ibmcloud not found."
    $checks += $false
}

# Check 3: Login session
Write-Host "3. Checking active login session..."
$acct = & $ibmcloud account show 2>&1 | Select-String "Account Name:"
if ($acct) {
    Write-Host "$PASS Logged in. $acct"
    $checks += $true
} else {
    Write-Host "$FAIL Not logged in."
    $checks += $false
}

# Check 4: Region
Write-Host "4. Checking targeted region..."
$target = & $ibmcloud target 2>&1
$regionLine = $target | Select-String "Region:"
if ($regionLine -match "eu-de") {
    Write-Host "$PASS Region: eu-de"
    $checks += $true
} else {
    Write-Host "$FAIL Wrong region. Run: ibmcloud target -r eu-de"
    Write-Host "       Current: $regionLine"
    $checks += $false
}

# Check 5: Resource group
Write-Host "5. Checking resource group..."
$rgLine = $target | Select-String "Resource group:"
if ($rgLine -match "i3-production") {
    Write-Host "$PASS Resource group: i3-production"
    $checks += $true
} else {
    Write-Host "$FAIL Wrong resource group. Run: ibmcloud target -g i3-production"
    Write-Host "       Current: $rgLine"
    $checks += $false
}

# Check 6+7: Plugins - use plain text output, no jq needed
Write-Host "6. Checking container-service plugin..."
$pluginList = & $ibmcloud plugin list 2>&1
if ($pluginList | Select-String "container-service") {
    $csLine = ($pluginList | Select-String "container-service").ToString().Trim()
    Write-Host "$PASS $csLine"
    $checks += $true
} else {
    Write-Host "$FAIL container-service missing. Run: ibmcloud plugin install container-service"
    $checks += $false
}

Write-Host "7. Checking container-registry plugin..."
if ($pluginList | Select-String "container-registry") {
    $crLine = ($pluginList | Select-String "container-registry").ToString().Trim()
    Write-Host "$PASS $crLine"
    $checks += $true
} else {
    Write-Host "$FAIL container-registry missing. Run: ibmcloud plugin install container-registry"
    $checks += $false
}

# Check 8: ROKS API
Write-Host "8. Checking IBM Kubernetes Service API..."
$clusters = & $ibmcloud ks clusters 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "$PASS Kubernetes Service API reachable."
    $checks += $true
} else {
    Write-Host "$WARN Could not list clusters (OK if none exist yet)."
    $checks += $true
}

# Check 9: Resource Controller
Write-Host "9. Checking Resource Controller (for COS)..."
$svc = & $ibmcloud resource service-instances 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "$PASS Resource Controller reachable."
    $checks += $true
} else {
    Write-Host "$FAIL Resource Controller unreachable."
    $checks += $false
}

# Summary
$passed = ($checks | Where-Object { $_ -eq $true }).Count
$failed = ($checks | Where-Object { $_ -eq $false }).Count
$total  = $checks.Count

Write-Host ""
Write-Host "----------------------------------------------"
Write-Host " Result: $passed / $total checks passed"
if ($failed -eq 0) {
    Write-Host " STATUS: READY - proceed to Step 4"
} else {
    Write-Host " STATUS: Fix the $failed FAIL item(s) above then re-run."
}
Write-Host "----------------------------------------------"
