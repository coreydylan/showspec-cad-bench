# ECS Cluster
resource "aws_ecs_cluster" "cad_bench" {
  name = "showspec-cad-bench"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "showspec-cad-bench"
  }
}

# ECS Cluster Capacity Providers
resource "aws_ecs_cluster_capacity_providers" "cad_bench" {
  cluster_name = aws_ecs_cluster.cad_bench.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "cad_bench" {
  name              = "/ecs/showspec-cad-bench"
  retention_in_days = 30

  tags = {
    Name = "showspec-cad-bench"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "cad_bench" {
  family                   = "showspec-cad-bench"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "cad-bench"
      image = "${aws_ecr_repository.cad_bench.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "LOG_LEVEL"
          value = "INFO"
        },
        {
          name  = "S3_TEMPLATE_BUCKET"
          value = aws_s3_bucket.templates.id
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.cad_bench.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 60
      }

      essential = true
    }
  ])

  tags = {
    Name = "showspec-cad-bench"
  }
}

# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "showspec-cad-bench-ecs-tasks"
  description = "Security group for ECS tasks"
  vpc_id      = local.vpc_id

  ingress {
    description     = "Allow traffic from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "showspec-cad-bench-ecs-tasks"
  }
}

# ECS Service
resource "aws_ecs_service" "cad_bench" {
  name            = "showspec-cad-bench"
  cluster         = aws_ecs_cluster.cad_bench.id
  task_definition = aws_ecs_task_definition.cad_bench.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.cad_bench.arn
    container_name   = "cad-bench"
    container_port   = 8000
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100
  enable_execute_command             = true

  depends_on = [
    aws_lb_listener.https
  ]

  tags = {
    Name = "showspec-cad-bench"
  }
}
