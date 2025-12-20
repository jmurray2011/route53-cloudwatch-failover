# Route 53 Failover Lambda - Terraform Infrastructure

This directory contains Terraform configuration for deploying the Route 53 weighted routing failover Lambda function.

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform >= 1.0
3. S3 bucket for state storage (with versioning and encryption enabled)

## Directory Structure

```
terraform/
├── modules/
│   └── route53-failover-lambda/   # Reusable module
│       ├── main.tf                # Module configuration
│       ├── variables.tf           # Input variables
│       ├── outputs.tf             # Output values
│       ├── iam.tf                 # IAM role and policies
│       ├── lambda.tf              # Lambda function and logs
│       └── sns.tf                 # SNS topic and subscription
└── environments/
    └── prod/                      # Production environment
        ├── main.tf                # Module invocation
        ├── backend.tf             # S3 state backend
        └── terraform.tfvars       # Environment values
```

## Resources Created

The module creates the following AWS resources:

- **Lambda Function** - The failover handler with environment variables
- **IAM Role** - Execution role for Lambda
- **IAM Policies** - Least-privilege policies for Route 53 and CloudWatch Logs
- **SNS Topic** - Receives CloudWatch alarm notifications
- **SNS Subscription** - Triggers Lambda from SNS
- **Lambda Permission** - Allows SNS to invoke Lambda
- **CloudWatch Log Group** - Stores Lambda execution logs

## Quick Start

### 1. Configure State Backend

Edit `terraform/environments/prod/backend.tf` and update the S3 bucket name:

```hcl
terraform {
  backend "s3" {
    bucket       = "your-terraform-state-bucket"  # Update this
    key          = "route53-failover/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
```

### 2. Configure Environment Variables

Edit `terraform/environments/prod/terraform.tfvars`:

```hcl
hosted_zone_id       = "Z1234567890ABC"  # Your Route 53 hosted zone ID
record_set_name      = "example.com."    # Your DNS record name
primary_identifier   = "primary"         # Your primary SetIdentifier
secondary_identifier = "secondary"       # Your secondary SetIdentifier
```

### 3. Deploy

```bash
cd terraform/environments/prod

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply changes
terraform apply
```

## Outputs

After deployment, Terraform outputs important values:

| Output | Description |
|--------|-------------|
| `lambda_function_arn` | ARN of the Lambda function |
| `lambda_function_name` | Name of the Lambda function |
| `sns_topic_arn` | ARN of the SNS topic (use in CloudWatch alarms) |
| `cloudwatch_log_group_name` | Name of the log group for debugging |

## GitHub Actions Integration

The repository includes a Terraform workflow (`.github/workflows/terraform.yml`) that:

- Runs `terraform plan` on pull requests to `terraform/**` files
- Comments the plan on the PR for review
- Runs `terraform apply` on push to main (requires `prod` environment approval)

### Required GitHub Configuration

1. Create a GitHub environment named `prod`
2. Add required reviewers (optional)
3. Add the following secrets:
   - `AWS_ROLE_ARN` - IAM role ARN for GitHub Actions (OIDC)
4. Add the following variables:
   - `AWS_REGION` - AWS region (e.g., `us-east-1`)

### AWS OIDC Setup

For secure GitHub Actions authentication, set up OIDC:

1. Create an IAM OIDC provider for `token.actions.githubusercontent.com`
2. Create an IAM role with trust policy for your repository
3. Attach permissions for S3 (state), Lambda, IAM, SNS, CloudWatch Logs, Route 53

Example trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/route53-weighted-routing:*"
        }
      }
    }
  ]
}
```

## Module Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `environment` | Environment name | (required) |
| `function_name` | Lambda function name | (required) |
| `hosted_zone_id` | Route 53 hosted zone ID | (required) |
| `record_set_name` | DNS record name | (required) |
| `primary_identifier` | Primary SetIdentifier | (required) |
| `secondary_identifier` | Secondary SetIdentifier | (required) |
| `record_type` | DNS record type (A, AAAA, CNAME) | `"A"` |
| `lambda_timeout` | Lambda timeout in seconds | `60` |
| `lambda_memory_size` | Lambda memory in MB | `128` |
| `log_retention_days` | Log retention in days | `14` |
| `tags` | Additional resource tags | `{}` |

## Connecting CloudWatch Alarms

After deployment, use the `sns_topic_arn` output to configure CloudWatch alarms:

```bash
# Get the SNS topic ARN
cd terraform/environments/prod
terraform output sns_topic_arn
```

Then configure your CloudWatch alarm to send notifications to this SNS topic. When the alarm state changes, the Lambda function will automatically adjust DNS weights.
