#!/usr/bin/env pwsh
# Watch ROKS worker nodes until all are 'deployed' or a failure is detected.
# Usage: . .\platform\scripts\load-env.ps1 ; .\platform\scripts\watch-workers.ps1

param(
  [int]$IntervalSeconds = 30,
  [int]$TimeoutMinutes  = 30
)

$ibm     = "C:\Program Files\IBM\Cloud\bin\ibmcloud.exe"
$cluster = "i3-platform"
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)

Write-Host "Watching workers for cluster '$cluster' (timeout: ${TimeoutMinutes}m, poll: ${IntervalSeconds}s)"
Write-Host "Press Ctrl+C to stop.`n"

while ((Get-Date) -lt $deadline) {
  $workers = & $ibm ks workers --cluster $cluster --output json 2>$null | ConvertFrom-Json
  $ts      = Get-Date -Format "HH:mm:ss"

  Write-Host "[$ts]"
  $allGood  = $true
  $anyFail  = $false

  foreach ($w in $workers) {
    $shortId = ($w.id -split '-')[-1]
    $state   = $w.lifecycle.actualState
    $zone    = $w.location
    $ip      = if ($w.networkInterfaces[0].ipAddress) { $w.networkInterfaces[0].ipAddress } else { "pending" }

    $icon = switch ($state) {
      "deployed"         { "[OK]  " }
      "provisioning"     { "[...] " }
      "provision_failed" { "[FAIL]" }
      default            { "[?]   " }
    }

    Write-Host "  $icon $shortId  $zone  $ip  $state"

    if ($state -ne "deployed") { $allGood = $false }
    if ($state -eq "provision_failed") { $anyFail = $true }
  }

  if ($allGood) {
    Write-Host "`n[SUCCESS] All workers are deployed!" -ForegroundColor Green
    exit 0
  }

  if ($anyFail) {
    Write-Host "`n[WARNING] One or more workers failed. Investigate before continuing." -ForegroundColor Red
    exit 1
  }

  Write-Host ""
  Start-Sleep -Seconds $IntervalSeconds
}

Write-Host "`n[TIMEOUT] Workers did not converge within ${TimeoutMinutes} minutes." -ForegroundColor Yellow
exit 2
