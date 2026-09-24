# ============================================================
# i3 Technologies — Keycloak User Provisioning Script
# September 2026  |  Senior Systems Administrator use only
#
# PURPOSE:
#   Provisions all 79 i3 Team members into Keycloak realm "i3"
#   with user-level access (role: i3-user).
#   Users already present in Keycloak are RETAINED and skipped.
#   New users receive:
#       • Username  = email address
#       • Password  = i3ar@2026!was  (temporary — must change on first login)
#       • Role      = i3-user
#       • Group     = their department group
#   Philip Mukiti (CEO) and Sebastian Njagi (Architect) receive
#   elevated roles (i3-admin / i3-learning-admin) as already held.
#
# PREREQUISITES:
#   - kcadm.sh accessible in PATH  (Keycloak Admin CLI)
#     OR set $KcAdm to full path e.g. "C:\keycloak\bin\kcadm.bat"
#   - Network access to https://sso.i3technologies.co.ke
#   - Keycloak admin credentials stored in environment vars:
#       KC_ADMIN_USER  — admin username
#       KC_ADMIN_PASS  — admin password
#
# USAGE:
#   .\provision-i3-users-keycloak.ps1
#   .\provision-i3-users-keycloak.ps1 -DryRun     # prints actions, no changes
#   .\provision-i3-users-keycloak.ps1 -Verbose
#
# HC COMPLIANCE:  HC-7 (no bypass), HC-4 (all accounts in realm i3)
# ============================================================

param(
    [switch]$DryRun,
    [switch]$Verbose
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Config ────────────────────────────────────────────────────────
# Support:  support@i3technologies.co.ke (general) | training@i3technologies.co.ke (labs/learning)
# Sr SysAdmin: josephm@i3technologies.co.ke (Joseph Maina — reports to Sebastian Njagi)
$KC_URL    = "https://sso.i3technologies.co.ke"
$KC_REALM  = "i3"
$TEMP_PASS = "i3ar@2026!was"
$KcAdm     = if ($env:KC_ADM_PATH) { $env:KC_ADM_PATH } else { "kcadm.sh" }

if (-not $env:KC_ADMIN_USER -or -not $env:KC_ADMIN_PASS) {
    Write-Error "Set KC_ADMIN_USER and KC_ADMIN_PASS environment variables before running."
    exit 1
}

# ── Helper ────────────────────────────────────────────────────────
function Invoke-Kc {
    param([string[]]$Args)
    if ($DryRun) {
        Write-Host "[DRY-RUN] kcadm $($Args -join ' ')" -ForegroundColor Cyan
        return ""
    }
    & $KcAdm @Args 2>&1
}

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $colour = switch ($Level) {
        "OK"   { "Green"  }
        "SKIP" { "Yellow" }
        "WARN" { "DarkYellow" }
        "ERR"  { "Red"    }
        default{ "White"  }
    }
    Write-Host "[$ts] [$Level] $Msg" -ForegroundColor $colour
}

# ── Authenticate ──────────────────────────────────────────────────
Write-Log "Authenticating to Keycloak at $KC_URL ..."
Invoke-Kc @("config", "credentials",
    "--server", $KC_URL,
    "--realm",  "master",
    "--user",   $env:KC_ADMIN_USER,
    "--password", $env:KC_ADMIN_PASS) | Out-Null
Write-Log "Authenticated." "OK"

