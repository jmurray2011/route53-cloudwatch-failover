terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Environment = "prod"
      ManagedBy   = "Terraform"
    }
  }
}

module "route53_failover" {
  source = "../../modules/route53-failover-lambda"

  environment          = "prod"
  function_name        = var.function_name
  hosted_zone_id       = var.hosted_zone_id
  record_set_name      = var.record_set_name
  primary_identifier   = var.primary_identifier
  secondary_identifier = var.secondary_identifier
  record_type          = var.record_type
  lambda_timeout       = var.lambda_timeout
  lambda_memory_size   = var.lambda_memory_size
  log_retention_days   = var.log_retention_days

  tags = var.tags
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile name"
  type        = string
  default     = null
}

variable "function_name" {
  description = "Lambda function name"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID"
  type        = string
}

variable "record_set_name" {
  description = "DNS record set name (with trailing dot)"
  type        = string
}

variable "primary_identifier" {
  description = "SetIdentifier for the primary weighted record"
  type        = string
}

variable "secondary_identifier" {
  description = "SetIdentifier for the secondary weighted record"
  type        = string
}

variable "record_type" {
  description = "DNS record type"
  type        = string
  default     = "A"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 60
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 128
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

# Outputs
output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.route53_failover.lambda_function_arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.route53_failover.lambda_function_name
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic - use this in CloudWatch alarm actions"
  value       = module.route53_failover.sns_topic_arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = module.route53_failover.cloudwatch_log_group_name
}
