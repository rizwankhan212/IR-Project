# ============================================================
# Terraform Configuration for ResearchSphere IR Project
# Deploys on AWS EC2 with Auto Scaling and Load Balancing
# ============================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── Provider ─────────────────────────────────────────────────
provider "aws" {
  region     = trimspace(var.aws_region)
  access_key = var.aws_access_key != "" ? trimspace(var.aws_access_key) : null
  secret_key = var.aws_secret_key != "" ? trimspace(var.aws_secret_key) : null
}

