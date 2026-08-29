# COS Recovery Runbook

**Purpose:** Recover a destroyed or missing IBM Cloud Object Storage (COS) instance,
recreate all required buckets, and generate fresh HMAC keys so Terraform remote state
can be restored.

**When to use:** If `terraform init` fails with "bucket not found" or if the COS instance
was accidentally deleted.

---

## Prerequisites

```powershell
# Load environment (API key, region, resource group)
. .\platform\scripts\load-env.ps1
. .\platform\scripts\setup-path.ps1
```

---

## Step 1 — Log in to IBM Cloud

```powershell
ibmcloud login --apikey $env:IBMCLOUD_API_KEY -r eu-de -g i3-production
```

---

## Step 2 — Recreate the COS Instance

```powershell
# Check if instance already exists
ibmcloud resource service-instances --service-name cloud-object-storage

# If missing, create it
ibmcloud resource service-instance-create i3-cos-instance cloud-object-storage standard global `
  -g i3-production
```

---

## Step 3 — Recreate Required Buckets

```powershell
$COS_INSTANCE = (ibmcloud resource service-instances --service-name cloud-object-storage --output json | ConvertFrom-Json | Where-Object { $_.name -eq "i3-cos-instance" }).id

# Terraform state bucket
ibmcloud cos bucket-create `
  --bucket i3-tfstate-077d74db `
  --ibm-service-instance-id $COS_INSTANCE `
  --region eu-de `
  --class smart

# pgBackRest backup bucket
ibmcloud cos bucket-create `
  --bucket i3-postgres-backup-eu-de `
  --ibm-service-instance-id $COS_INSTANCE `
  --region eu-de `
  --class smart

# SeaweedFS DR bucket
ibmcloud cos bucket-create `
  --bucket i3-seaweedfs-dr-eu-de `
  --ibm-service-instance-id $COS_INSTANCE `
  --region eu-de `
  --class smart

# Platform data bucket
ibmcloud cos bucket-create `
  --bucket i3-platform-data-eu-de `
  --ibm-service-instance-id $COS_INSTANCE `
  --region eu-de `
  --class smart
```

---

## Step 4 — Create HMAC Credentials

```powershell
ibmcloud resource service-key-create i3-cos-hmac-key Writer `
  --instance-name i3-cos-instance `
  --parameters '{"HMAC":true}'

# Extract and display keys (store securely — never in git)
$keys = ibmcloud resource service-key i3-cos-hmac-key --output json | ConvertFrom-Json
$ACCESS_KEY = $keys.credentials.cos_hmac_access_key_id
$SECRET_KEY = $keys.credentials.cos_hmac_secret_access_key

Write-Host "TF_COS_ACCESS_KEY=$ACCESS_KEY"
Write-Host "TF_COS_SECRET_KEY=$SECRET_KEY"
```

**Store these in your `.env.txt` file:**

```
TF_COS_ACCESS_KEY=<value>
TF_COS_SECRET_KEY=<value>
```

---

## Step 5 — Import into Terraform State

```powershell
# Import the COS instance back into Terraform
make tf-import-iam

# Re-initialize Terraform with recovered backend
make init-infra
```

---

## Step 6 — Verify

```powershell
# List all buckets
ibmcloud cos list-buckets --ibm-service-instance-id $COS_INSTANCE

# Verify Terraform can reach state
cd platform/terraform
terraform state list
```

---

## Recovery Checklist

- [ ] COS instance `i3-cos-instance` recreated and active
- [ ] Bucket `i3-tfstate-077d74db` exists in eu-de
- [ ] Bucket `i3-postgres-backup-eu-de` exists in eu-de
- [ ] Bucket `i3-seaweedfs-dr-eu-de` exists in eu-de
- [ ] Bucket `i3-platform-data-eu-de` exists in eu-de
- [ ] HMAC keys generated and stored in `.env.txt` (NOT committed to git)
- [ ] `make tf-import-iam` completed without errors
- [ ] `make init-infra` completed — Terraform can read/write remote state
- [ ] `make plan-infra` shows no destructive changes
