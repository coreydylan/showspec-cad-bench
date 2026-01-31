# ShowSpec CAD Bench - Deployment Status

**Date:** 2026-01-30
**Status:** 98% Complete - Ready for Image Push

---

## ✅ Completed Infrastructure

### AWS Resources (All Deployed)
| Resource | ID/Name | Status |
|----------|---------|--------|
| **VPC** | vpc-0ca908490213c58bc (default) | ✅ Active |
| **ECR Repository** | showspec-cad-bench | ✅ Created |
| **ECS Cluster** | showspec-cad-bench | ✅ Running |
| **ECS Service** | showspec-cad-bench | ✅ Deployed (waiting for image) |
| **Application Load Balancer** | showspec-cad-bench-1012080224.us-west-2.elb.amazonaws.com | ✅ Active |
| **ACM Certificate** | arn:aws:acm:us-west-2:790856971687:certificate/939b24a2-37e0-40d2-ab2d-09ea44dc64d2 | ✅ Validated |
| **S3 Bucket** | showspec-cad-bench-templates-790856971687 | ✅ Created |
| **CloudWatch Logs** | /ecs/showspec-cad-bench | ✅ Active |

### DNS Records (Cloudflare)
- ✅ `_927863233341e3dd22c3048d94ea50ee.cad.showspec.cc` → ACM validation
- ✅ `cad.showspec.cc` → `showspec-cad-bench-1012080224.us-west-2.elb.amazonaws.com`

### Application Code
- ✅ FastAPI application (complete)
- ✅ Docker image built (3.37GB with FreeCAD)
- ✅ Templates & materials library
- ✅ Tests configured

---

## 🔧 Remaining Task

### Push Docker Image to ECR

**Issue:** macOS Keychain blocking Docker login to ECR

**Solution 1: Manual Push (Recommended)**
```bash
# Unlock your Mac keychain
security unlock-keychain ~/Library/Keychains/login.keychain-db

# Login to ECR
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  790856971687.dkr.ecr.us-west-2.amazonaws.com

# Push the image
docker push 790856971687.dkr.ecr.us-west-2.amazonaws.com/showspec-cad-bench:latest

# Force ECS to deploy the new image
aws ecs update-service \
  --cluster showspec-cad-bench \
  --service showspec-cad-bench \
  --force-new-deployment \
  --region us-west-2
```

**Solution 2: GitHub Actions**
The repository includes a GitHub Actions workflow (`.github/workflows/deploy.yml`) that will automatically build and deploy on push to main:

```bash
git add .
git commit -m "Deploy ShowSpec CAD Bench

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
git push origin main
```

---

## 🧪 Testing

Once the image is deployed:

```bash
# Check health endpoint
curl https://cad.showspec.cc/health

# Expected response:
# {
#   "status": "healthy",
#   "freecad_version": "...",
#   "woodworking_wb_version": "1.0",
#   "templates_loaded": 1,
#   "uptime_seconds": ...
# }

# Test calculate endpoint
curl -X POST https://cad.showspec.cc/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "component_type": "wall_straight",
    "dimensions": {"width": 120, "height": 96, "depth": 0.75},
    "surfaces": {"front": "laminate", "back": "raw"}
  }'
```

---

## 📊 Resource Summary

**Total Files Created:** 40+
- API code: 15 files
- Infrastructure: 10 Terraform files
- Docker: 3 files
- Templates & Materials: 4 files
- Tests: 3 files
- Documentation: 5 files

**AWS Costs (Estimated):**
- ECS Fargate (1 task, 1 vCPU, 2GB): ~$30/month
- ALB: ~$16/month
- ECR storage: ~$1/month
- Data transfer: Variable
- **Total: ~$50/month**

**Deployment Time:**
- Infrastructure setup: ~30 minutes
- Docker build: ~10 minutes
- **Total: ~40 minutes**

---

## 🎯 Next Steps

1. **Push Docker image** (see above)
2. **Wait 2-3 minutes** for ECS to deploy
3. **Test the API** at https://cad.showspec.cc/health
4. **Integrate with ShowSpec frontend** using the example in `README.md`

---

## 🔗 Important URLs

- API Endpoint: https://cad.showspec.cc
- API Docs: https://cad.showspec.cc/docs
- ALB: http://showspec-cad-bench-1012080224.us-west-2.elb.amazonaws.com
- ECR: 790856971687.dkr.ecr.us-west-2.amazonaws.com/showspec-cad-bench
- CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logsV2:log-groups/log-group/$252Fecs$252Fshowspec-cad-bench

---

## 📝 Notes

- Using default VPC due to account VPC limit (5/5)
- FreeCAD runs in headless mode with Xvfb virtual display
- Templates stored in S3 for production, local filesystem for development
- CORS configured for showspec.cc and localhost:5173
