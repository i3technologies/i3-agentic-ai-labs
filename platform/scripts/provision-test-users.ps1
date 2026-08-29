#!/usr/bin/env pwsh
# ============================================================
# i3 Platform — Test User Provisioning Script
# PURPOSE:
#   Creates 4 test users in the Keycloak 'i3' realm via the
#   Admin REST API. Run this after Keycloak is live and the
#   realm has been imported.
#
# USERS PROVISIONED:
#   Philip Mukiti    philipm@i3technologies.co.ke   admin, instructor, student
#   Sebastian Njagi  snjagi@i3technologies.co.ke    admin, instructor, student
#   Joseph Maina     josephm@i3technologies.co.ke   admin, instructor, student
#   Dorothy Akoth    dorothy@i3technologies.co.ke   instructor
#
# PREREQUISITES:
#   - Keycloak pod is running in i3-auth namespace
#   - oc is configured against i3-platform cluster
#   - KEYCLOAK_ADMIN_PASSWORD is set (or defaults to 'admin')
#
# USAGE:
#   . .\platform\scripts\load-env.ps1
#   $env:KEYCLOAK_ADMIN_PASSWORD = "<admin-password>"
#   .\platform\scripts\provision-test-users.ps1
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$kcNs         = "i3-auth"
$oc           = "oc"
$realm        = "i3"
$kcAdminUser  = "admin"
$kcAdminPass  = if ($env:KEYCLOAK_ADMIN_PASSWORD) { $env:KEYCLOAK_ADMIN_PASSWORD } else { "admin" }
$tempPassword = "i3Test@2025!"   # Temporary — users are forced to change on first login

