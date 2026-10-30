# ============================================================
# Terraform Backend — S3 Remote State
# ============================================================
# Uses S3 for persistent state storage across GitHub Actions runs.
# Bucket and region are dynamically injected via -backend-config in deploy.yml.

terraform {
  backend "s3" {}
}
