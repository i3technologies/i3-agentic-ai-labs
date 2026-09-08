# ============================================================
# Terraform Module: IBM Cloud Object Storage
# Creates: 1 Standard COS instance + tfstate bucket + platform bucket
# ============================================================

terraform {
  required_providers {
    ibm = { source = "ibm-cloud/ibm" }
  }
}

variable "region"            { type = string }
variable "resource_group"    { type = string }
variable "cos_instance_name" { type = string }
variable "cos_bucket_name"   { type = string }

data "ibm_resource_group" "rg" {
  name = var.resource_group
}

# COS instance — keep on lite plan (free tier, matches existing provisioned instance)
resource "ibm_resource_instance" "cos" {
  name              = var.cos_instance_name
  resource_group_id = data.ibm_resource_group.rg.id
  service           = "cloud-object-storage"
  plan              = "lite"
  location          = "global"
  tags              = ["platform:i3", "env:production"]
}

# Terraform state bucket — versioning kept to protect state history
resource "ibm_cos_bucket" "tfstate" {
  bucket_name          = var.cos_bucket_name
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"

  object_versioning {
    enable = true
  }
}

# Platform data bucket — keep existing bucket name
resource "ibm_cos_bucket" "platform" {
  bucket_name          = "i3-platform-077d74db"
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"
}

# pgBackRest backup bucket (new — does not exist yet)
resource "ibm_cos_bucket" "pgbackrest" {
  bucket_name          = "i3-postgres-backup-eu-de"
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"
}

# SeaweedFS DR bucket — keep existing bucket name and versioning
resource "ibm_cos_bucket" "seaweedfs_dr" {
  bucket_name          = "i3-seaweedfs-dr-077d74db"
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"

  object_versioning {
    enable = true
  }
}

output "instance_crn"          { value = ibm_resource_instance.cos.crn }
output "standard_instance_crn" { value = ibm_resource_instance.cos.crn }
output "tfstate_bucket_name"   { value = ibm_cos_bucket.tfstate.bucket_name }
output "platform_bucket_name"  { value = ibm_cos_bucket.platform.bucket_name }
