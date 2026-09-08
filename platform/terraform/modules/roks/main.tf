# ============================================================
# Terraform Module: ROKS Cluster + Worker Pools
# CPU pool: 3×bx2.4x16 (always-on)
# GPU pool: gx2.8x64 (scale-to-zero, burst only)
# OCP entitlement: cloud_pak (MW02049 — zero licensing cost)
# ============================================================

terraform {
  required_providers {
    ibm = { source = "ibm-cloud/ibm" }
  }
}

variable "region"            { type = string }
variable "resource_group"    { type = string }
variable "cluster_name"      { type = string }
variable "vpc_id"            { type = string }
variable "subnet_ids"        { type = list(string) }
variable "worker_flavor"     { type = string }
variable "gpu_worker_flavor" { type = string }
variable "min_workers"       { type = number }
variable "max_workers"       { type = number }
variable "cos_instance_crn"  { type = string }

data "ibm_resource_group" "rg" {
  name = var.resource_group
}

# Use the latest supported OCP version if not pinned
data "ibm_container_cluster_versions" "versions" {
  resource_group_id = data.ibm_resource_group.rg.id
}

resource "ibm_container_vpc_cluster" "main" {
  name                = var.cluster_name
  vpc_id              = var.vpc_id
  flavor              = var.worker_flavor
  worker_count        = var.min_workers
  # Do not pin kube_version — let IBM manage patch updates on the existing cluster
  resource_group_id   = data.ibm_resource_group.rg.id
  cos_instance_crn    = var.cos_instance_crn

  # OCP entitlement — eliminates per-node OCP subscription cost
  entitlement = "cloud_pak"

  zones {
    subnet_id = var.subnet_ids[0]
    name      = "${var.region}-1"
  }

  zones {
    subnet_id = var.subnet_ids[1]
    name      = "${var.region}-2"
  }

  zones {
    subnet_id = var.subnet_ids[2]
    name      = "${var.region}-3"
  }

  tags = ["platform:i3", "env:production"]

  timeouts {
    create = "90m"
    update = "60m"
    delete = "45m"
  }
}

# GPU burst worker pool — DEFERRED to Phase 2 (RHOAI month)
# gx2.8x64 flavor is not available in eu-de; uncomment when GPU nodes become available
# resource "ibm_container_vpc_worker_pool" "gpu_burst" {
#   cluster           = ibm_container_vpc_cluster.main.id
#   worker_pool_name  = "gpu-burst"
#   flavor            = var.gpu_worker_flavor
#   vpc_id            = var.vpc_id
#   worker_count      = 0
#   resource_group_id = data.ibm_resource_group.rg.id
#   entitlement       = "cloud_pak"
#   zones {
#     subnet_id = var.subnet_ids[0]
#     name      = "${var.region}-1"
#   }
#   labels = { "workload" = "gpu-burst", "accelerator" = "v100" }
#   taints { key = "dedicated", value = "gpu", effect = "NoSchedule" }
# }

output "cluster_id"       { value = ibm_container_vpc_cluster.main.id }
output "cluster_name"     { value = ibm_container_vpc_cluster.main.name }
output "ingress_hostname" { value = ibm_container_vpc_cluster.main.ingress_hostname }
output "cpu_pool_name"    { value = "default" }
output "gpu_pool_name"    { value = "gpu-burst" }
