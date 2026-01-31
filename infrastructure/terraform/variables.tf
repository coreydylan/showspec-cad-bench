variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.50.0.0/16"
}

variable "domain_name" {
  description = "Domain name for the service"
  type        = string
  default     = "cad.showspec.cc"
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for showspec.cc"
  type        = string
  default     = "771315bdf39b1463bf6f25e7cc1f9024"
}

variable "ecs_cpu" {
  description = "ECS task CPU units"
  type        = number
  default     = 1024  # 1 vCPU
}

variable "ecs_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 2048  # 2 GB
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}
