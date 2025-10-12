#!/usr/bin/env bash
set -euo pipefail

APISERVER=$(hostname -I | awk '{print $1}')
sudo kubeadm init --apiserver-advertise-address="${APISERVER}" --pod-network-cidr=192.168.0.0/16

# kubeconfig cho user mặc định (cloud-init chạy với root, nhưng HOME=/root)
HOME_DIR="/home/ubuntu"
mkdir -p ${HOME_DIR}/.kube
sudo cp -i /etc/kubernetes/admin.conf ${HOME_DIR}/.kube/config
sudo chown ubuntu:ubuntu ${HOME_DIR}/.kube/config

# Calico operator (v3.30.x)
sudo -u ubuntu kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.3/manifests/operator-crds.yaml
sudo -u ubuntu kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.3/manifests/tigera-operator.yaml

# Sinh lệnh join
kubeadm token create --print-join-command | tee ${HOME_DIR}/join-command.txt
chown ubuntu:ubuntu ${HOME_DIR}/join-command.txt

# Helper script để SSH vào 2 worker join (điền IP trong Terraform outputs / hoặc tự sửa sau)
cat <<'JOIN' > ${HOME_DIR}/join-all-workers.sh
#!/usr/bin/env bash
set -euo pipefail
JOIN_CMD="$(cat ${HOME}/join-command.txt)"
WORKERS=(__WORKER1__ __WORKER2__)  # thay IP private workers
for W in "${WORKERS[@]}"; do
  echo "==> Joining $W"
  ssh -o StrictHostKeyChecking=no ubuntu@$W "echo '$JOIN_CMD' | sudo bash"
done
JOIN
chmod +x ${HOME_DIR}/join-all-workers.sh
chown ubuntu:ubuntu ${HOME_DIR}/join-all-workers.sh

cat <<'NOTE' > ${HOME_DIR}/README_CLUSTER.txt
- K8s master đã init + Calico applied.
- Lệnh join: ~/join-command.txt
- Script join SSH: ~/join-all-workers.sh (sửa __WORKER1__/__WORKER2__)
- Kiểm tra: kubectl get nodes -o wide
NOTE
chown ubuntu:ubuntu ${HOME_DIR}/README_CLUSTER.txt

echo "Master init done" | sudo tee /opt/setup/STATUS_MASTER_OK
