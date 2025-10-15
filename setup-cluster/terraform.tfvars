region   = "ap-southeast-1"
key_name = "mbs-poc-key"

minio_instance_type = "t3.medium"
svc_instance_type   = "t3.xlarge"
starrock_instance_type = "m5.4xlarge"
# minio_instance_type = "m5.2xlarge"
# svc_instance_type   = "m5.4xlarge"

# storage
minio_data_size_gb   = 2048
svc_data_size_gb     = 1024
minio_gp3_iops       = 6000
minio_gp3_throughput = 500
svc_gp3_iops         = 4000
svc_gp3_throughput   = 250
starrock_size_gb = 1000

# MinIO creds
minio_root_user     = "minio"
minio_root_password = "minio@123"
