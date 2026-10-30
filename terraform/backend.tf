# ============================================================
# Terraform Backend — S3 Remote State (optional)
# ============================================================
# Uncomment the block below if you want to store Terraform
# state remotely in S3 (recommended for team workflows).
#
# Before using this, create the S3 bucket and DynamoDB table:
#   aws s3 mb s3://researchsphere-tf-state
#   aws dynamodb create-table \
#     --table-name researchsphere-tf-lock \
#     --attribute-definitions AttributeName=LockID,AttributeType=S \
#     --key-schema AttributeName=LockID,KeyType=HASH \
#     --billing-mode PAY_PER_REQUEST

# terraform {
#   backend "s3" {
#     bucket         = "researchsphere-tf-state"
#     key            = "infra/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "researchsphere-tf-lock"
#     encrypt        = true
#   }
# }
