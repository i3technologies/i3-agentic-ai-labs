#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Ingests all C1000-207 practice exam CSVs from the Watsonx-Orchestrate-Exam-Bank
  folder into EvalOS via its REST API.

.DESCRIPTION
  Reads all 6 CSV files (360 questions total), transforms each row into the EvalOS
  question schema, and POSTs them via the EvalOS Admin API.

  Exam Bank layout:
    Question_Number, Domain_Number, Domain_Name, Question_Type,
    Question, Option_A–E, Correct_Answer, Explanation

  Question types:
    MC  = Multiple Choice (single correct answer)
    MR  = Multiple Response (multiple correct answers - Correct_Answer = "A,C" etc.)

  This script:
    1. Obtains a Keycloak bearer token for the admin service account
    2. Creates an Exam Bank named "C1000-207 - IBM watsonx Orchestrate v2 Associate"
       (idempotent - skips if already exists)
    3. Creates 7 Topics (one per domain) inside that bank
    4. Upserts all 360 questions, tagged with set number + domain
    5. Creates 6 Practice Exam sets, each with 60 questions linked to the bank

.PREREQUISITES
  - oc is logged in against i3-platform cluster (for token retrieval)
  - curl.exe in PATH (or PowerShell 7 with Invoke-RestMethod)
  - EvalOS running at https://evalos.i3technologies.co.ke
  - Keycloak realm i3, client evalos-spa, admin user with instructor role

.USAGE
  . .\platform\scripts\load-env.ps1
  .\platform\scripts\ingest-evalos-questions.ps1

  # Dry-run (validate CSV only, no API calls)
  .\platform\scripts\ingest-evalos-questions.ps1 -DryRun

  # Ingest a specific set only
  .\platform\scripts\ingest-evalos-questions.ps1 -SetFilter 1

