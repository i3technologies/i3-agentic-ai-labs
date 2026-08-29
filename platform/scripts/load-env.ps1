# i3 Platform — PowerShell Environment Loader
# Usage (run from workspace root):
#   . .\platform\scripts\load-env.ps1
#
# This script reads .env, validates required values are filled in,
# and exports them as process-scoped environment variables.
# Nothing is written to disk.

# Always resolve .env from the current working directory (workspace root)
$envFile = Join-Path (Get-Location) ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "ERROR: .env file not found at $envFile"
    Write-Host  "  Run: Copy-Item .env.example .env"
    Write-Host  "  Then fill in your real values."
    return
}

$missing = @()
$loaded  = 0

Get-Content $envFile | Where-Object { $_ -match "^\s*[^#].*=." } | ForEach-Object {
    $parts = $_ -split "=", 2
    $key   = $parts[0].Trim()
    $value = $parts[1].Trim()

    if ($value -like "REPLACE*") {
        $missing += $key
        return
    }

    [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    $loaded++
}

Write-Host ""
Write-Host "Loaded $loaded environment variables."

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Warning "The following values still need to be filled in .env:"
    $missing | ForEach-Object { Write-Host "  - $_" }
} else {
    Write-Host "All variables set. Ready to run Terraform."
}

# Quick sanity check — key value is masked, never printed in full
Write-Host ""
Write-Host "Key values set:"
Write-Host "  IBMCLOUD_API_KEY      : $(if ($env:IBMCLOUD_API_KEY) { $env:IBMCLOUD_API_KEY.Substring(0,[Math]::Min(6,$env:IBMCLOUD_API_KEY.Length)) + '...[redacted]' } else { 'NOT SET' })"
Write-Host "  TF_VAR_region         : $env:TF_VAR_region"
Write-Host "  TF_VAR_resource_group : $env:TF_VAR_resource_group"
Write-Host "  TF_VAR_cluster_name   : $env:TF_VAR_cluster_name"