function Banner([string]$msg) {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Cyan
}
function Step([string]$msg) { Write-Host "[>] $msg" -ForegroundColor Yellow }
function OK([string]$msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "  [WARN] $msg" -ForegroundColor Magenta }
function Fail([string]$msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
Banner "Preflight"

Step "Finding Keycloak pod..."
$kcPod = (& $oc get pods -n $kcNs -l "app=keycloak" --no-headers 2>&1 |
    Where-Object { $_ -match "Running" } |
    Select-Object -First 1) -split '\s+' | Select-Object -First 1

if (-not $kcPod) {
    Write-Error "No running Keycloak pod found in $kcNs. Deploy Keycloak first."
}
OK "Keycloak pod: $kcPod"

if ($kcAdminPass -eq "admin") {
    Write-Warning "Using default admin password 'admin'. Set KEYCLOAK_ADMIN_PASSWORD for production."
}

# ---------------------------------------------------------------------------
Banner "Obtain Admin Token"

$tokenRaw = & $oc exec -n $kcNs $kcPod -- `
    curl -s -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" `
    -H "Content-Type: application/x-www-form-urlencoded" `
    -d "username=$kcAdminUser&password=$kcAdminPass&grant_type=password&client_id=admin-cli" 2>&1

$tokenObj = ($tokenRaw -join "") | ConvertFrom-Json
$token    = $tokenObj.access_token
if (-not $token) {
    Write-Host "Token response: $tokenRaw" -ForegroundColor Red
    Write-Error "Could not obtain admin token. Check KEYCLOAK_ADMIN_PASSWORD."
}
OK "Admin token acquired (expires in $($tokenObj.expires_in)s)"

# ---------------------------------------------------------------------------
# Helper: create or update a user, then assign realm roles
# ---------------------------------------------------------------------------
function EnsureUser {
    param(
        [string]$Username,
        [string]$Email,
        [string]$FirstName,
        [string]$LastName,
        [string[]]$Roles
    )

    Step "Processing user: $Username ($Email)"

    # Check if user already exists
    $existingRaw = & $oc exec -n $kcNs $kcPod -- `
        curl -s "http://localhost:8080/admin/realms/$realm/users?username=$Username&exact=true" `
        -H "Authorization: Bearer $token" 2>&1
    $existing = ($existingRaw -join "") | ConvertFrom-Json

    $userId = $null

    if ($existing -and $existing.Count -gt 0) {
        $userId = $existing[0].id
        Warn "User '$Username' already exists (id: $userId) — updating roles only"
    } else {
        # Create user
        $userBody = @{
            username      = $Username
            email         = $Email
            firstName     = $FirstName
            lastName      = $LastName
            enabled       = $true
            emailVerified = $true
            attributes    = @{
                organisation = @("i3 Technologies")
                userType     = @("test")
            }
            credentials   = @(
                @{
                    type      = "password"
                    value     = $tempPassword
                    temporary = $true
                }
            )
        } | ConvertTo-Json -Depth 5

        $createRaw = & $oc exec -n $kcNs $kcPod -- `
            curl -s -o /dev/null -w "%{http_code}" `
            -X POST "http://localhost:8080/admin/realms/$realm/users" `
            -H "Authorization: Bearer $token" `
            -H "Content-Type: application/json" `
            -d $userBody 2>&1

        $httpCode = ($createRaw -join "").Trim()
        if ($httpCode -eq "201") {
            OK "User '$Username' created (HTTP 201)"
        } else {
            Fail "User create returned HTTP $httpCode for '$Username'"
            return
        }

        # Fetch the new user ID
        $newUserRaw = & $oc exec -n $kcNs $kcPod -- `
            curl -s "http://localhost:8080/admin/realms/$realm/users?username=$Username&exact=true" `
            -H "Authorization: Bearer $token" 2>&1
        $newUser = ($newUserRaw -join "") | ConvertFrom-Json
        $userId  = $newUser[0].id
    }

    if (-not $userId) {
        Fail "Could not resolve user ID for '$Username'"
        return
    }

    # Fetch all available realm roles (need id + name for assignment)
    $allRolesRaw = & $oc exec -n $kcNs $kcPod -- `
        curl -s "http://localhost:8080/admin/realms/$realm/roles" `
        -H "Authorization: Bearer $token" 2>&1
    $allRoles = ($allRolesRaw -join "") | ConvertFrom-Json

    # Resolve the requested roles to role objects
    $roleObjs = @()
    foreach ($roleName in $Roles) {
        $roleObj = $allRoles | Where-Object { $_.name -eq $roleName } | Select-Object -First 1
        if ($roleObj) {
            $roleObjs += $roleObj
        } else {
            Warn "Role '$roleName' not found in realm '$realm' — skipping"
        }
    }

    if ($roleObjs.Count -eq 0) {
        Warn "No valid roles resolved for '$Username'"
        return
    }

    # Assign roles
    $rolePayload = ($roleObjs | Select-Object id, name | ConvertTo-Json -AsArray)
    $assignRaw = & $oc exec -n $kcNs $kcPod -- `
        curl -s -o /dev/null -w "%{http_code}" `
        -X POST "http://localhost:8080/admin/realms/$realm/users/$userId/role-mappings/realm" `
        -H "Authorization: Bearer $token" `
        -H "Content-Type: application/json" `
        -d $rolePayload 2>&1

    $assignCode = ($assignRaw -join "").Trim()
    if ($assignCode -eq "204") {
        OK "Roles assigned: $($Roles -join ', ')"
    } else {
        Warn "Role assignment returned HTTP $assignCode (may already be assigned)"
    }

    OK "User '$Username' ready — temporary password set, must change on first login"
}

# ---------------------------------------------------------------------------
Banner "Provisioning Test Users"

EnsureUser -Username "philipm"  -Email "philipm@i3technologies.co.ke"  `
           -FirstName "Philip"    -LastName "Mukiti"  `
           -Roles @("admin", "instructor", "student")

EnsureUser -Username "snjagi"   -Email "snjagi@i3technologies.co.ke"   `
           -FirstName "Sebastian" -LastName "Njagi"   `
           -Roles @("admin", "instructor", "student")

EnsureUser -Username "josephm"  -Email "josephm@i3technologies.co.ke"  `
           -FirstName "Joseph"    -LastName "Maina"   `
           -Roles @("admin", "instructor", "student")

EnsureUser -Username "dorothy"  -Email "dorothy@i3technologies.co.ke"  `
           -FirstName "Dorothy"   -LastName "Akoth"   `
           -Roles @("instructor")

# ---------------------------------------------------------------------------
Banner "Verification"

Step "Listing all users in realm '$realm'..."
$usersRaw = & $oc exec -n $kcNs $kcPod -- `
    curl -s "http://localhost:8080/admin/realms/$realm/users?max=50" `
    -H "Authorization: Bearer $token" 2>&1
$users = ($usersRaw -join "") | ConvertFrom-Json

$testUsers = $users | Where-Object { $_.email -like "*@i3technologies.co.ke" }
Write-Host ""
Write-Host "  i3technologies.co.ke users in realm '$realm':" -ForegroundColor White
foreach ($u in $testUsers) {
    Write-Host "    $($u.username.PadRight(12)) $($u.email.PadRight(40)) enabled=$($u.enabled)" -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
Banner "Summary"

Write-Host ""
Write-Host "  4 test users provisioned in Keycloak realm: i3" -ForegroundColor White
Write-Host ""
Write-Host "  User              Email                              Roles" -ForegroundColor White
Write-Host "  ──────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  philipm           philipm@i3technologies.co.ke      admin, instructor, student" -ForegroundColor Green
Write-Host "  snjagi            snjagi@i3technologies.co.ke       admin, instructor, student" -ForegroundColor Green
Write-Host "  josephm           josephm@i3technologies.co.ke      admin, instructor, student" -ForegroundColor Green
Write-Host "  dorothy           dorothy@i3technologies.co.ke      instructor" -ForegroundColor Green
Write-Host ""
Write-Host "  Temporary password: $tempPassword" -ForegroundColor Yellow
Write-Host "  ⚠ Each user MUST change password on first login" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Login URL: https://sso.i3technologies.co.ke/realms/i3/account" -ForegroundColor Cyan
Write-Host "  Admin console: https://sso.i3technologies.co.ke/admin/i3/console" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To verify roles for a specific user:" -ForegroundColor White
Write-Host "    oc exec -n i3-auth <keycloak-pod> -- curl -s \" -ForegroundColor Gray
Write-Host "      'http://localhost:8080/admin/realms/i3/users?username=philipm&exact=true' \" -ForegroundColor Gray
Write-Host "      -H 'Authorization: Bearer <token>'" -ForegroundColor Gray
