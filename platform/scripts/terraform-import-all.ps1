# terraform-import-all.ps1
# Imports all existing IBM Cloud resources into Terraform state
# so that 'plan' shows 0 destroys before we apply.
#
# IDs taken directly from the terraform plan output (2026-08-16 run).
# Run this ONCE from workspace root after 'init -reconfigure'.

. .\platform\scripts\load-env.ps1
$env:TF_VAR_ibmcloud_api_key = $env:IBMCLOUD_API_KEY

$tf  = "C:\tools\tf198\terraform.exe"
$dir = "C:\Users\Admin\Documents\i3-Agentic-AI-Labs\platform\terraform"

# Write API key for the import calls
$tmpVars = "$dir\_api_key.auto.tfvars"
Set-Content -Path $tmpVars -Value "ibmcloud_api_key = `"$env:IBMCLOUD_API_KEY`"" -Encoding UTF8

function tf-import($address, $id) {
    Write-Host ""
    Write-Host "Importing: $address" -ForegroundColor Cyan
    Write-Host "       ID: $id"
    & $tf "-chdir=$dir" import -input=false $address $id
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  -> already in state or not found (continuing)" -ForegroundColor Yellow
    }
}

Write-Host "=== Re-init ===" -ForegroundColor Yellow
& $tf "-chdir=$dir" init `
  "-backend-config=access_key=$env:TF_COS_ACCESS_KEY" `
  "-backend-config=secret_key=$env:TF_COS_SECRET_KEY" `
  -reconfigure 2>&1 | Select-Object -Last 3

Write-Host ""
Write-Host "=== Importing VPC ===" -ForegroundColor Green
tf-import "module.vpc.ibm_is_vpc.main"                               "r010-ee352d42-6958-4f2b-b679-be9245ad925b"

Write-Host ""
Write-Host "=== Importing VPC Address Prefixes ===" -ForegroundColor Green
tf-import 'module.vpc.ibm_is_vpc_address_prefix.zone["eu-de-1"]'    "r010-ee352d42-6958-4f2b-b679-be9245ad925b/r010-05d81b58-609a-4359-b7f6-fc810512936f"
tf-import 'module.vpc.ibm_is_vpc_address_prefix.zone["eu-de-2"]'    "r010-ee352d42-6958-4f2b-b679-be9245ad925b/r010-853fd7fe-70d5-4fa1-976e-74189c208fe8"
tf-import 'module.vpc.ibm_is_vpc_address_prefix.zone["eu-de-3"]'    "r010-ee352d42-6958-4f2b-b679-be9245ad925b/r010-54ec8183-d2e6-45b4-a75c-cc55366874b6"

Write-Host ""
Write-Host "=== Importing Subnets ===" -ForegroundColor Green
tf-import 'module.vpc.ibm_is_subnet.worker["eu-de-1"]'              "02b7-ae592cea-2eb3-4ff3-b813-c373a855d88d"
tf-import 'module.vpc.ibm_is_subnet.worker["eu-de-2"]'              "02c7-265c7cfb-7719-439e-b890-19a426674f92"
tf-import 'module.vpc.ibm_is_subnet.worker["eu-de-3"]'              "02d7-2a6338f5-69e9-4d7e-be2d-9cdbdb6624a0"

Write-Host ""
Write-Host "=== Importing ROKS Cluster ===" -ForegroundColor Green
tf-import "module.roks.ibm_container_vpc_cluster.main"               "da0umukf0anep6valpig"

Write-Host ""
Write-Host "=== Importing Default Worker Pool ===" -ForegroundColor Green
tf-import "module.roks.ibm_container_vpc_worker_pool.default_cpu"    "da0umukf0anep6valpig/da0umukf0anep6valpig-6f9caaa"

Write-Host ""
Write-Host "=== Importing IAM Trusted Profile ===" -ForegroundColor Green
tf-import "module.iam.ibm_iam_trusted_profile.workload_identity"     "Profile-bf810386-1ee3-48ea-9de1-adde072a14dd"

Write-Host ""
Write-Host "=== Importing Public Gateways ===" -ForegroundColor Green
tf-import 'module.vpc.ibm_is_public_gateway.pgw["eu-de-1"]'         "r010-723e4de8-b5c9-4946-948a-5bbcfc04b5cd"
tf-import 'module.vpc.ibm_is_public_gateway.pgw["eu-de-2"]'         "r010-5cae4783-9867-4d6e-a84c-6522453af1f4"
tf-import 'module.vpc.ibm_is_public_gateway.pgw["eu-de-3"]'         "r010-830f91be-4fb3-46b0-9504-289327a68bab"

Remove-Item $tmpVars -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== Import complete. Now run: .\run-tf-plan.ps1 ===" -ForegroundColor Green
Write-Host "Target: plan should show 0 destroys of existing resources."
