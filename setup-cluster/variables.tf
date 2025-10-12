variable "region" {
  description = "AWS region (vd: ap-southeast-1)"
  type        = string
}

variable "key_name" {
  description = "Tên EC2 Key Pair để SSH"
  type        = string
}

variable "minio_instance_type" {
  description = "Loại instance cho MinIO"
  type        = string
  default     = "m7i.2xlarge"
}

variable "svc_instance_type" {
  description = "Loại instance cho service nodes"
  type        = string
  default     = "m7i.3xlarge"
}

variable "minio_data_size_gb" {
  description = "Kích thước EBS gp3 cho MinIO (GiB)"
  type        = number
  default     = 2048
}

variable "svc_data_size_gb" {
  description = "Kích thước EBS gp3 cho service nodes (GiB)"
  type        = number
  default     = 1024
}

variable "minio_gp3_iops" {
  description = "IOPS cho volume gp3 MinIO"
  type        = number
  default     = 6000
}

variable "minio_gp3_throughput" {
  description = "Throughput (MiB/s) cho volume gp3 MinIO"
  type        = number
  default     = 500
}

variable "svc_gp3_iops" {
  description = "IOPS cho volume gp3 service nodes"
  type        = number
  default     = 4000
}

variable "svc_gp3_throughput" {
  description = "Throughput (MiB/s) cho volume gp3 service nodes"
  type        = number
  default     = 250
}

variable "minio_root_user" {
  description = "MINIO_ROOT_USER"
  type        = string
}

variable "minio_root_password" {
  description = "MINIO_ROOT_PASSWORD (>=8 ký tự)"
  type        = string
  sensitive   = true
}
