#!/usr/bin/env bash
set -Eeuo pipefail

NAMESPACE="${NAMESPACE:-orchestration}"
RELEASE="${RELEASE:-airflow}"
AIRFLOW_HOST="${AIRFLOW_HOST:-airflow.k8s.tailnet}"
VALUES_FILE="${VALUES_FILE:-values-keycloak-only.yaml}"

if [[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]]; then
  echo "ERROR: Hãy export KEYCLOAK_CLIENT_SECRET trước khi chạy." >&2
  exit 1
fi

command -v kubectl >/dev/null
command -v helm >/dev/null
command -v openssl >/dev/null

echo "== Kiểm tra Helm release hiện tại =="
RELEASE_JSON="$(helm list -n "$NAMESPACE" -o json)"
CHART_FIELD="$(printf '%s' "$RELEASE_JSON" | python3 -c '
import json, sys
items=json.load(sys.stdin)
name=sys.argv[1]
matches=[x for x in items if x.get("name")==name]
if not matches:
    raise SystemExit(f"Không tìm thấy release {name}")
print(matches[0]["chart"])
' "$RELEASE")"

CHART_VERSION="${CHART_FIELD#airflow-}"
echo "Release: $RELEASE"
echo "Giữ nguyên chart version: $CHART_VERSION"

echo "== Sao lưu values hiện tại =="
helm get values "$RELEASE" -n "$NAMESPACE" -o yaml \
  > "values-before-keycloak-$(date +%Y%m%d-%H%M%S).yaml"

echo "== Tạo/cập nhật Secret Keycloak =="
kubectl create secret generic airflow-keycloak \
  -n "$NAMESPACE" \
  --from-literal=KEYCLOAK_CLIENT_ID=airflow \
  --from-literal=KEYCLOAK_CLIENT_SECRET="$KEYCLOAK_CLIENT_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "== Tạo TLS Secret nếu chưa có =="
if ! kubectl get secret airflow-tls -n "$NAMESPACE" >/dev/null 2>&1; then
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout "$tmpdir/airflow.key" \
    -out "$tmpdir/airflow.crt" \
    -subj "/CN=${AIRFLOW_HOST}" \
    -addext "subjectAltName=DNS:${AIRFLOW_HOST}"

  kubectl create secret tls airflow-tls \
    -n "$NAMESPACE" \
    --cert="$tmpdir/airflow.crt" \
    --key="$tmpdir/airflow.key"
fi

echo "== Giữ nguyên chart/image/version và chỉ áp overlay SSO =="
helm repo add apache-airflow https://airflow.apache.org >/dev/null 2>&1 || true
helm repo update apache-airflow >/dev/null

helm upgrade "$RELEASE" apache-airflow/airflow \
  -n "$NAMESPACE" \
  --version "$CHART_VERSION" \
  --reuse-values \
  -f "$VALUES_FILE" \
  --wait \
  --timeout 15m

echo "== Trạng thái =="
kubectl get pods,svc,ingress -n "$NAMESPACE" -o wide

echo
echo "Hoàn tất. Truy cập: https://${AIRFLOW_HOST}:31662"
