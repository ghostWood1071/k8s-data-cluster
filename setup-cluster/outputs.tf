# output "minio_public_ips" { value = [aws_instance.mbs-poc-minio_a.public_ip, aws_instance.mbs-poc-minio_b.public_ip] }
# output "minio_private_ips" { value = [aws_instance.mbs-poc-minio_a.private_ip, aws_instance.mbs-poc-minio_b.private_ip] }
output "svc_master_public_ip" { value = aws_instance.mbs-poc-svc_master.public_ip }
output "svc_master_private_ip" { value = aws_instance.mbs-poc-svc_master.private_ip }
output "svc_worker_public_ips" { value = [for i in aws_instance.mbs-poc-svc_workers : i.public_ip] }
output "svc_worker_private_ips" { value = [for i in aws_instance.mbs-poc-svc_workers : i.private_ip] }
