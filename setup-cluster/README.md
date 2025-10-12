# Kubeadm Cluster + MinIO on AWS (Ubuntu 22.04)

## Kiến trúc
- 1× MinIO node (m7i.2xlarge, 8 vCPU, 32GiB RAM, EBS gp3 2TB)
- 3× Service nodes:
  - 1× Control-plane (m7i.3xlarge, 12 vCPU, 48GiB RAM, EBS gp3 1TB)
  - 2× Workers (m7i.3xlarge, 12 vCPU, 48GiB RAM, EBS gp3 1TB)

EC2 được cài sẵn:
- containerd (SystemdCgroup=true)
- kubeadm, kubelet, kubectl (repo pkgs.k8s.io)
- Master tự `kubeadm init` + cài Calico (pod CIDR 192.168.0.0/16)
- MinIO tự mount /dev/sdf → /mnt/minio và chạy MinIO server + console
- Workers đã cài sẵn mọi thứ, chờ lệnh `kubeadm join`.

> Mặc định dùng Default VPC/Subnet để nhanh. Có thể tách VPC/Subnet riêng sau.

---

## Cách chạy nhanh

### 0) Chuẩn bị
- Tạo **Key Pair** trong AWS (EC2 → Key Pairs), lấy tên key cho `key_name`.
- Lấy Access để chạy `terraform` (profile/role tuỳ bạn).

### 1) Điền biến
Sửa `terraform.tfvars` (tạo từ file mẫu `terraform.tfvars.example`).

### 2) Apply hạ tầng
```bash
terraform init
terraform apply -auto-approve
