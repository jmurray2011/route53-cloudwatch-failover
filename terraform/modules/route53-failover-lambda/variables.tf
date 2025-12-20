variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "function_name" {
  description = "Name of the Lambda function"
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
  description = "DNS record type (A, AAAA, CNAME)"
  type        = string
  default     = "A"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 60
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 128
}

variable "log_retention_days" {
  description = "CloudWatch log group retention in days"
  type        = number
  default     = 14
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
