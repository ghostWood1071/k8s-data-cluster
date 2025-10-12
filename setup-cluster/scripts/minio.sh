#!/usr/bin/env bash
set -euo pipefail

# --- Helper: discover region via IMDS ---
get_region() {
  curl -sLf --connect-timeout 2 http://169.254.169.254/latest/dynamic/instance-identity/document \
    | grep region | awk -F\" '{print $4}'
}

# --- Packages needed for discovery ---
sudo apt-get update -y
sudo apt-get install -y awscli jq

# --- Format/mount data volume ---
sudo mkfs.ext4 -F /dev/sdf
sudo mkdir -p /mnt/minio
echo "/dev/sdf /mnt/minio ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
sudo mount -a

# --- Install MinIO server ---
wget -q https://dl.min.io/server/minio/release/linux-amd64/minio -O /tmp/minio
sudo install -m 0755 /tmp/minio /usr/local/bin/minio

# --- Service user ---
sudo useradd -r -s /sbin/nologin minio-user || true
sudo chown -R minio-user:minio-user /mnt/minio

# --- Discover peer IPs by tag Role=minio (requires AmazonEC2ReadOnlyAccess) ---
REGION="$(get_region || echo "")"
if [[ -z "${REGION}" ]]; then
  # Fallback: try instance metadata again
  REGION="$(curl -sLf http://169.254.169.254/latest/meta-data/placement/region || true)"
fi

# Get all running instances with tag Role=minio (private IPs)
PEERS=$(aws ec2 describe-instances \
  --region "${REGION}" \
  --filters "Name=tag:Role,Values=minio" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].PrivateIpAddress' \
  --output text 2>/dev/null || true)

# Build endpoints line
ENDPOINTS=""
if [[ -n "${PEERS}" ]]; then
  for ip in ${PEERS}; do
    ENDPOINTS+=" http://${ip}/mnt/minio"
  done
fi

# Fallback: if discovery failed, at least run single-node
if [[ -z "${ENDPOINTS}" ]]; then
  # Try local private IP
  SELF_IP="$(hostname -I | awk '{print $1}')"
  ENDPOINTS=" http://${SELF_IP}/mnt/minio"
fi

echo "${ENDPOINTS}" | sudo tee /etc/minio.args

# --- Systemd unit (reads /etc/minio.env and /etc/minio.args) ---
cat <<'UNIT' | sudo tee /etc/systemd/system/minio.service >/dev/null
[Unit]
Description=MinIO (Distributed or Single)
After=network.target

[Service]
User=minio-user
Group=minio-user
EnvironmentFile=/etc/minio.env
ExecStart=/usr/local/bin/minio server $(/bin/cat /etc/minio.args) --console-address ":9001"
Restart=always
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now minio

echo "MinIO started (endpoints:$(cat /etc/minio.args))" | sudo tee /opt/setup/STATUS_MINIO_OK
