# Security Group for ALB
resource "aws_security_group" "alb" {
  name        = "showspec-cad-bench-alb"
  description = "Security group for ALB"
  vpc_id      = local.vpc_id

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "showspec-cad-bench-alb"
  }
}

# Application Load Balancer
resource "aws_lb" "cad_bench" {
  name               = "showspec-cad-bench"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = local.public_subnet_ids

  enable_deletion_protection = false

  tags = {
    Name = "showspec-cad-bench"
  }
}

# Target Group
resource "aws_lb_target_group" "cad_bench" {
  name        = "showspec-cad-bench"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = local.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 10
    unhealthy_threshold = 3
  }

  tags = {
    Name = "showspec-cad-bench"
  }
}

# ACM Certificate
resource "aws_acm_certificate" "cad_bench" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "showspec-cad-bench"
  }
}

# HTTPS Listener
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.cad_bench.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.cad_bench.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.cad_bench.arn
  }

  depends_on = [aws_acm_certificate_validation.cad_bench]
}

# HTTP Listener (redirect to HTTPS)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.cad_bench.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# ACM Certificate Validation (will need DNS records added to Cloudflare)
resource "aws_acm_certificate_validation" "cad_bench" {
  certificate_arn = aws_acm_certificate.cad_bench.arn

  # This will wait for DNS validation
  # You'll need to add the DNS records to Cloudflare manually or via API
  timeouts {
    create = "30m"
  }
}
