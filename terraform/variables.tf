# ============================================================
# Input Variables
# ============================================================

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "aws_access_key" {
  description = "AWS Access Key ID (from GitHub Secrets)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "aws_secret_key" {
  description = "AWS Secret Access Key (from GitHub Secrets)"
  type        = string
  sensitive   = true
  default     = ""
}


variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "researchsphere"
}

variable "instance_type" {
  description = "EC2 instance type (t2.micro = 1 GB RAM, t3.micro = 1 GB, t3.small = 2 GB)"
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "Amazon Linux 2023 AMI ID (default: latest for us-east-1). Override per-region as needed."
  type        = string
  default     = ""
}

variable "key_pair_name" {
  description = "Name of an existing EC2 Key Pair for SSH access. Leave empty to skip SSH."
  type        = string
  default     = ""
}

variable "min_instances" {
  description = "Minimum number of EC2 instances in the Auto Scaling Group"
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Maximum number of EC2 instances in the Auto Scaling Group"
  type        = number
  default     = 3
}

variable "desired_instances" {
  description = "Desired number of EC2 instances at steady state"
  type        = number
  default     = 1
}

variable "scale_up_cpu_threshold" {
  description = "CPU utilization percentage that triggers scale-out"
  type        = number
  default     = 70
}

variable "scale_down_cpu_threshold" {
  description = "CPU utilization percentage that triggers scale-in"
  type        = number
  default     = 30
}

variable "docker_image" {
  description = "Docker image URI (e.g. ghcr.io/user/repo:latest)"
  type        = string
}

variable "ghcr_token" {
  description = "GitHub Container Registry PAT for pulling the image"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ghcr_username" {
  description = "GitHub username for GHCR authentication"
  type        = string
  default     = ""
}
