# AWS Route 53 CloudWatch Failover

Automated DNS failover for AWS Route 53 using weighted routing policies. A Lambda function triggered by CloudWatch alarms adjusts DNS record weights to route traffic between primary and secondary resources based on health status.

## Features

- **Multi-Record Type Support**: Works with ALIAS, A, AAAA, and CNAME records
- **Dynamic DNS Weight Adjustment**: Automatically reroutes traffic based on alarm state
- **Terraform Deployment**: Infrastructure as Code for repeatable deployments
- **Comprehensive Logging**: Structured logging for debugging
- **Robust Error Handling**: Validates configuration and handles API errors gracefully
- **Well Tested**: Unit test suite with 80%+ code coverage

## Prerequisites

- AWS account with Route53, Lambda, and CloudWatch access
- Terraform >= 1.0 (for IaC deployment)
- A Route53 hosted zone with weighted routing records configured:
  - Primary and secondary resources with unique SetIdentifiers
  - Initial weights (e.g., primary=1, secondary=0)

## Deployment

### Using Terraform

1. Create a `terraform.tfvars` file in `terraform/environments/prod/`:
```hcl
aws_region           = "us-east-1"
function_name        = "route53-failover-prod"
hosted_zone_id       = "YOUR_HOSTED_ZONE_ID"
record_set_name      = "example.com."
primary_identifier   = "primary"
secondary_identifier = "secondary"
record_type          = "A"  # or CNAME, AAAA, etc.
```

2. Deploy:
```bash
cd terraform/environments/prod
export AWS_PROFILE=your-profile
terraform init
terraform apply
```

3. Connect the SNS topic (from Terraform output) to your CloudWatch alarms.

### Manual Deployment

1. Create a Lambda function with Python 3.10+ runtime
2. Set environment variables:
   - `HOSTED_ZONE_ID`: Route53 hosted zone ID
   - `RECORD_SET_NAME`: DNS record name (with trailing dot)
   - `PRIMARY_IDENTIFIER`: SetIdentifier for primary record
   - `SECONDARY_IDENTIFIER`: SetIdentifier for secondary record
   - `RECORD_TYPE`: Record type (A, AAAA, CNAME)
3. Attach IAM policy with `route53:ListResourceRecordSets` and `route53:ChangeResourceRecordSets`
4. Subscribe to SNS topic triggered by CloudWatch alarms

## Usage

The Lambda responds to CloudWatch alarm state changes via SNS:

- **ALARM**: Routes traffic to secondary (primary weight=0, secondary weight=1)
- **OK**: Routes traffic to primary (primary weight=1, secondary weight=0)
- **INSUFFICIENT_DATA**: No action taken

## Development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests
make test

# Run linting
make lint
```

## License

MIT
