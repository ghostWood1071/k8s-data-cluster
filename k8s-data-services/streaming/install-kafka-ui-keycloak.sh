#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="streaming"
KAFKA_UI_HOST="${KAFKA_UI_HOST:-kafka-ui.datalabutehy.com}"
MANIFEST="${1:-kafka-ui-keycloak-rbac.yaml}"

for command in kubectl; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Thiếu lệnh bắt buộc: ${command}"
    exit 1
  fi
done

if [[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]]; then
  echo "Thiếu KEYCLOAK_CLIENT_SECRET."
  echo "Chạy: export KEYCLOAK_CLIENT_SECRET='secret-lay-tu-keycloak-client-kafka-ui'"
  exit 1
fi

if [[ ! -f "${MANIFEST}" ]]; then
  echo "Không tìm thấy manifest: ${MANIFEST}"
  exit 1
fi

echo "==> Kiểm tra namespace"
kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

echo "==> Kiểm tra các Service phụ thuộc"
kubectl get svc kafka-broker kafka-connect -n "${NAMESPACE}"

echo "==> Xóa bản Kafka UI cũ"
kubectl delete deployment,service,ingress kafka-ui   -n "${NAMESPACE}"   --ignore-not-found

kubectl delete secret kafka-ui-keycloak   -n "${NAMESPACE}"   --ignore-not-found

kubectl delete configmap kafka-ui-config kafka-ui-rbac   -n "${NAMESPACE}"   --ignore-not-found

echo "==> Tạo Secret chứa client Keycloak"
kubectl create secret generic kafka-ui-keycloak   -n "${NAMESPACE}"   --from-literal=client-secret="${KEYCLOAK_CLIENT_SECRET}"

echo "==> Deploy Kafka UI + Keycloak OAuth2 + RBAC"
kubectl apply -f "${MANIFEST}"

echo "==> Chờ Kafka UI sẵn sàng"
kubectl rollout status deployment/kafka-ui   -n "${NAMESPACE}"   --timeout=300s

echo
kubectl get deployment,pod,service,ingress   -n "${NAMESPACE}"   -l app.kubernetes.io/name=kafka-ui

echo
echo "URL: https://${KAFKA_UI_HOST}"
echo "Authorization debug: https://${KAFKA_UI_HOST}/api/authorization"
echo "Logs: kubectl logs -n ${NAMESPACE} deployment/kafka-ui -f"
