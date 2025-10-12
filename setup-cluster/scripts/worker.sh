#!/usr/bin/env bash
set -euo pipefail
echo "Worker ready for kubeadm join" | sudo tee /opt/setup/STATUS_WORKER_WAIT_JOIN