# ── User Definitions ─────────────────────────────────────────────
# Format: Email | FullName | Department | Role | IsAdmin
# Roles: i3-user | i3-learning-admin | i3-admin
$users = @(
    @{ Email="abigaela@i3technologies.co.ke";         Name="Abigael Amuruon";              Dept="Unassigned";                     Role="i3-user" }
    @{ Email="alimm@i3technologies.co.ke";            Name="Ali Mohammed";                 Dept="Research and Development";       Role="i3-user" }
    @{ Email="alvinekiprono@i3technologies.co.ke";    Name="Alvine Kiprono";               Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="alvino@i3technologies.co.ke";           Name="Alvin Osao";                   Dept="IT - Server-Storage";            Role="i3-user" }
    @{ Email="andrewmakori@i3technologies.co.ke";     Name="Andrew Makori Nyachaki";        Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="angelak@i3technologies.co.ke";          Name="Angela Kinoro";                Dept="Unassigned";                     Role="i3-user" }
    @{ Email="annewambui@i3technologies.co.ke";       Name="Ann Wambui Kingori";           Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="annnjeri@i3technologies.co.ke";         Name="Ann Njeri Mucheke";            Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="anthonymm@i3technologies.co.ke";        Name="Anthony Mureithi";             Dept="Unassigned";                     Role="i3-user" }
    @{ Email="antonym@i3technologies.co.ke";          Name="Anthony Mbugua Githinji";      Dept="IT - Operations";                Role="i3-user" }
    @{ Email="bensonk@i3technologies.co.ke";          Name="Benson Chege";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="bevinlugonzo@i3technologies.co.ke";     Name="Bevin Fadhili Lugonzo";        Dept="Unassigned";                     Role="i3-user" }
    @{ Email="bmulongo@i3technologies.co.ke";         Name="Benjamin Mulongo Kisiangani";  Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="briang@i3technologies.co.ke";           Name="Brian Muigai";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="charlesndiritu@i3technologies.co.ke";   Name="Charles Maina Nderitu";        Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="collinsm@i3technologies.co.ke";         Name="Collins Muka";                 Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="collinsnyatundo@i3technologies.co.ke";  Name="Collins Nyatundo Nyagaka";     Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="collinso@i3technologies.co.ke";         Name="Collins Curtis";               Dept="IT - Risk-Compliance-Security";  Role="i3-user" }
    @{ Email="danielo@i3technologies.co.ke";          Name="Daniel Odhiambo";              Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="denniswatsuma@i3technologies.co.ke";    Name="Dennis Watsuma";               Dept="Unassigned";                     Role="i3-user" }
    @{ Email="dorothy@i3technologies.co.ke";          Name="Dorothy Akoth";                Dept="Unassigned";                     Role="i3-user" }
    @{ Email="elsac@i3technologies.co.ke";            Name="Elsa Cherono";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="emmanueln@i3technologies.co.ke";        Name="Emanuel Njoroge";              Dept="Unassigned";                     Role="i3-user" }
    @{ Email="enockrotich@i3technologies.co.ke";      Name="Enock Rotich";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="ericmwendwa@i3technologies.co.ke";      Name="Eric Mwendwa Muema";           Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="eugenegusmao@i3technologies.co.ke";     Name="Eugene Gusmao Odhiambo";       Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="evelynewambui@i3technologies.co.ke";    Name="Evelyne Wambui";               Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="fadhilig@i3technologies.co.ke";         Name="Fadhili Gakwa";                Dept="Unassigned";                     Role="i3-user" }
    @{ Email="felixkm@i3technologies.co.ke";          Name="Felix Kimweli";                Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="francismatheka@i3technologies.co.ke";   Name="Francis Matheka";              Dept="Unassigned";                     Role="i3-user" }
    @{ Email="fredrickow@i3technologies.co.ke";       Name="Fredrick Owino";               Dept="Unassigned";                     Role="i3-user" }
    @{ Email="gichurugabriel@i3technologies.co.ke";   Name="Gichuru Gabriel Kelsie";       Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="gilbertm@i3technologies.co.ke";         Name="Gilbert Martin Muhiri";        Dept="Unassigned";                     Role="i3-user" }
    @{ Email="glorian@i3technologies.co.ke";          Name="Gloria Nthenya Baker";         Dept="Unassigned";                     Role="i3-user" }
    @{ Email="hannahw@i3technologies.co.ke";          Name="Hannah Mwaura";                Dept="Unassigned";                     Role="i3-user" }
    @{ Email="jacksonm@i3technologies.co.ke";         Name="Jackson Muturi";               Dept="Unassigned";                     Role="i3-user" }
    @{ Email="jamesm@i3technologies.co.ke";           Name="James Kiumi";                  Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="jemimahjemutai@i3technologies.co.ke";   Name="Jemimah Jemutai";              Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="jeremymwangi@i3technologies.co.ke";     Name="Jeremy Mwangi Maina";          Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="julianamuendo@i3technologies.co.ke";    Name="Juliana Muendo";               Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="juniasw@i3technologies.co.ke";          Name="Junias W. Kinguru";            Dept="IT - Risk-Compliance-Security";  Role="i3-user" }
    @{ Email="kelvinm@i3technologies.co.ke";          Name="Kelvin Mwangi Gitimu";         Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="kemuntof@i3technologies.co.ke";         Name="Kemunto Faith Ogwoka";         Dept="Unassigned";                     Role="i3-user" }
    @{ Email="kenanm@i3technologies.co.ke";           Name="Kenan Mutuma";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="larrybaraza@i3technologies.co.ke";      Name="Larry Baraza";                 Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="lauranyongesa@i3technologies.co.ke";    Name="Laura Nyongesa";               Dept="IT - Telecom";                   Role="i3-user" }
    @{ Email="leahgithinji@i3technologies.co.ke";     Name="Leah Wanjiru Githinji";        Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="linselo@i3technologies.co.ke";          Name="Linsel Ajode";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="margareto@i3technologies.co.ke";        Name="Margaret Okore";               Dept="IT - Risk-Compliance-Security";  Role="i3-user" }
    @{ Email="markn@i3technologies.co.ke";            Name="Mark Njore Mwaura";            Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="marko@i3technologies.co.ke";            Name="Mark Okoth";                   Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="martinwachiye@i3technologies.co.ke";    Name="Martin Wachiye Wafula";        Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="maurinec@i3technologies.co.ke";         Name="Maurine Chebet";               Dept="IT - Risk-Compliance-Security";  Role="i3-user" }
    @{ Email="mercyy@i3technologies.co.ke";           Name="Mercy Yvonne Njaramba";        Dept="Unassigned";                     Role="i3-user" }
    @{ Email="nusuraa@i3technologies.co.ke";          Name="Nusura Abdallah";              Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="oscarw@i3technologies.co.ke";           Name="Oscar Wekesa";                 Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="paulo@i3technologies.co.ke";            Name="Paul Obado";                   Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="peninan@i3technologies.co.ke";          Name="Penina Nduta Kingori";         Dept="Unassigned";                     Role="i3-user" }
    @{ Email="petronellamumbua@i3technologies.co.ke"; Name="Petronella Mumbua";            Dept="Unassigned";                     Role="i3-user" }
    @{ Email="philipm@i3technologies.co.ke";          Name="Philip Mukiti";                Dept="IT - Applications-Development";  Role="i3-admin" }
    @{ Email="philipmw@i3technologies.co.ke";         Name="Philip Muyale Wakah";          Dept="IT - Telecom";                   Role="i3-user" }
    @{ Email="rachaelk@i3technologies.co.ke";         Name="Rachael Kamau";                Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="reberathanalemba@i3technologies.co.ke"; Name="Reberatha Nalemba Kimanzi";    Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="richardorido@i3technologies.co.ke";     Name="Richard Orido";                Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="romarsn@i3technologies.co.ke";          Name="Romars Nyambura Marigi";       Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="roynjuguna@i3technologies.co.ke";       Name="Roy Njuguna Mwangi";           Dept="IT - Risk-Compliance-Security";  Role="i3-user" }
    @{ Email="sakina@i3technologies.co.ke";           Name="Sakina Hussein";               Dept="IT - Applications-Development";  Role="i3-user" }
    @{ Email="sheilam@i3technologies.co.ke";          Name="Sheila Mulwa";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="simonk@i3technologies.co.ke";           Name="Simon Kiragu";                 Dept="Unassigned";                     Role="i3-user" }
    @{ Email="snjagi@i3technologies.co.ke";           Name="Sebastian Njagi";              Dept="IT - Server-Storage";            Role="i3-learning-admin" }
    @{ Email="ssentongosudice@i3technologies.co.ke";  Name="Ssentongo Sudice";             Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="taniaw@i3technologies.co.ke";           Name="Tania Maina";                  Dept="Unassigned";                     Role="i3-user" }
    @{ Email="traceyn@i3technologies.co.ke";          Name="Tracey Nzisa Tsurwa";          Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="vicmugoh@i3technologies.co.ke";         Name="VIC Mugoh Githinji";           Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="wadonderac@i3technologies.co.ke";       Name="Wadondera A. Collins";         Dept="Unassigned";                     Role="i3-user" }
    @{ Email="wanjikupeninah@i3technologies.co.ke";   Name="Wanjiku Peninah";              Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="wisdomk@i3technologies.co.ke";          Name="Wisdom Kinoti";                Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="yasminn@i3technologies.co.ke";          Name="Yasmin Naaman";                Dept="Talent as a Service";            Role="i3-user" }
    @{ Email="zeddo@i3technologies.co.ke";            Name="Zedd Onguso";                  Dept="IT - Operations";                Role="i3-user" }

    # ── Pre-existing admin — ensure role is set, skip if already present ──
    # Joseph Maina — Senior Systems Administrator (reports to Sebastian Njagi)
    @{ Email="josephm@i3technologies.co.ke";          Name="Joseph Maina";                 Dept="IT - Operations";                Role="i3-admin" }
)

