#!/usr/bin/env bash
set -euo pipefail

APISERVER=$(hostname -I | awk '{print $1}')
sudo kubeadm init --apiserver-advertise-address="${APISERVER}" --pod-network-cidr=192.168.0.0/16

# kubeconfig cho user mặc định (cloud-init chạy với root, nhưng HOME=/root)
HOME_DIR="/home/ubuntu"
mkdir -p ${HOME_DIR}/.kube
sudo cp -i /etc/kubernetes/admin.conf ${HOME_DIR}/.kube/config
sudo chown ubuntu:ubuntu ${HOME_DIR}/.kube/config

