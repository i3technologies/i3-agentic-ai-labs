# ============================================================
# Terraform Variables — i3 Platform IBM Cloud Infrastructure
# ============================================================

variable "ibmcloud_api_key" {
  description = "IBM Cloud API Key. Passed at plan/apply time via -var flag."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "IBM Cloud region for all resources."
  type        = string
  default     = "eu-de"
}

variable "resource_group" {
  description = "IBM Cloud Resource Group name."
  type        = string
  default     = "i3-production"
}

variable "cluster_name" {
  description = "ROKS cluster name."
  type        = string
  default     = "i3-platform"
}

variable "cos_instance_name" {
  description = "IBM Cloud Object Storage instance name."
  type        = string
  default     = "i3-cos-instance"
}

variable "cos_bucket_name" {
  description = "Name of the primary COS bucket for Terraform state."
  type        = string
  default     = "i3-tfstate-077d74db"
}

variable "worker_flavor" {
  description = "CPU worker node flavor (always-on pool)."
  type        = string
  default     = "bx2.4x16"
}

variable "gpu_worker_flavor" {
  description = "GPU burst worker node flavor (scale-to-zero pool)."
  type        = string
  default     = "gx2.8x64"
}

variable "min_workers" {
  description = "Minimum CPU workers (always-on)."
  type        = number
  default     = 3
}

variable "max_workers" {
  description = "Maximum CPU workers (autoscale ceiling)."
  type        = number
  default     = 6
}

variable "kube_version" {
  description = "OpenShift / Kubernetes version for ROKS cluster."
  type        = string
  default     = "4.15_openshift"
}

variable "cos_hmac_access_key" {
  description = "IBM COS HMAC access key ID for pgBackRest backup bucket authentication."
  type        = string
  sensitive   = true
  default     = ""
}

variable "cos_hmac_secret_key" {
  description = "IBM COS HMAC secret access key for pgBackRest backup bucket authentication."
  type        = string
  sensitive   = true
  default     = ""
}

variable "kms_instance_crn" {
  description = "IBM Key Protect (KMS) instance CRN for ROKS envelope encryption. Fill in Phase 2."
  type        = string
  default     = ""
}

variable "kms_crk_id" {
  description = "IBM Key Protect Customer Root Key ID for ROKS cluster encryption. Fill in Phase 2."
  type        = string
  default     = ""
}
