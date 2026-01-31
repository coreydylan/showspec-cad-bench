# ShowSpec CAD Bench - Deployment Guide

## Prerequisites

1. **AWS CLI** configured with valid credentials for account `790856971687`
2. **Terraform** >= 1.0 installed
3. **Docker** installed for building images
4. **Cloudflare API Token** (already in CLAUDE.md)

## Quick Start

```bash
# 1. Configure AWS credentials
aws configure
# Enter access key, secret key, region: us-west-2

# 2. Run full deployment
./scripts/deploy.sh all
```

## Step-by-Step Deployment

### 1. Initialize Terraform

```bash
cd infrastructure/terraform
terraform init
```

### 2. Plan and Apply Infrastructure

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

This creates:
- VPC with public/private subnets
- ECR repository
- ECS cluster and service
- Application Load Balancer
- S3 bucket for templates
- ACM certificate for HTTPS

### 3. Add ACM Certificate Validation DNS Records

After `terraform apply`, you'll see output like:

```
acm_validation_records = {
  "cad.showspec.cc" = {
    name  = "_abc123.cad.showspec.cc."
    type  = "CNAME"
    value = "_xyz789.acm-validations.aws."
  }
}
```

Add this CNAME record to Cloudflare:
```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/771315bdf39b1463bf6f25e7cc1f9024/dns_records" \
  -H "Authorization: Bearer fPYyR54sp_o61OS-FOB9u5USnaipa-P0Evtz0CTi" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "CNAME",
    "name": "_abc123.cad",
    "content": "_xyz789.acm-validations.aws.",
    "ttl": 1,
    "proxied": false
  }'
```

### 4. Build and Push Docker Image

```bash
# Get ECR URL from Terraform output
ECR_URL=$(terraform output -raw ecr_repository_url)

# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin $ECR_URL

# Build and push
cd ../..
docker build -t showspec-cad-bench -f docker/Dockerfile .
docker tag showspec-cad-bench:latest $ECR_URL:latest
docker push $ECR_URL:latest
```

### 5. Deploy to ECS

The ECS service will automatically pull the image. Force a new deployment:

```bash
aws ecs update-service \
  --cluster showspec-cad-bench \
  --service showspec-cad-bench \
  --force-new-deployment \
  --region us-west-2
```

### 6. Add DNS Record for cad.showspec.cc

```bash
# Get ALB DNS name
ALB_DNS=$(terraform output -raw alb_dns_name)

# Add CNAME to Cloudflare
curl -X POST "https://api.cloudflare.com/client/v4/zones/771315bdf39b1463bf6f25e7cc1f9024/dns_records" \
  -H "Authorization: Bearer fPYyR54sp_o61OS-FOB9u5USnaipa-P0Evtz0CTi" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "CNAME",
    "name": "cad",
    "content": "'"$ALB_DNS"'",
    "ttl": 1,
    "proxied": false
  }'
```

### 7. Verify Deployment

```bash
# Check health endpoint
curl https://cad.showspec.cc/health

# Test calculation
curl -X POST https://cad.showspec.cc/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "component_type": "wall_straight",
    "dimensions": {"width": 120, "height": 96, "depth": 0.75}
  }'
```

## Local Development

```bash
cd docker
docker-compose up --build

# Test locally
curl http://localhost:8000/health
curl -X POST http://localhost:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{"component_type":"wall_straight","dimensions":{"width":120,"height":96,"depth":0.75}}'
```

## Resource Summary

| Resource | Name/ID |
|----------|---------|
| AWS Account | 790856971687 |
| AWS Region | us-west-2 |
| VPC CIDR | 10.50.0.0/16 |
| ECS Cluster | showspec-cad-bench |
| ECR Repo | showspec-cad-bench |
| S3 Bucket | showspec-cad-bench-templates-790856971687 |
| Domain | cad.showspec.cc |
| Cloudflare Zone | 771315bdf39b1463bf6f25e7cc1f9024 |

## Troubleshooting

### ECS Task Fails to Start

Check CloudWatch logs:
```bash
aws logs tail /ecs/showspec-cad-bench --follow --region us-west-2
```

### ACM Certificate Not Validating

Verify DNS record is correctly added to Cloudflare:
```bash
curl -s "https://api.cloudflare.com/client/v4/zones/771315bdf39b1463bf6f25e7cc1f9024/dns_records" \
  -H "Authorization: Bearer fPYyR54sp_o61OS-FOB9u5USnaipa-P0Evtz0CTi" | jq '.result[] | select(.name | contains("cad"))'
```

### Health Check Failing

The container needs Xvfb running for FreeCAD. Check the entrypoint script is properly starting the virtual display.
