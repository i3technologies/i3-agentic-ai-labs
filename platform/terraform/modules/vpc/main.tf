# ============================================================
# Terraform Module: VPC + Subnets
# Creates: 1 VPC, 2 subnets across 2 availability zones (eu-de-1, eu-de-2)
# ============================================================

terraform {
  required_providers {
    ibm = {
      source = "ibm-cloud/ibm"
    }
  }
}

variable "region"         { type = string }
variable "resource_group" { type = string }
variable "cluster_name"   { type = string }

data "ibm_resource_group" "rg" {
  name = var.resource_group
}

resource "ibm_is_vpc" "main" {
  # Keep the existing VPC name — rename to i3-platform-vpc is blocked by IBM API
  name                      = "i3-prod-vpc"
  resource_group            = data.ibm_resource_group.rg.id
  address_prefix_management = "manual"

  tags = [
    "platform:i3",
    "env:production",
    "region:${var.region}",
  ]
}

resource "ibm_is_vpc_address_prefix" "zone" {
  for_each = {
    "eu-de-1" = "10.240.0.0/18"
    "eu-de-2" = "10.240.64.0/18"
    "eu-de-3" = "10.240.128.0/18"
  }
  name = "${var.cluster_name}-prefix-${each.key}"
  vpc  = ibm_is_vpc.main.id
  zone = each.key
  cidr = each.value
}

resource "ibm_is_subnet" "worker" {
  for_each                 = toset(["eu-de-1", "eu-de-2", "eu-de-3"])
  name                     = "${var.cluster_name}-subnet-${each.key}"
  vpc                      = ibm_is_vpc.main.id
  zone                     = each.key
  resource_group           = data.ibm_resource_group.rg.id
  total_ipv4_address_count = 4096
  depends_on               = [ibm_is_vpc_address_prefix.zone]
}

# Security group: allow all internal + required external ports
resource "ibm_is_security_group" "cluster_sg" {
  name           = "${var.cluster_name}-sg"
  vpc            = ibm_is_vpc.main.id
  resource_group = data.ibm_resource_group.rg.id
}

resource "ibm_is_security_group_rule" "allow_inbound_all_vpc" {
  group     = ibm_is_security_group.cluster_sg.id
  direction = "inbound"
  remote    = "10.240.0.0/14"
}

resource "ibm_is_security_group_rule" "allow_outbound_all" {
  group     = ibm_is_security_group.cluster_sg.id
  direction = "outbound"
  remote    = "0.0.0.0/0"
}

# RTMP/SRT for OTT live ingest
resource "ibm_is_security_group_rule" "rtmp_inbound" {
  group     = ibm_is_security_group.cluster_sg.id
  direction = "inbound"
  remote    = "0.0.0.0/0"
  tcp {
    port_min = 1935
    port_max = 1935
  }
}

resource "ibm_is_security_group_rule" "srt_inbound" {
  group     = ibm_is_security_group.cluster_sg.id
  direction = "inbound"
  remote    = "0.0.0.0/0"
  udp {
    port_min = 9999
    port_max = 9999
  }
}

# WebRTC ICE (R3: must be verified before go-live)
resource "ibm_is_security_group_rule" "webrtc_ice" {
  group     = ibm_is_security_group.cluster_sg.id
  direction = "inbound"
  remote    = "0.0.0.0/0"
  udp {
    port_min = 10000
    port_max = 10004
  }
}

resource "ibm_is_public_gateway" "pgw" {
  for_each       = toset(["eu-de-1", "eu-de-2", "eu-de-3"])
  name           = "${var.cluster_name}-pgw-${each.key}"
  vpc            = ibm_is_vpc.main.id
  zone           = each.key
  resource_group = data.ibm_resource_group.rg.id
}

output "vpc_id"    { value = ibm_is_vpc.main.id }
output "subnet_ids" {
  value = [
    ibm_is_subnet.worker["eu-de-1"].id,
    ibm_is_subnet.worker["eu-de-2"].id,
    ibm_is_subnet.worker["eu-de-3"].id,
  ]
}
output "security_group_id" { value = ibm_is_security_group.cluster_sg.id }