.PARAMETERS
  -DryRun     Validate and preview without making API calls
  -SetFilter  Ingest only the specified set number (1-6). Default: all
  -BaseUrl    Override EvalOS base URL (default: https://evalos.i3technologies.co.ke)
#>

param(
  [switch] $DryRun,
  [int]    $SetFilter = 0,
  [string] $BaseUrl   = "https://evalos.i3technologies.co.ke"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# ── Config ────────────────────────────────────────────────────────────────────
$KC_URL      = "https://sso.i3technologies.co.ke/auth"
$KC_REALM    = "i3"
$KC_CLIENT   = "admin-cli"           # admin-cli on master realm — evalos-spa blocks password grant
$KC_TOKEN_REALM = "master"           # Token obtained from master realm, API calls target i3 realm
$CSV_DIR     = Join-Path $PSScriptRoot "..\..\Watsonx-Orchestrate-Exam-Bank"
$EXAM_TITLE  = 'C1000-207 - IBM watsonx Orchestrate v2 Associate'
$EXAM_CODE   = "C1000-207"

# Domain -> topic description map
$DOMAIN_DESC = @{
  "1" = 'Platform Architecture and Core Concepts (15pct)'
  "2" = 'Agent and Assistant Integration (20pct)'
  "3" = 'Workflow and Orchestration Design (15pct)'
  "4" = 'Agent Development (20pct)'
  "5" = 'Model Management (15pct)'
  "6" = 'Security, Compliance, and Observability (10pct)'
  "7" = 'Deployment, Scaling, Optimization, and Resiliency (5pct)'
}

# ── Helper: REST call ─────────────────────────────────────────────────────────
function Invoke-EvalOS {
  param(
    [string] $Method,
    [string] $Path,
    [object] $Body,
    [string] $Token
  )
  $uri     = "$BaseUrl/api$Path"
  $headers = @{ Authorization = "Bearer $Token"; "Content-Type" = "application/json" }
  $json    = if ($Body) { $Body | ConvertTo-Json -Depth 10 -Compress } else { $null }
  try {
    $resp = Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $json -ErrorAction Stop
    return $resp
  } catch {
    $status = $_.Exception.Response.StatusCode.value__
    $detail = $_.ErrorDetails.Message
    if ($status -eq 409) { return $null }   # Already exists - treat as OK
    Write-Error "[$Method $Path] HTTP $status - $detail"
    throw
  }
}

# ── Step 1: Get Keycloak Token (skipped in -DryRun) ──────────────────────────
$TOKEN = ""
$ADMIN_USER = ""
$ADMIN_PASS = ""

if (-not $DryRun) {
  Write-Host "[1] Obtaining Keycloak token..." -ForegroundColor Cyan

  # Try OpenBao first
  try {
    $baoOut     = oc exec -n i3-security openbao-0 -- bao kv get -format=json i3/keycloak/admin 2>&1 | ConvertFrom-Json
    $ADMIN_PASS = $baoOut.data.data.password
    $ADMIN_USER = $baoOut.data.data.username
    Write-Host "  Credentials loaded from OpenBao" -ForegroundColor Gray
  } catch {
    Write-Host "  OpenBao unavailable - trying cluster secret..." -ForegroundColor Yellow
    # Fall back to the credential-i3-keycloak secret on the cluster
    try {
      $rawPass    = oc get secret credential-i3-keycloak -n i3-auth -o jsonpath="{.data.ADMIN_PASSWORD}" 2>&1
      $ADMIN_PASS = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($rawPass.Trim()))
      $ADMIN_USER = "admin"
      Write-Host "  Credentials loaded from cluster secret" -ForegroundColor Gray
    } catch {
      Write-Host "  Cluster secret unavailable - checking env vars..." -ForegroundColor Yellow
      $ADMIN_USER = if ($env:EVALOS_ADMIN_USER) { $env:EVALOS_ADMIN_USER } else { "" }
      $ADMIN_PASS = if ($env:EVALOS_ADMIN_PASS) { $env:EVALOS_ADMIN_PASS } else { "" }
      if (-not $ADMIN_PASS) {
        $cred       = Get-Credential -Message "Enter Keycloak admin password (user: admin)"
        $ADMIN_USER = $cred.UserName
        $ADMIN_PASS = $cred.GetNetworkCredential().Password
      }
    }
  }

  # Token from master realm using admin-cli
  $tokenResp = Invoke-RestMethod -Method POST `
    -Uri "$KC_URL/realms/$KC_TOKEN_REALM/protocol/openid-connect/token" `
    -Body @{
      client_id  = $KC_CLIENT
      grant_type = "password"
      username   = $ADMIN_USER
      password   = $ADMIN_PASS
    } -ErrorAction Stop

  $TOKEN = $tokenResp.access_token
  Write-Host "  Token obtained (expires in $($tokenResp.expires_in)s)" -ForegroundColor Green
} else {
  Write-Host "[1] Skipping token (dry run)" -ForegroundColor Yellow
}

# ── Step 2: Load and validate CSV files ──────────────────────────────────────
Write-Host "[2] Loading CSV files from: $CSV_DIR" -ForegroundColor Cyan

$csvFiles = Get-ChildItem -Path $CSV_DIR -Filter "C1000-207_Practice_Exam_Set*_CSV.csv" | Sort-Object Name
if ($csvFiles.Count -eq 0) { Write-Error "No CSV files found in $CSV_DIR"; exit 1 }

$allQuestions = [System.Collections.Generic.List[PSCustomObject]]::new()

foreach ($file in $csvFiles) {
  $setNum = [regex]::Match($file.Name, 'Set(\d+)').Groups[1].Value
  if ($SetFilter -gt 0 -and [int]$setNum -ne $SetFilter) { continue }

  $rows = Import-Csv $file.FullName
  $rows | ForEach-Object {
    $_ | Add-Member -NotePropertyName "SetNumber" -NotePropertyValue $setNum -Force
    $allQuestions.Add($_)
  }
  Write-Host "  Loaded $($rows.Count) questions from Set $setNum ($($file.Name))" -ForegroundColor Gray
}

Write-Host "  Total: $($allQuestions.Count) questions loaded" -ForegroundColor Green

# Validate: check all required columns present
$required = @("Question_Number","Domain_Number","Domain_Name","Question_Type","Question","Option_A","Option_B","Option_C","Correct_Answer","Explanation")
$missing  = $required | Where-Object { $allQuestions[0].PSObject.Properties.Name -notcontains $_ }
if ($missing) { Write-Error "Missing columns in CSV: $($missing -join ', ')"; exit 1 }

Write-Host "  CSV schema validated OK" -ForegroundColor Green

# Initialise variables that StrictMode checks at parse time even in -DryRun
$bank    = $null
$bankId  = $null
$topicIds = @{}
$topic   = $null

if ($DryRun) {
  Write-Host "`n[DRY RUN SUMMARY]" -ForegroundColor Yellow
  $allQuestions | Group-Object Domain_Name | Sort-Object { [int]($_.Group[0].Domain_Number) } | ForEach-Object {
    $mc = @($_.Group | Where-Object { $_.Question_Type -eq "MC" }).Count
    $mr = @($_.Group | Where-Object { $_.Question_Type -eq "MR" }).Count
    Write-Host "  Domain $($_.Group[0].Domain_Number): $($_.Name) - $($_.Count) questions (MC:$mc / MR:$mr)"
  }
  Write-Host "`n  Dry run complete - no changes made." -ForegroundColor Yellow
  exit 0
}

# ── Step 3: Create Exam Bank ──────────────────────────────────────────────────
Write-Host "[3] Creating Exam Bank: '$EXAM_TITLE'..." -ForegroundColor Cyan

$bank = Invoke-EvalOS -Method POST -Path "/admin/exam-banks" -Token $TOKEN -Body @{
  title       = $EXAM_TITLE
  code        = $EXAM_CODE
  description = "IBM Certified Associate Developer - watsonx Orchestrate v2 (C1000-207). 360 practice questions across 7 domains covering platform architecture, agent development, workflow design, model management, security, and deployment."
  tags        = @("ibm-certification", "watsonx", "orchestrate", "C1000-207")
}

$bankId = if ($bank) { $bank.id } else {
  # Already exists - fetch it
  (Invoke-EvalOS -Method GET -Path "/admin/exam-banks?code=$EXAM_CODE" -Token $TOKEN).data[0].id
}
Write-Host "  Exam Bank ID: $bankId" -ForegroundColor Green

# ── Step 4: Create Topics (one per domain) ───────────────────────────────────
Write-Host "[4] Creating domain topics..." -ForegroundColor Cyan

$topicIds = @{}
$uniqueDomains = $allQuestions | Select-Object Domain_Number, Domain_Name -Unique | Sort-Object { [int]$_.Domain_Number }

foreach ($d in $uniqueDomains) {
  $topic = Invoke-EvalOS -Method POST -Path "/admin/exam-banks/$bankId/topics" -Token $TOKEN -Body @{
    name        = $d.Domain_Name
    description = $DOMAIN_DESC[$d.Domain_Number]
    domainNumber = [int]$d.Domain_Number
  }
  $topicId = if ($topic) { $topic.id } else {
    (Invoke-EvalOS -Method GET -Path "/admin/exam-banks/$bankId/topics?domain=$($d.Domain_Number)" -Token $TOKEN).data[0].id
  }
  $topicIds[$d.Domain_Number] = $topicId
  Write-Host "  Domain $($d.Domain_Number): $($d.Domain_Name) → Topic $topicId" -ForegroundColor Gray
}

# ── Step 5: Upsert Questions ─────────────────────────────────────────────────
Write-Host "[5] Ingesting $($allQuestions.Count) questions..." -ForegroundColor Cyan

$ingested = 0; $skipped = 0; $errors = 0

foreach ($q in $allQuestions) {
  # Build options array - include non-empty options only
  $options = @()
  @("A","B","C","D","E") | ForEach-Object {
    $val = $q."Option_$_"
    if ($val -and $val.Trim() -ne "") {
      $options += @{ label = $_; text = $val.Trim() }
    }
  }

  # Handle MC vs MR correct answers
  $correctAnswers = if ($q.Question_Type -eq "MR") {
    $q.Correct_Answer -split '[,/]' | ForEach-Object { $_.Trim().ToUpper() }
  } else {
    @($q.Correct_Answer.Trim().ToUpper())
  }

  $payload = @{
    bankId       = $bankId
    topicId      = $topicIds[$q.Domain_Number]
    setNumber    = [int]$q.SetNumber
    questionNumber = [int]$q.Question_Number
    type         = $q.Question_Type        # "MC" or "MR"
    text         = $q.Question.Trim()
    options      = $options
    correctAnswers = $correctAnswers
    explanation  = $q.Explanation.Trim()
    domain       = @{
      number = [int]$q.Domain_Number
      name   = $q.Domain_Name
    }
    tags         = @("C1000-207", "set-$($q.SetNumber)", "domain-$($q.Domain_Number)")
    difficulty   = "associate"
  }

  try {
    Invoke-EvalOS -Method POST -Path "/admin/exam-banks/$bankId/questions" -Token $TOKEN -Body $payload | Out-Null
    $ingested++
    if ($ingested % 30 -eq 0) { Write-Host "  ...ingested $ingested/$($allQuestions.Count)" -ForegroundColor Gray }
  } catch {
    $errors++
    Write-Host "  ERROR on Q$($q.Question_Number) Set$($q.SetNumber): $_" -ForegroundColor Red
  }
}

Write-Host "  Questions: $ingested ingested, $skipped skipped, $errors errors" -ForegroundColor Green

# ── Step 6: Create Practice Exam Sets ────────────────────────────────────────
Write-Host "[6] Creating Practice Exam sets..." -ForegroundColor Cyan

$setSets = $allQuestions | Group-Object SetNumber
foreach ($set in $setSets) {
  $exam = Invoke-EvalOS -Method POST -Path "/admin/exams" -Token $TOKEN -Body @{
    bankId      = $bankId
    title       = "C1000-207 Practice Set $($set.Name)"
    code        = "C1000-207-SET$($set.Name)"
    description = "60-question practice exam (Set $($set.Name) of 6) for IBM watsonx Orchestrate v2 Associate certification."
    durationMinutes = 90
    passingScore    = 68
    randomizeOrder  = $false
    showExplanations = $true
    tags            = @("C1000-207", "set-$($set.Name)", "practice")
    filter          = @{ setNumber = [int]$set.Name }
  }
  if ($exam) { Write-Host "  Created Exam Set $($set.Name): $($exam.id)" -ForegroundColor Green }
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host " Ingestion complete!" -ForegroundColor Green
Write-Host " Exam Bank : $EXAM_TITLE" -ForegroundColor Green
Write-Host " Bank ID   : $bankId" -ForegroundColor Green
Write-Host " Questions : $ingested ingested" -ForegroundColor Green
Write-Host " Errors    : $errors" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Verify at: $BaseUrl/admin/exam-banks/$bankId"
Write-Host "Assign to students: $BaseUrl/admin/exams"
