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
  name           = "${var.cluster_name}-vpc"
  resource_group = data.ibm_resource_group.rg.id

  tags = [
    "platform:i3",
    "env:production",
    "region:${var.region}",
  ]
}

resource "ibm_is_subnet" "zone1" {
  name                     = "${var.cluster_name}-subnet-1"
  vpc                      = ibm_is_vpc.main.id
  zone                     = "${var.region}-1"
  resource_group           = data.ibm_resource_group.rg.id
  total_ipv4_address_count = 256
}

resource "ibm_is_subnet" "zone2" {
  name                     = "${var.cluster_name}-subnet-2"
  vpc                      = ibm_is_vpc.main.id
  zone                     = "${var.region}-2"
  resource_group           = data.ibm_resource_group.rg.id
  total_ipv4_address_count = 256
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
  remote    = ibm_is_vpc.main.id
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

output "vpc_id"    { value = ibm_is_vpc.main.id }
output "subnet_ids" {
  value = [ibm_is_subnet.zone1.id, ibm_is_subnet.zone2.id]
}
output "security_group_id" { value = ibm_is_security_group.cluster_sg.id }
