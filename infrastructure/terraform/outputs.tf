output "vpc_id" {
  description = "VPC ID"
  value       = local.vpc_id
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.cad_bench.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.cad_bench.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.cad_bench.name
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.cad_bench.dns_name
}

output "alb_zone_id" {
  description = "ALB zone ID for DNS alias"
  value       = aws_lb.cad_bench.zone_id
}

output "s3_bucket_name" {
  description = "S3 bucket name for templates"
  value       = aws_s3_bucket.templates.id
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.cad_bench.name
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "https://${var.domain_name}"
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN"
  value       = aws_acm_certificate.cad_bench.arn
}

output "acm_validation_records" {
  description = "ACM certificate DNS validation records (add to Cloudflare)"
  value = {
    for dvo in aws_acm_certificate.cad_bench.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}
