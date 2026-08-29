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

# Standard COS instance (used for ROKS etcd backup + IAM)
resource "ibm_resource_instance" "cos" {
  name              = var.cos_instance_name
  resource_group_id = data.ibm_resource_group.rg.id
  service           = "cloud-object-storage"
  plan              = "standard"
  location          = "global"
  tags              = ["platform:i3", "env:production"]
}

# Terraform state bucket
resource "ibm_cos_bucket" "tfstate" {
  bucket_name          = var.cos_bucket_name
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"

  lifecycle_rule {
    id      = "expire-old-state"
    enable  = true
    expiration {
      days = 365
    }
  }
}

# Platform data bucket (SeaweedFS DR + pgBackRest backup)
resource "ibm_cos_bucket" "platform" {
  bucket_name          = "i3-platform-data-eu-de"
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"
}

# pgBackRest backup bucket
resource "ibm_cos_bucket" "pgbackrest" {
  bucket_name          = "i3-postgres-backup-eu-de"
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"
}

# SeaweedFS DR bucket
resource "ibm_cos_bucket" "seaweedfs_dr" {
  bucket_name          = "i3-seaweedfs-dr-eu-de"
  resource_instance_id = ibm_resource_instance.cos.id
  region_location      = var.region
  storage_class        = "smart"
}

output "instance_crn"          { value = ibm_resource_instance.cos.crn }
output "standard_instance_crn" { value = ibm_resource_instance.cos.crn }
output "tfstate_bucket_name"   { value = ibm_cos_bucket.tfstate.bucket_name }
output "platform_bucket_name"  { value = ibm_cos_bucket.platform.bucket_name }
