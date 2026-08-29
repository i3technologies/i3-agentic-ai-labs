terraform {
  required_version = ">= 1.7"
  required_providers {
    ibm = {
      source  = "ibm-cloud/ibm"
      version = "~> 1.89"
    }
  }

  backend "s3" {
    bucket                     = "i3-tfstate-077d74db"
    key                        = "terraform.tfstate"
    region                     = "eu-de"
    endpoints                  = { s3 = "https://s3.eu-de.cloud-object-storage.appdomain.cloud" }
    encrypt                    = true
    skip_credentials_validation = true
    skip_metadata_api_check    = true
    skip_region_validation     = true
    skip_requesting_account_id = true
    use_path_style             = true
    # access_key and secret_key passed via -backend-config at init time
  }
}

provider "ibm" {
  ibmcloud_api_key    = var.ibmcloud_api_key
  region              = var.region
  # iaas_classic credentials not needed for VPC-gen2 + COS
}

locals {
  region         = "eu-de"
  cluster_name   = "i3-platform"
  resource_group = "i3-production"
}

module "vpc" {
  source         = "./modules/vpc"
  region         = local.region
  resource_group = local.resource_group
  cluster_name   = local.cluster_name
}

module "cos" {
  source         = "./modules/cos"
  region         = local.region
  resource_group = local.resource_group
  cos_instance_name = var.cos_instance_name
  cos_bucket_name   = var.cos_bucket_name
}

module "iam" {
  source            = "./modules/iam"
  resource_group    = local.resource_group
  cos_instance_crn  = module.cos.instance_crn
}

module "roks" {
  source             = "./modules/roks"
  region             = local.region
  resource_group     = local.resource_group
  cluster_name       = local.cluster_name
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.subnet_ids
  worker_flavor      = var.worker_flavor
  gpu_worker_flavor  = var.gpu_worker_flavor
  min_workers        = var.min_workers
  max_workers        = var.max_workers
  cos_instance_crn   = module.cos.standard_instance_crn
}
