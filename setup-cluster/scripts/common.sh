#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update -y
sudo swapoff -a || true

# Kernel modules + sysctl
cat <<'EOF' | sudo tee /etc/modules-load.d/containerd.conf
overlay
br_netfilter
EOF
sudo modprobe overlay
sudo modprobe br_netfilter

cat <<'EOF' | sudo tee /etc/sysctl.d/99-kubernetes.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
sudo sysctl --system

# Containerd + cgroup driver systemd
sudo apt-get install -y containerd apt-transport-https ca-certificates curl gpg
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/^\(\s*SystemdCgroup\s*=\s*\)false/\1true/' /etc/containerd/config.toml
sudo systemctl enable --now containerd

# kubeadm/kubelet/kubectl từ pkgs.k8s.io (v1.34 stable stream)
sudo curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.34/deb/Release.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.34/deb/ /' \
 | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update -y
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl

echo "Common bootstrap done" | sudo tee /opt/setup/STATUS_COMMON_OK
