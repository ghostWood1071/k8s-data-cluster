#!/bin/bash
set -e
STARROCKS_VERSION="3.3.18"
INSTALL_DIR="/opt/starrocks"
MY_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

apt-get update -y
apt-get install -y openjdk-17-jdk wget tar mysql-client net-tools

mkdir -p ${INSTALL_DIR}
cd ${INSTALL_DIR}
wget -q https://releases.starrocks.io/starrocks/StarRocks-${STARROCKS_VERSION}-ubuntu-amd64.tar.gz -O starrocks.tar.gz
tar -xzf starrocks.tar.gz && rm starrocks.tar.gz
mv starrocks-* fe
cp -r fe be

# --- FE conf ---
cat <<EOF > ${INSTALL_DIR}/fe/conf/fe.conf
run_mode=shared_data
priority_networks=${MY_IP}/24
metadata_failure_recovery=true
EOF

# --- BE conf ---
cat <<EOF > ${INSTALL_DIR}/be/conf/be.conf
storage_root_path=${INSTALL_DIR}/be/storage
priority_networks=${MY_IP}/24
heartbeat_service_port=9050
be_port=9060
brpc_port=8060
EOF

# --- systemd services ---
cat <<EOF > /etc/systemd/system/starrocks-fe.service
[Unit]
Description=StarRocks FrontEnd
After=network.target
[Service]
Type=forking
ExecStart=${INSTALL_DIR}/fe/bin/start_fe.sh --daemon
ExecStop=${INSTALL_DIR}/fe/bin/stop_fe.sh
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
ExecStart=${INSTALL_DIR}/be/bin/start_be.sh --daemon
ExecStop=${INSTALL_DIR}/be/bin/stop_be.sh
Restart=always
LimitNOFILE=65536
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable starrocks-fe starrocks-be
systemctl start starrocks-fe
sleep 60
systemctl start starrocks-be
sleep 30

echo "MASTER_IP=${MY_IP}" > /opt/starrocks/master_info
echo "[OK] FE+BE master started on $MY_IP"
