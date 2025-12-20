data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.root}/../../../lambda_function.py"
  output_path = "${path.module}/files/lambda_function.zip"
}

resource "aws_lambda_function" "failover" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = var.function_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.10"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  environment {
    variables = {
      HOSTED_ZONE_ID       = var.hosted_zone_id
      RECORD_SET_NAME      = var.record_set_name
      PRIMARY_IDENTIFIER   = var.primary_identifier
      SECONDARY_IDENTIFIER = var.secondary_identifier
      RECORD_TYPE          = var.record_type
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy_attachment.cloudwatch_attach,
    aws_iam_role_policy_attachment.route53_attach,
  ]

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}
