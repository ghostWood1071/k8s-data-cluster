#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${NAMESPACE:-orchestration}"
RELEASE="${RELEASE:-airflow}"
AIRFLOW_HOST="${AIRFLOW_HOST:-airflow.k8s.tailnet}"
AIRFLOW_PUBLIC_URL="${AIRFLOW_PUBLIC_URL:-https://airflow.datalabutehy.com}"
VALUES_FILE="${VALUES_FILE:-$SCRIPT_DIR/values-keycloak-only-http.yaml}"
EXTRA_VALUES_FILES="${EXTRA_VALUES_FILES:-}"
BACKUP_DIR="${BACKUP_DIR:-/tmp}"

for cmd in kubectl helm python3 openssl; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERROR: command '$cmd' was not found." >&2
    exit 1
  }
done

on_error() {
  rc=$?
  echo >&2
  echo "ERROR: Airflow restart failed (exit=$rc)." >&2
  kubectl get pods,svc,ingress,pvc -n "$NAMESPACE" -o wide 2>/dev/null || true
  kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' 2>/dev/null | tail -n 40 || true
  exit "$rc"
}
trap on_error ERR

if [[ "$NAMESPACE" != "orchestration" ]]; then
  echo "ERROR: this script is restricted to namespace orchestration." >&2
  exit 1
fi

kubectl config current-context
kubectl cluster-info >/dev/null

if ! helm status "$RELEASE" -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "ERROR: Helm release '$RELEASE' was not found in namespace '$NAMESPACE'." >&2
  echo "This script only updates an existing release to avoid accidental fresh installs." >&2
  exit 1
fi

if ! kubectl get storageclass longhorn >/dev/null 2>&1; then
  echo "ERROR: StorageClass 'longhorn' was not found." >&2
  exit 1
fi

echo "== Apply orchestration-only resources =="
kubectl apply -f "$SCRIPT_DIR/storage.yaml"
kubectl apply -f "$SCRIPT_DIR/postgres-nodeport.yaml"

echo "== Webserver secret =="
if ! kubectl get secret airflow-webserver-secret -n "$NAMESPACE" >/dev/null 2>&1; then
  kubectl create secret generic airflow-webserver-secret \
    -n "$NAMESPACE" \
    --from-literal=webserver-secret-key="$(openssl rand -hex 32)"
else
  echo "Keeping existing secret airflow-webserver-secret."
fi

echo "== Keycloak client secret =="
if ! kubectl get secret airflow-keycloak -n "$NAMESPACE" >/dev/null 2>&1; then
  if [[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]]; then
    echo "ERROR: secret airflow-keycloak does not exist." >&2
    echo "Run: export KEYCLOAK_CLIENT_SECRET='<client-secret>'" >&2
    exit 1
  fi

  kubectl create secret generic airflow-keycloak \
    -n "$NAMESPACE" \
    --from-literal=KEYCLOAK_CLIENT_ID=airflow \
    --from-literal=KEYCLOAK_CLIENT_SECRET="$KEYCLOAK_CLIENT_SECRET"
else
  echo "Keeping existing secret airflow-keycloak."
fi

echo "== Detect installed chart version =="
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

mkdir -p "$BACKUP_DIR"
backup_file="$BACKUP_DIR/${RELEASE}-values-before-restart-$(date +%Y%m%d-%H%M%S).yaml"

echo "Installed chart version: $chart_version"
echo "Saving current values to $backup_file"
helm get values "$RELEASE" -n "$NAMESPACE" -o yaml > "$backup_file"

helm repo add apache-airflow https://airflow.apache.org >/dev/null 2>&1 || true
helm repo update apache-airflow >/dev/null

helm_args=(
  "$RELEASE"
  apache-airflow/airflow
  -n "$NAMESPACE"
  --version "$chart_version"
  --reuse-values
  -f "$VALUES_FILE"
  --wait
  --timeout 30m
)

if [[ -n "$EXTRA_VALUES_FILES" ]]; then
  for values_path in $EXTRA_VALUES_FILES; do
    if [[ "$values_path" != /* ]]; then
      values_path="$SCRIPT_DIR/$values_path"
    fi
    helm_args+=(-f "$values_path")
  done
fi

echo "== Helm upgrade/restart Airflow =="
helm upgrade "${helm_args[@]}"

echo "== Remove stale NGINX basic-auth annotations from Airflow ingress =="
for ingress_name in "${RELEASE}-ingress" "${RELEASE}-webserver"; do
  kubectl annotate ingress "$ingress_name" \
    -n "$NAMESPACE" \
    nginx.ingress.kubernetes.io/auth-type- \
    nginx.ingress.kubernetes.io/auth-secret- \
    nginx.ingress.kubernetes.io/auth-realm- \
    nginx.ingress.kubernetes.io/auth-url- \
    nginx.ingress.kubernetes.io/auth-signin- \
    --overwrite || true
done

echo "== Orchestration status =="
helm status "$RELEASE" -n "$NAMESPACE"
kubectl get pods,svc,ingress,pvc -n "$NAMESPACE" -o wide

echo
echo "Airflow public: ${AIRFLOW_PUBLIC_URL}"
echo "Airflow internal ingress: http://${AIRFLOW_HOST}:30296"
