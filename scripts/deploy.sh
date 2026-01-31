#!/bin/bash
set -e

# ShowSpec CAD Bench Deployment Script
# Usage: ./scripts/deploy.sh [init|plan|apply|destroy]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TF_DIR="$PROJECT_ROOT/infrastructure/terraform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for AWS credentials
check_aws_creds() {
    echo -e "${YELLOW}Checking AWS credentials...${NC}"
    if ! aws sts get-caller-identity &>/dev/null; then
        echo -e "${RED}Error: AWS credentials are not valid or not configured.${NC}"
        echo "Please configure AWS credentials with: aws configure"
        exit 1
    fi
    echo -e "${GREEN}AWS credentials valid.${NC}"
    aws sts get-caller-identity
}

# Initialize Terraform
tf_init() {
    echo -e "${YELLOW}Initializing Terraform...${NC}"
    cd "$TF_DIR"
    terraform init
    echo -e "${GREEN}Terraform initialized.${NC}"
}

# Plan infrastructure
tf_plan() {
    echo -e "${YELLOW}Planning infrastructure...${NC}"
    cd "$TF_DIR"
    terraform plan -out=tfplan
    echo -e "${GREEN}Plan complete. Review above and run 'apply' to proceed.${NC}"
}

# Apply infrastructure
tf_apply() {
    echo -e "${YELLOW}Applying infrastructure...${NC}"
    cd "$TF_DIR"

    if [ -f tfplan ]; then
        terraform apply tfplan
    else
        terraform apply -auto-approve
    fi

    echo -e "${GREEN}Infrastructure deployed.${NC}"

    # Show outputs
    echo -e "${YELLOW}Outputs:${NC}"
    terraform output

    # Show ACM validation instructions
    echo ""
    echo -e "${YELLOW}IMPORTANT: Add the following DNS records to Cloudflare for certificate validation:${NC}"
    terraform output -json acm_validation_records
}

# Build and push Docker image
build_and_push() {
    echo -e "${YELLOW}Building and pushing Docker image...${NC}"

    cd "$TF_DIR"
    ECR_URL=$(terraform output -raw ecr_repository_url)
    AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-west-2")

    cd "$PROJECT_ROOT"

    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URL

    # Build image
    docker build -t showspec-cad-bench -f docker/Dockerfile .

    # Tag and push
    docker tag showspec-cad-bench:latest $ECR_URL:latest
    docker push $ECR_URL:latest

    echo -e "${GREEN}Docker image pushed to ECR.${NC}"
}

# Update ECS service
update_service() {
    echo -e "${YELLOW}Updating ECS service...${NC}"

    aws ecs update-service \
        --cluster showspec-cad-bench \
        --service showspec-cad-bench \
        --force-new-deployment \
        --region us-west-2

    echo -e "${GREEN}ECS service update initiated.${NC}"
    echo "Run 'aws ecs wait services-stable --cluster showspec-cad-bench --services showspec-cad-bench --region us-west-2' to wait for deployment."
}

# Add Cloudflare DNS records
setup_dns() {
    echo -e "${YELLOW}Setting up Cloudflare DNS...${NC}"

    CLOUDFLARE_TOKEN="${CLOUDFLARE_API_TOKEN:-fPYyR54sp_o61OS-FOB9u5USnaipa-P0Evtz0CTi}"
    ZONE_ID="771315bdf39b1463bf6f25e7cc1f9024"

    cd "$TF_DIR"
    ALB_DNS=$(terraform output -raw alb_dns_name)

    # Add CNAME for cad.showspec.cc pointing to ALB
    curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
        -H "Authorization: Bearer $CLOUDFLARE_TOKEN" \
        -H "Content-Type: application/json" \
        --data '{
            "type": "CNAME",
            "name": "cad",
            "content": "'"$ALB_DNS"'",
            "ttl": 1,
            "proxied": false
        }'

    echo -e "${GREEN}DNS record created.${NC}"
}

# Destroy infrastructure
tf_destroy() {
    echo -e "${RED}WARNING: This will destroy all infrastructure!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" == "yes" ]; then
        cd "$TF_DIR"
        terraform destroy
    else
        echo "Aborted."
    fi
}

# Main
case "$1" in
    init)
        check_aws_creds
        tf_init
        ;;
    plan)
        check_aws_creds
        tf_plan
        ;;
    apply)
        check_aws_creds
        tf_apply
        ;;
    build)
        check_aws_creds
        build_and_push
        ;;
    deploy)
        check_aws_creds
        build_and_push
        update_service
        ;;
    dns)
        setup_dns
        ;;
    destroy)
        check_aws_creds
        tf_destroy
        ;;
    all)
        check_aws_creds
        tf_init
        tf_plan
        tf_apply
        build_and_push
        update_service
        setup_dns
        ;;
    *)
        echo "Usage: $0 {init|plan|apply|build|deploy|dns|destroy|all}"
        echo ""
        echo "Commands:"
        echo "  init    - Initialize Terraform"
        echo "  plan    - Plan infrastructure changes"
        echo "  apply   - Apply infrastructure changes"
        echo "  build   - Build and push Docker image to ECR"
        echo "  deploy  - Build image and update ECS service"
        echo "  dns     - Set up Cloudflare DNS records"
        echo "  destroy - Destroy all infrastructure"
        echo "  all     - Run full deployment (init, plan, apply, build, deploy, dns)"
        exit 1
        ;;
esac
