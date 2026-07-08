#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${NAMESPACE:-orchestration}"
RELEASE="${RELEASE:-airflow}"
AIRFLOW_HOST="${AIRFLOW_HOST:-airflow.k8s.tailnet}"
VALUES_FILE="${VALUES_FILE:-$SCRIPT_DIR/values-keycloak-only-http.yaml}"

for cmd in kubectl helm python3 openssl; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERROR: Không tìm thấy lệnh '$cmd'." >&2
    exit 1
  }
done

on_error() {
  rc=$?
  echo >&2
  echo "ERROR: Khởi động Airflow thất bại (exit=$rc)." >&2
  kubectl get pods,svc,ingress,pvc -n "$NAMESPACE" -o wide 2>/dev/null || true
  kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' 2>/dev/null | tail -n 40 || true
  exit "$rc"
}
trap on_error ERR

if [[ "$NAMESPACE" != "orchestration" ]]; then
  echo "ERROR: Script này chỉ cho phép namespace orchestration." >&2
  exit 1
fi

kubectl config current-context
kubectl cluster-info >/dev/null

if ! helm status "$RELEASE" -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "ERROR: Không tìm thấy Helm release '$RELEASE' trong namespace '$NAMESPACE'." >&2
  echo "Script này chỉ khởi động/cập nhật release hiện có để tránh cài lại bằng image hoặc version không chắc chắn." >&2
  exit 1
fi

if ! kubectl get storageclass longhorn >/dev/null 2>&1; then
  echo "ERROR: Không tìm thấy StorageClass 'longhorn'." >&2
  exit 1
fi

echo "== Chỉ apply tài nguyên trong namespace orchestration =="
kubectl apply -f "$SCRIPT_DIR/storage.yaml"
kubectl apply -f "$SCRIPT_DIR/postgres-nodeport.yaml"

echo "== Secret webserver =="
if ! kubectl get secret airflow-webserver-secret -n "$NAMESPACE" >/dev/null 2>&1; then
  kubectl create secret generic airflow-webserver-secret \
    -n "$NAMESPACE" \
    --from-literal=webserver-secret-key="$(openssl rand -hex 32)"
else
  echo "Giữ nguyên Secret airflow-webserver-secret hiện có."
fi

echo "== Secret kết nối Keycloak trong namespace orchestration =="
if ! kubectl get secret airflow-keycloak -n "$NAMESPACE" >/dev/null 2>&1; then
  if [[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]]; then
    echo "ERROR: Secret airflow-keycloak chưa tồn tại." >&2
    echo "Chạy: export KEYCLOAK_CLIENT_SECRET='<client-secret>'" >&2
    exit 1
  fi

  kubectl create secret generic airflow-keycloak \
    -n "$NAMESPACE" \
    --from-literal=KEYCLOAK_CLIENT_ID=airflow \
    --from-literal=KEYCLOAK_CLIENT_SECRET="$KEYCLOAK_CLIENT_SECRET"
else
  echo "Giữ nguyên Secret airflow-keycloak hiện có."
fi

echo "== Xác định đúng chart version đang chạy =="
chart_field="$(helm list -n "$NAMESPACE" -o json | python3 -c '
import json, sys
items = json.load(sys.stdin)
name = sys.argv[1]
match = next((item for item in items if item.get("name") == name), None)
if not match:
    raise SystemExit(1)
print(match["chart"])
' "$RELEASE")"
chart_version="${chart_field#airflow-}"

echo "Chart version hiện tại: $chart_version"
helm get values "$RELEASE" -n "$NAMESPACE" -o yaml \
  > "$SCRIPT_DIR/values-before-restart-$(date +%Y%m%d-%H%M%S).yaml"

helm repo add apache-airflow https://airflow.apache.org >/dev/null 2>&1 || true
helm repo update apache-airflow >/dev/null

echo "== Upgrade/restart Airflow, giữ nguyên values và image hiện tại =="
helm upgrade "$RELEASE" apache-airflow/airflow \
  -n "$NAMESPACE" \
  --version "$chart_version" \
  --reuse-values \
  -f "$VALUES_FILE" \
  --wait \
  --timeout 30m

echo "== Trạng thái orchestration =="
helm status "$RELEASE" -n "$NAMESPACE"
kubectl get pods,svc,ingress,pvc -n "$NAMESPACE" -o wide

echo
echo "Airflow: http://${AIRFLOW_HOST}:30296"
