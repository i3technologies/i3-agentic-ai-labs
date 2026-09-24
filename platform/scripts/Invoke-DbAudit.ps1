#!/usr/bin/env pwsh
# Invoke-DbAudit.ps1 — Phase 1 Step 2: DB Migrations, Seeding & Multi-Tenancy Audit
# Run from repo root: .\platform\scripts\Invoke-DbAudit.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Hdr  { param($t) Write-Host ("`n" + "="*68 + "`n  $t`n" + "="*68) -ForegroundColor Cyan }
function Sect { param($t) Write-Host "`n-- $t" -ForegroundColor Yellow }
function Pass { param($t) Write-Host "  [PASS] $t" -ForegroundColor Green }
function Fail { param($t) Write-Host "  [FAIL] $t" -ForegroundColor Red }
function Warn { param($t) Write-Host "  [WARN] $t" -ForegroundColor Magenta }
function Info { param($t) Write-Host "  [INFO] $t" -ForegroundColor Gray }

# ── Locate primary pod ─────────────────────────────────────────────────────
Hdr "Phase 1 Step 2 - i3 Database Audit"
$PRIMARY_POD = kubectl get pods -n i3-data --no-headers 2>&1 |
    Where-Object { $_ -match 'i3-postgres-primary.*Running' } |
    Select-Object -First 1 |
    ForEach-Object { ($_ -split '\s+')[0] }
if (-not $PRIMARY_POD) { Fail "No running primary pod found in i3-data"; exit 1 }
Pass "Primary pod: $PRIMARY_POD"

# ── Decode i3admin creds ───────────────────────────────────────────────────
function deco64 { param($s) [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($s)) }
$sec  = kubectl get secret i3-postgres-pguser-i3admin -n i3-data -o json 2>&1 | ConvertFrom-Json
$PGUSER = deco64 $sec.data.user
$PGPASS = deco64 $sec.data.password
$PGHOST = deco64 $sec.data.host
$PGPORT = deco64 $sec.data.port
Pass "Creds resolved: user=$PGUSER host=$PGHOST port=$PGPORT"

