# Use default VPC (account at VPC limit)
data "aws_vpc" "default" {
  default = true
}

# Get default subnets
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Availability Zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Locals for compatibility
locals {
  vpc_id             = data.aws_vpc.default.id
  public_subnet_ids  = slice(data.aws_subnets.default.ids, 0, min(2, length(data.aws_subnets.default.ids)))
  private_subnet_ids = slice(data.aws_subnets.default.ids, 0, min(2, length(data.aws_subnets.default.ids)))
}
