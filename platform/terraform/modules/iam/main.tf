# ============================================================
# Terraform Module: IAM — Service IDs, API Keys, COS HMAC
# Creates: Terraform service ID + API key + COS HMAC credentials
# ============================================================

terraform {
  required_providers {
    ibm = { source = "ibm-cloud/ibm" }
  }
}

variable "resource_group" { type = string }
variable "cos_instance_crn" { type = string }

data "ibm_resource_group" "rg" {
  name = var.resource_group
}

# Terraform automation service ID
resource "ibm_iam_service_id" "terraform" {
  name        = "i3-terraform-automation"
  description = "Service ID used by Terraform for IBM Cloud infrastructure provisioning"
  tags        = ["platform:i3", "env:production"]
}

# IAM policy: platform admin on i3-production resource group
resource "ibm_iam_service_policy" "terraform_admin" {
  iam_service_id = ibm_iam_service_id.terraform.id
  roles          = ["Administrator", "Manager"]

  resources {
    resource_group_id = data.ibm_resource_group.rg.id
  }
}

# IAM policy: Kubernetes Service admin (for ROKS cluster management)
resource "ibm_iam_service_policy" "kubernetes_admin" {
  iam_service_id = ibm_iam_service_id.terraform.id
  roles          = ["Administrator", "Manager"]

  resources {
    service = "containers-kubernetes"
  }
}

# IAM policy: VPC infrastructure admin
resource "ibm_iam_service_policy" "vpc_admin" {
  iam_service_id = ibm_iam_service_id.terraform.id
  roles          = ["Administrator"]

  resources {
    service = "is"
  }
}

# COS HMAC credentials (for Terraform remote state + rclone)
resource "ibm_resource_key" "cos_hmac" {
  name                 = "i3-cos-hmac-key"
  resource_instance_id = var.cos_instance_crn
  role                 = "Writer"

  parameters = {
    HMAC = "true"
  }
}

output "terraform_service_id" { value = ibm_iam_service_id.terraform.id }
