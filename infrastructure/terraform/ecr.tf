# ECR Repository
resource "aws_ecr_repository" "cad_bench" {
  name                 = "showspec-cad-bench"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "showspec-cad-bench"
  }
}

# ECR Lifecycle Policy - Keep last 10 images
resource "aws_ecr_lifecycle_policy" "cad_bench" {
  repository = aws_ecr_repository.cad_bench.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
