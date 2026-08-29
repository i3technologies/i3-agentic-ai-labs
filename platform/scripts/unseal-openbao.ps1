#!/usr/bin/env pwsh
# ============================================================
# OpenBao Unseal Script
# Usage: . .\platform\scripts\load-env.ps1
#        .\platform\scripts\unseal-openbao.ps1
# 
# Unseals all openbao pods in i3-security namespace.
# Keys are read from environment variables set by load-env.ps1
# ============================================================

param(
  [int]$TimeoutSeconds = 120
)

# Prefer `oc` (OpenShift CLI) if available, fall back to `kubectl`
$oc = if (Get-Command oc -ErrorAction SilentlyContinue) { "oc" }
      elseif (Get-Command kubectl -ErrorAction SilentlyContinue) { "kubectl" }
      else {
        # Last-resort: check common WinGet install paths
        $candidates = @(
          "C:\tools\oc\oc.exe",
          "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Kubernetes.kubectl_Microsoft.Winget.Source_8wekyb3d8bbwe\kubectl.exe"
        )
        $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($found) { $found }
        else { Write-Error "Neither oc nor kubectl found on PATH. Run: . .\platform\scripts\setup-path.ps1"; exit 1 }
      }

$ns        = "i3-security"
$threshold = 3

$keys = @(
  $env:OPENBAO_UNSEAL_KEY_1,
  $env:OPENBAO_UNSEAL_KEY_2,
  $env:OPENBAO_UNSEAL_KEY_3
)

if ($keys | Where-Object { -not $_ }) {
  Write-Error "Missing OPENBAO_UNSEAL_KEY_1/2/3 in environment. Run load-env.ps1 first."
  exit 1
}

# Get all openbao pods — label used by the StatefulSet template is app=openbao
$pods = & $oc get pods -n $ns -l "app=openbao" --no-headers 2>&1 |
  Where-Object { $_ -match "Running" } |
  ForEach-Object { ($_ -split '\s+')[0] }

if (-not $pods) {
  Write-Error "No running openbao pods found in $ns. Check: $oc get pods -n $ns"
  exit 1
}

foreach ($pod in $pods) {
  Write-Host "`n=== Checking $pod ==="

  # Check if already unsealed
  $statusRaw = & $oc exec -n $ns $pod -- bao status -format=json 2>&1
  $status    = $statusRaw -join "" | ConvertFrom-Json -ErrorAction SilentlyContinue
  if ($status -and $status.sealed -eq $false) {
    Write-Host "  $pod`: already unsealed. Skipping."
    continue
  }
  if ($status -and -not $status.initialized) {
    Write-Host "  $pod`: not initialized — joining raft cluster (TLS)..."
    & $oc exec -n $ns $pod -- bao operator raft join `
      "https://openbao-0.openbao-internal.i3-security.svc.cluster.local:8200" 2>&1
  }

  Write-Host "  Unsealing $pod`..."
  foreach ($key in $keys) {
    $result = & $oc exec -n $ns $pod -- bao operator unseal $key 2>&1 |
              Select-String "Sealed|Progress|Unseal"
    Write-Host "    $result"
  }

  # Verify
  $finalRaw    = & $oc exec -n $ns $pod -- bao status -format=json 2>&1
  $finalStatus = $finalRaw -join "" | ConvertFrom-Json -ErrorAction SilentlyContinue
  if ($finalStatus -and $finalStatus.sealed -eq $false) {
    Write-Host "  ✓ $pod unsealed successfully" -ForegroundColor Green
  } else {
    Write-Warning "  $pod still sealed — may need more keys or check raft join status"
  }
}

Write-Host "`n=== Final OpenBao pod status ==="
& $oc get pods -n $ns 2>&1