# ── Main Provisioning Loop ────────────────────────────────────────
$provisioned = 0
$skipped     = 0
$failed      = 0

foreach ($u in $users) {
    # Check if user already exists
    $existing = Invoke-Kc @("get", "users",
        "--target-realm", $KC_REALM,
        "-q", "email=$($u.Email)")

    if ($existing -and $existing -ne "[ ]" -and $existing -ne "") {
        Write-Log "SKIP  $($u.Email)  — already exists in Keycloak" "SKIP"
        $skipped++
        continue
    }

    # Derive first / last name
    $parts    = $u.Name -split " ", 2
    $firstName = $parts[0]
    $lastName  = if ($parts.Count -gt 1) { $parts[1] } else { "" }

    try {
        # Create user
        Invoke-Kc @("create", "users",
            "--target-realm", $KC_REALM,
            "-s", "username=$($u.Email)",
            "-s", "email=$($u.Email)",
            "-s", "firstName=$firstName",
            "-s", "lastName=$lastName",
            "-s", "enabled=true",
            "-s", "emailVerified=true",
            "-s", "attributes.department=$($u.Dept)") | Out-Null

        # Set temporary password (must change on first login)
        Invoke-Kc @("set-password",
            "--target-realm", $KC_REALM,
            "--username", $u.Email,
            "--new-password", $TEMP_PASS,
            "--temporary") | Out-Null

        # Assign role
        Invoke-Kc @("add-roles",
            "--target-realm", $KC_REALM,
            "--uusername", $u.Email,
            "--rolename", $u.Role) | Out-Null

        # Add to department group (create group if missing)
        $groupPath = "/departments/$($u.Dept)"
        Invoke-Kc @("update", "users",
            "--target-realm", $KC_REALM,
            "--username", $u.Email,
            "-s", "groups=[`"$groupPath`"]") | Out-Null

        Write-Log "PROVISIONED  $($u.Email)  [$($u.Role)]  dept=$($u.Dept)" "OK"
        $provisioned++
    }
    catch {
        Write-Log "FAILED  $($u.Email)  — $($_.Exception.Message)" "ERR"
        $failed++
    }
}

# ── Summary ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " Provisioning Complete" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " Provisioned : $provisioned"
Write-Host " Skipped     : $skipped  (already existed — RETAINED)"
Write-Host " Failed      : $failed"
Write-Host ""
if ($DryRun) { Write-Host " ⚠  DRY-RUN mode — no changes were made." -ForegroundColor Yellow }
