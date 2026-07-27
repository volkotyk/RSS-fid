output "cover_image_url" {
  description = "HTTPS URL that serves the podcast cover art via Lambda redirect"
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/cover"
}

output "rss_feed_url" {
  description = "Public RSS feed URL — subscribe your podcast player to this"
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/feed"
}

output "s3_bucket_name" {
  description = "S3 bucket name — upload audio files here"
  value       = aws_s3_bucket.podcast_audio.bucket
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.rss_generator.function_name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group (7-day retention)"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}
