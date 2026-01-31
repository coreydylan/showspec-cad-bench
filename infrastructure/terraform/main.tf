terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration - uncomment for production with S3 state
  # backend "s3" {
  #   bucket = "showspec-terraform-state"
  #   key    = "cad-bench/terraform.tfstate"
  #   region = "us-west-2"
  # }

  # Using local backend for initial setup
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "showspec-cad-bench"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for current region
data "aws_region" "current" {}
