# ============================================================
# Launch Template + Auto Scaling Group
# ============================================================

# User-data script: installs Docker, pulls image, runs container
locals {
  ami_id = var.ami_id != "" ? var.ami_id : data.aws_ami.amazon_linux.id

  # Docker repository names MUST be lowercase
  docker_image_normalized = lower(trimspace(var.docker_image))

  user_data = <<-USERDATA
    #!/bin/bash
    set -euxo pipefail

    # ── Create 2GB swap space to prevent OOM on t3.micro ───
    if ! swapon --show | grep -q "/swapfile"; then
      dd if=/dev/zero of=/swapfile bs=128M count=16
      chmod 600 /swapfile
      mkswap /swapfile
      swapon /swapfile
      echo "/swapfile swap swap defaults 0 0" >> /etc/fstab
    fi

    # ── System updates ──────────────────────────────────────
    dnf update -y
    dnf install -y docker curl
    systemctl enable docker
    systemctl start docker

    # ── GHCR login (if credentials provided) ────────────────
    %{if var.ghcr_username != "" && var.ghcr_token != ""}
    echo "${var.ghcr_token}" | docker login ghcr.io -u "${var.ghcr_username}" --password-stdin || true
    %{endif}

    # ── Pull and run the application container ──────────────
    docker pull ${local.docker_image_normalized}

    docker run -d \
      --name researchsphere \
      --restart always \
      -p 8501:8501 \
      ${local.docker_image_normalized}

    echo "ResearchSphere container started successfully"
  USERDATA
}

resource "aws_launch_template" "app" {
  name_prefix   = "${var.project_name}-lt-"
  image_id      = local.ami_id
  instance_type = var.instance_type
  key_name      = var.key_pair_name != "" ? var.key_pair_name : null

  vpc_security_group_ids = [aws_security_group.ec2.id]

  user_data = base64encode(local.user_data)

  # Enable detailed monitoring for auto-scaling decisions
  monitoring {
    enabled = true
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name    = "${var.project_name}-instance"
      Project = var.project_name
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ── Auto Scaling Group ─────────────────────────────────────
resource "aws_autoscaling_group" "app" {
  name                = "${var.project_name}-asg"
  min_size            = var.min_instances
  max_size            = var.max_instances
  desired_capacity    = var.desired_instances
  vpc_zone_identifier = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  target_group_arns   = [aws_lb_target_group.app.arn]

  # Health checks via ALB
  health_check_type         = "ELB"
  health_check_grace_period = 180

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  # Rolling update strategy
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${var.project_name}-asg-instance"
    propagate_at_launch = true
  }

  tag {
    key                 = "Project"
    value               = var.project_name
    propagate_at_launch = true
  }
}

# ── Scale-Up Policy (CPU > threshold) ──────────────────────
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "${var.project_name}-scale-up"
  autoscaling_group_name = aws_autoscaling_group.app.name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = 1
  cooldown               = 120
  policy_type            = "SimpleScaling"
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.project_name}-cpu-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = var.scale_up_cpu_threshold
  alarm_description   = "Scale up when CPU >= ${var.scale_up_cpu_threshold}%"
  alarm_actions       = [aws_autoscaling_policy.scale_up.arn]

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app.name
  }
}

# ── Scale-Down Policy (CPU < threshold) ────────────────────
resource "aws_autoscaling_policy" "scale_down" {
  name                   = "${var.project_name}-scale-down"
  autoscaling_group_name = aws_autoscaling_group.app.name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = -1
  cooldown               = 300
  policy_type            = "SimpleScaling"
}

resource "aws_cloudwatch_metric_alarm" "cpu_low" {
  alarm_name          = "${var.project_name}-cpu-low"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = var.scale_down_cpu_threshold
  alarm_description   = "Scale down when CPU <= ${var.scale_down_cpu_threshold}%"
  alarm_actions       = [aws_autoscaling_policy.scale_down.arn]

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app.name
  }
}
