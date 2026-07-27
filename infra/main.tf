terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  bucket_name = "${var.project_name}-audio-${data.aws_caller_identity.current.account_id}"
}

# ─────────────────────────────────────────────
# S3 — private audio file storage
# ─────────────────────────────────────────────

resource "aws_s3_bucket" "podcast_audio" {
  bucket        = local.bucket_name
  force_destroy = var.allow_destroy_media_deletion
  tags          = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "podcast_audio" {
  bucket                  = aws_s3_bucket.podcast_audio.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "podcast_audio" {
  bucket = aws_s3_bucket.podcast_audio.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = false
  }
}

resource "aws_s3_bucket_versioning" "podcast_audio" {
  bucket = aws_s3_bucket.podcast_audio.id
  versioning_configuration { status = "Disabled" }
}

# ─────────────────────────────────────────────
# CloudWatch — 7-day retention (Free Tier safe)
# ─────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-rss-generator"
  retention_in_days = 7
  tags              = local.common_tags
}

# ─────────────────────────────────────────────
# API Gateway HTTP API — created before Lambda so its
# invoke_url is available as the PODCAST_LINK env var
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_api" "rss" {
  name          = "${var.project_name}-rss-api"
  protocol_type = "HTTP"
  tags          = local.common_tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.rss.id
  name        = "$default"
  auto_deploy = true
  tags        = local.common_tags
}

# ─────────────────────────────────────────────
# Lambda — package and function
# ─────────────────────────────────────────────

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "rss_generator" {
  function_name    = "${var.project_name}-rss-generator"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 128
  timeout          = 29

  environment {
    variables = {
      BUCKET_NAME         = aws_s3_bucket.podcast_audio.bucket
      PODCAST_TITLE       = var.podcast_title
      PODCAST_DESCRIPTION = var.podcast_description
      PODCAST_AUTHOR      = var.podcast_author
      # Stage invoke_url has no dependency on Lambda — no cycle.
      # trimslash removes the trailing "/" the $default stage appends.
      PODCAST_LINK = trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")
      # Cover art is served by the same Lambda via GET /cover
      PODCAST_IMAGE_URL   = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/cover"
      PODCAST_LANGUAGE    = var.podcast_language
      PODCAST_CATEGORY    = var.podcast_category
      PODCAST_OWNER_NAME  = var.podcast_owner_name
      PODCAST_OWNER_EMAIL = var.podcast_owner_email
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy_attachment.lambda_logs,
  ]

  tags = local.common_tags
}

# ─────────────────────────────────────────────
# API Gateway — integration, routes, permission
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.rss.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.rss_generator.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

resource "aws_apigatewayv2_route" "feed" {
  api_id    = aws_apigatewayv2_api.rss.id
  route_key = "GET /feed"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Serves podcast cover art via a short-lived S3 pre-signed URL redirect.
resource "aws_apigatewayv2_route" "cover" {
  api_id    = aws_apigatewayv2_api.rss.id
  route_key = "GET /cover"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Serves audio files via short-lived S3 pre-signed URL redirects.
# {proxy+} captures the full key path including any slashes.
resource "aws_apigatewayv2_route" "audio" {
  api_id    = aws_apigatewayv2_api.rss.id
  route_key = "GET /audio/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Serves episode artwork via short-lived S3 pre-signed URL redirects.
resource "aws_apigatewayv2_route" "images" {
  api_id    = aws_apigatewayv2_api.rss.id
  route_key = "GET /images/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rss_generator.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rss.execution_arn}/*/*"
}