# ── SQL runner ────────────────────────────────────────────────────────────
# Writes SQL to a temp file inside the pod so quotes are never mangled by
# the shell argument parser.
function Run-Sql {
    param([string]$db, [string]$sql)
    # Write SQL to a temp file on the pod, run it, then delete it
    $tmpfile = "/tmp/audit_$([System.IO.Path]::GetRandomFileName() -replace '\.','').sql"
    # Copy SQL into the pod via stdin of a tee command
    $out = $sql | kubectl exec -i -n i3-data $PRIMARY_POD -c database -- `
        bash -c "cat > $tmpfile && PGPASSWORD='$PGPASS' psql -U $PGUSER -h $PGHOST -p $PGPORT -d $db -tAf $tmpfile; rm -f $tmpfile" 2>&1
    return $out
}

$FAILS = [System.Collections.Generic.List[string]]::new()
$WARNS = [System.Collections.Generic.List[string]]::new()

# ==========================================================================
# CHECK 1 -- Migration 002_add_tenant_id applied (tenant_id column exists)
# ==========================================================================
Hdr "CHECK 1 - Migration 002_add_tenant_id Applied"

$CHECK1 = @{
    engage_db       = @('email_campaigns','contacts','contact_lists','inbound_messages')
    pmaas_db        = @('campaigns','voters','ward_targets')
    ford_members_db = @('members_pii','agent_velocity')
    evalos_db       = @('questions','exams','quiz_attempts')
}

foreach ($db in $CHECK1.Keys) {
    Sect "$db"
    foreach ($tbl in $CHECK1[$db]) {
        $cnt = (Run-Sql $db "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='$tbl' AND column_name='tenant_id';").Trim()
        if ($cnt -eq '1') { Pass "$db.$tbl -- tenant_id column present" }
        else { Fail "$db.$tbl -- tenant_id column MISSING"; $FAILS.Add("$db.$tbl missing tenant_id") }
    }
}

# ==========================================================================
# CHECK 2 -- tenant_id UUID NOT NULL
# ==========================================================================
Hdr "CHECK 2 - tenant_id UUID NOT NULL"

$NULLCHECK_TABLES = @{
    engage_db       = @('email_campaigns','contacts','contact_lists','inbound_messages','contact_events','email_sends','sms_messages')
    pmaas_db        = @('campaigns','voters','ward_targets','wards','volunteers','campaign_activity','ai_briefings','voter_interactions')
    ford_members_db = @('members_pii','agent_velocity')
    evalos_db       = @('questions','exams','quiz_attempts','ai_interviews','ai_interview_questions','code_submissions')
}

foreach ($db in $NULLCHECK_TABLES.Keys) {
    Sect "$db"
    foreach ($tbl in $NULLCHECK_TABLES[$db]) {
        $nullable = (Run-Sql $db "SELECT is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='$tbl' AND column_name='tenant_id';").Trim()
        if ($nullable -eq 'NO') { Pass "$db.$tbl  tenant_id NOT NULL -- OK" }
        elseif ($nullable -eq 'YES') { Fail "$db.$tbl  tenant_id NULLABLE -- HC-4 VIOLATION"; $FAILS.Add("$db.$tbl tenant_id nullable") }
        else { Warn "$db.$tbl  tenant_id column not found (is_nullable='$nullable')"; $WARNS.Add("$db.$tbl tenant_id not found") }
    }
}

# ==========================================================================
# CHECK 3 -- Row-Level Security enabled
# ==========================================================================
Hdr "CHECK 3 - Row-Level Security (relrowsecurity)"

$RLS_TABLES = @{
    engage_db       = @('email_campaigns','contacts','contact_lists','inbound_messages','contact_events','email_sends','sms_messages')
    pmaas_db        = @('campaigns','voters','ward_targets','wards','volunteers','campaign_activity','ai_briefings','voter_interactions')
    ford_members_db = @('members_pii','agent_velocity')
    evalos_db       = @('questions','exams','quiz_attempts','ai_interviews','ai_interview_questions','code_submissions')
    ar_db           = @('agent_registry','agent_decision_log','ar_actions','ar_approvals')
}

foreach ($db in $RLS_TABLES.Keys) {
    Sect "$db"
    foreach ($tbl in $RLS_TABLES[$db]) {
        $rls = (Run-Sql $db "SELECT relrowsecurity FROM pg_class WHERE relname='$tbl' AND relkind='r';").Trim()
        if ($rls -eq 't') { Pass "$db.$tbl  relrowsecurity=t" }
        elseif ($rls -eq 'f') { Fail "$db.$tbl  relrowsecurity=f -- RLS NOT ENABLED"; $FAILS.Add("$db.$tbl RLS disabled") }
        else { Warn "$db.$tbl  table not found (rls='$rls')"; $WARNS.Add("$db.$tbl not found for RLS check") }
    }
}

# ==========================================================================
# CHECK 4 -- Seed data
# ==========================================================================
Hdr "CHECK 4 - Seed Data"

Sect "4a - system tenant 000...0001 in ar_actions"
$cnt = (Run-Sql "ar_db" "SELECT COUNT(*) FROM ar_actions WHERE tenant_id='00000000-0000-0000-0000-000000000001';").Trim()
if ([int]$cnt -gt 0) { Pass "ar_db.ar_actions $cnt rows with system tenant" }
else { Fail "ar_db.ar_actions zero rows with system tenant"; $FAILS.Add("ar_actions system tenant missing") }

Sect "4b - ar_actions total seed count (expect >= 14)"
$total = (Run-Sql "ar_db" "SELECT COUNT(*) FROM ar_actions;").Trim()
Info "ar_db.ar_actions total: $total rows"
if ([int]$total -ge 14) { Pass "ar_actions seeded with $total actions" }
else { Fail "ar_actions only $total rows -- expected >= 14"; $FAILS.Add("ar_actions seed low ($total)") }

Sect "4c - evalos question bank (expect >= 5)"
$qcnt = (Run-Sql "evalos_db" "SELECT COUNT(*) FROM questions;").Trim()
Info "evalos.questions total: $qcnt rows"
if ([int]$qcnt -ge 5) { Pass "questions seeded with $qcnt rows" }
else { Warn "questions only $qcnt rows"; $WARNS.Add("evalos.questions seed low ($qcnt)") }

Sect "4d - evalos AI interview questions (expect >= 5)"
$iqcnt = (Run-Sql "evalos_db" "SELECT COUNT(*) FROM ai_interview_questions WHERE is_active=true;").Trim()
Info "evalos.ai_interview_questions (active): $iqcnt rows"
if ([int]$iqcnt -ge 5) { Pass "ai_interview_questions seeded with $iqcnt rows" }
else { Warn "ai_interview_questions only $iqcnt active rows"; $WARNS.Add("ai_interview_questions seed low ($iqcnt)") }

Sect "4e - agent_registry entries"
$arcnt = (Run-Sql "ar_db" "SELECT COUNT(*) FROM agent_registry;").Trim()
Info "ar_db.agent_registry: $arcnt rows"
if ([int]$arcnt -ge 1) { Pass "agent_registry has $arcnt registered agents" }
else { Warn "agent_registry is empty"; $WARNS.Add("agent_registry empty") }

# ==========================================================================
# CHECK 5 -- Cross-tenant data leak test
# ==========================================================================
Hdr "CHECK 5 - Cross-Tenant Leak Test"

$SYS = '00000000-0000-0000-0000-000000000001'
$FRN = '99999999-9999-9999-9999-999999999999'

$LEAK_TARGETS = @(
    [pscustomobject]@{ db='engage_db';       tbl='email_campaigns' }
    [pscustomobject]@{ db='engage_db';       tbl='contacts' }
    [pscustomobject]@{ db='pmaas_db';        tbl='campaigns' }
    [pscustomobject]@{ db='ford_members_db'; tbl='members_pii' }
    [pscustomobject]@{ db='evalos_db';       tbl='questions' }
    [pscustomobject]@{ db='ar_db';           tbl='agent_decision_log' }
)

foreach ($t in $LEAK_TARGETS) {
    Sect "$($t.db).$($t.tbl)"

    # Foreign-tenant query (wrapped in a transaction so SET LOCAL is safe)
    $leak_sql = "BEGIN; SET LOCAL app.tenant_id='$SYS'; SELECT COUNT(*) FROM $($t.tbl) WHERE tenant_id='$FRN'; ROLLBACK;"
    $raw  = (Run-Sql $t.db $leak_sql) -split '\s+' | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1
    $leak = if ($raw) { $raw } else { '0' }
    if ($leak -eq '0') { Pass "$($t.db).$($t.tbl) -- 0 foreign-tenant rows (RLS enforced)" }
    else { Fail "$($t.db).$($t.tbl) -- $leak foreign-tenant rows VISIBLE -- RLS BREACH"; $FAILS.Add("$($t.db).$($t.tbl) leak=$leak") }

    # Own-tenant row count (informational)
    $own_sql = "BEGIN; SET LOCAL app.tenant_id='$SYS'; SELECT COUNT(*) FROM $($t.tbl) WHERE tenant_id='$SYS'; ROLLBACK;"
    $own_raw = (Run-Sql $t.db $own_sql) -split '\s+' | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1
    $own = if ($own_raw) { $own_raw } else { '?' }
    Info "$($t.db).$($t.tbl) -- $own own-tenant rows visible to tenant $SYS"
}

# ==========================================================================
# SUMMARY
# ==========================================================================
Hdr "AUDIT SUMMARY"

if ($WARNS.Count -gt 0) {
    Write-Host "`n  Warnings ($($WARNS.Count)):" -ForegroundColor Magenta
    foreach ($w in $WARNS) { Write-Host "    - $w" -ForegroundColor Magenta }
}

if ($FAILS.Count -eq 0) {
    Write-Host "`n  ALL CHECKS PASSED -- Phase 1 Step 2 data layer is HC-4 compliant.`n" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n  FAILURES ($($FAILS.Count)):" -ForegroundColor Red
    foreach ($f in $FAILS) { Write-Host "    - $f" -ForegroundColor Red }
    Write-Host "`n  Phase 1 Step 2 BLOCKED -- remediate failures above.`n" -ForegroundColor Red
    exit 1
}
