# ============================================================
# Outputs
# ============================================================

output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer"
  value       = aws_lb.app.dns_name
}

output "alb_url" {
  description = "Full URL to access ResearchSphere"
  value       = "http://${aws_lb.app.dns_name}"
}

output "application_url" {
  description = "Application Live URL (Open in browser after deployment)"
  value       = "http://${aws_lb.app.dns_name}"
}

output "health_check_url" {
  description = "Streamlit Health Check endpoint"
  value       = "http://${aws_lb.app.dns_name}/_stcore/health"
}

output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.app.name
}

output "vpc_id" {
  description = "ID of the created VPC"
  value       = aws_vpc.main.id
}

output "ami_used" {
  description = "AMI ID used for the launch template"
  value       = local.ami_id
}
