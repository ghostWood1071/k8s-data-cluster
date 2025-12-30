terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}


data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "ubuntu_2204_gp2" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  ami_id    = data.aws_ami.ubuntu_2204_gp2.id
  subnet_id = element(data.aws_subnets.default.ids, 0)
}


resource "aws_security_group" "data-platform-sg" {
  name        = "data-platform-sg"
  description = "Kubernetes + SSH + MinIO"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 79
    to_port     = 79
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 2379
    to_port     = 2380
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 10250
    to_port     = 10250
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 10257
    to_port     = 10257
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 10259
    to_port     = 10259
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 9000
    to_port     = 9001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow all inbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"     
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_iam_policy_document" "ssm_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm_role" {
  name               = "ec2-ssm-role"
  assume_role_policy = data.aws_iam_policy_document.ssm_assume.json
}

resource "aws_iam_instance_profile" "ssm_profile" {
  name = "ec2-ssm-instance-profile"
  role = aws_iam_role.ssm_role.name
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "ec2_readonly" {
  role       = aws_iam_role.ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess"
}

locals {
  common_sh = replace(file("${path.module}/scripts/common.sh"), "\n", "\n        ")
  master_sh = replace(file("${path.module}/scripts/master.sh"), "\n", "\n        ")

  master_user_data = templatefile("${path.module}/cloudinit/master-cloudinit.yaml.tmpl", {
    COMMON_SH = local.common_sh
    MASTER_SH = local.master_sh
  })

  worker_user_data = templatefile("${path.module}/cloudinit/worker-cloudinit.yaml.tmpl", {
    COMMON_SH = local.common_sh
  })
}

resource "aws_instance" "poc-svc_master" {
  ami                    = local.ami_id
  instance_type          = var.svc_master_instance_type
  subnet_id              = local.subnet_id
  key_name               = var.key_name
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name
  vpc_security_group_ids = [aws_security_group.data-platform-sg.id]

  user_data = local.master_user_data

  root_block_device {
    volume_type = var.svc_storage_type
    volume_size = var.svc_master_storage_size_gb
    iops = var.svc_gp3_iops
    throughput = var.svc_gp3_throughput
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "svc-master"
    Role = "k8s-master"
    OS   = "ubuntu-22.04"
  }
}

resource "aws_instance" "poc-svc_workers" {
  count                  = var.svc_num_worker
  ami                    = local.ami_id
  instance_type          = var.svc_instance_type
  subnet_id              = local.subnet_id
  key_name               = var.key_name
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name
  vpc_security_group_ids = [aws_security_group.data-platform-sg.id]

  user_data = local.worker_user_data

  root_block_device {
    volume_type = var.svc_storage_type
    volume_size = var.svc_data_size_gb
    iops = var.svc_gp3_iops
    throughput = var.svc_gp3_throughput
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "svc-worker-${count.index + 1}"
    Role = "k8s-worker"
    OS   = "ubuntu-22.04"
  }
}

resource "null_resource" "hint_join_script" {
  triggers = {
    master_ip  = aws_instance.poc-svc_master.private_ip
    worker1_ip = aws_instance.poc-svc_workers[0].private_ip
    worker2_ip = aws_instance.poc-svc_workers[1].private_ip
  }

  provisioner "local-exec" {
    command = <<-CMD
      echo "==> Master private IP:  ${aws_instance.poc-svc_master.private_ip}"
      echo "==> Workers private IP: ${aws_instance.poc-svc_workers[0].private_ip}, ${aws_instance.poc-svc_workers[1].private_ip}"
    CMD
  }
}
