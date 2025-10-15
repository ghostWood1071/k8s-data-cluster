#!/bin/bash
set -e
STARROCKS_VERSION="3.3.0"
INSTALL_DIR="/opt/starrocks"

# Terraform injects MASTER_IP directly
MASTER_IP="__MASTER_IP__"

# Get this node’s private IP without curl
# Option 1: hostname -I (Ubuntu friendly)
MY_IP=$(hostname -I | awk '{print $1}')

# Option 2 (fallback): ip route
# MY_IP=$(ip route get 1 | awk '{print $7; exit}')

apt-get update -y
apt-get install -y openjdk-17-jdk wget tar mysql-client net-tools

mkdir -p "/opt/starrocks"
cd "/opt/starrocks"
wget -q https://releases.starrocks.io/starrocks/StarRocks-${STARROCKS_VERSION}-ubuntu-amd64.tar.gz -O starrocks.tar.gz
tar -xzf tarrocks.tar.gz && rm starrocks.tar.gz
mv StarRocks-* fe
cp -r fe be

# FE conf
cat <<EOF > "/opt/starrocks"/fe/conf/fe.conf
run_mode=shared_data
priority_networks=${MY_IP}/24
metadata_failure_recovery=true
EOF

# BE conf
cat <<EOF > "/opt/starrocks"/be/conf/be.conf
storage_root_path="/opt/starrocks"/be/storage
priority_networks=${MY_IP}/24
heartbeat_service_port=9050
be_port=9060
brpc_port=8060
EOF

# systemd configs (FE + BE)
cat <<EOF > /etc/systemd/system/starrocks-fe.service
[Unit]
Description=StarRocks FrontEnd
After=network.target
[Service]
Type=forking
ExecStart="/opt/starrocks"/fe/bin/start_fe.sh --daemon
ExecStop="/opt/starrocks"/fe/bin/stop_fe.sh
Restart=always
LimitNOFILE=65536
[Install]
WantedBy=multi-user.target
EOF

cat <<EOF > /etc/systemd/system/starrocks-be.service
[Unit]
Description=StarRocks BackEnd
After=network.target
[Service]
Type=forking
ExecStart="/opt/starrocks"/be/bin/start_be.sh --daemon
ExecStop="/opt/starrocks"/be/bin/stop_be.sh
Restart=always
LimitNOFILE=65536
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable starrocks-fe starrocks-be

# Start and join cluster
sleep 60
systemctl start starrocks-fe
sleep 40
systemctl start starrocks-be
sleep 40

echo "[OK] Worker ($MY_IP) joined master ($MASTER_IP)"
