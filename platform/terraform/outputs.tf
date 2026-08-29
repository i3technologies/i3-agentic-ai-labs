# ============================================================
# Terraform Outputs — i3 Platform IBM Cloud Infrastructure
# ============================================================

output "cluster_id" {
  description = "ROKS cluster ID (used to configure kubectl / oc context)."
  value       = module.roks.cluster_id
}

output "cluster_ingress_hostname" {
  description = "Default OpenShift Ingress subdomain (*.apps.<cluster>.<zone>.containers.appdomain.cloud)."
  value       = module.roks.ingress_hostname
}

output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "vpc_subnet_ids" {
  description = "Subnet IDs used by ROKS worker nodes."
  value       = module.vpc.subnet_ids
}

output "cos_instance_crn" {
  description = "COS service instance CRN (used by ROKS for etcd backup)."
  value       = module.cos.instance_crn
}

output "cos_standard_instance_crn" {
  description = "COS standard instance CRN."
  value       = module.cos.standard_instance_crn
}

output "cos_tfstate_bucket" {
  description = "COS bucket holding Terraform remote state."
  value       = module.cos.tfstate_bucket_name
}

output "iam_terraform_service_id" {
  description = "Service ID used by Terraform for IBM Cloud operations."
  value       = module.iam.terraform_service_id
  sensitive   = false
}

output "worker_pool_cpu_name" {
  description = "Name of the CPU always-on worker pool."
  value       = module.roks.cpu_pool_name
}

output "worker_pool_gpu_name" {
  description = "Name of the GPU burst worker pool (scale-to-zero)."
  value       = module.roks.gpu_pool_name
}
