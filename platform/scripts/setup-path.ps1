# i3 Platform — PATH Setup Script
# Run once after a fresh terminal to activate all tool paths
# Usage: . .\platform\scripts\setup-path.ps1

$toolPaths = @(
    "C:\tools\oc",
    "C:\tools\jq",
    "C:\Program Files\IBM\Cloud\bin",
    "C:\Users\$env:USERNAME\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe"
)

foreach ($p in $toolPaths) {
    if (Test-Path $p) {
        if ($env:Path -notlike "*$p*") {
            $env:Path += ";$p"
            Write-Host "  Added: $p"
        }
    }
}

Write-Host ""
Write-Host "Tool versions active in this session:"
terraform version 2>&1 | Select-Object -First 1
& "C:\Program Files\IBM\Cloud\bin\ibmcloud.exe" version 2>&1 | Select-Object -First 1
& "C:\tools\oc\oc.exe" version --client 2>&1 | Select-Object -First 1
& "C:\tools\jq\jq.exe" --version 2>&1
