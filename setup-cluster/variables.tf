variable "region" {
  description = "AWS region (vd: ap-southeast-1)"
  type        = string
}

variable "key_name" {
  description = "Tên EC2 Key Pair để SSH"
  type        = string
}

variable "svc_instance_type" {
  description = "Loại instance cho service nodes"
  type        = string
  default     = "m7i.3xlarge"
}

variable "svc_master_instance_type" {
  description = "Loại instance cho service nodes"
  type        = string
  default     = "m7i.3xlarge"
}

variable "svc_data_size_gb" {
  description = "Kích thước EBS gp3 cho service nodes (GiB)"
  type        = number
  default     = 1024
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

variable "svc_num_worker" {
  description = "number of worker"
  type        = number
  default     = 2
}

variable "svc_master_storage_size_gb" {
  description = "master storage size"
  type        = number
  default     = 2
}

variable "svc_storage_type" {
  description = "storage type gp3/gp2"
  type        = string
  default     = "gp3"
}

