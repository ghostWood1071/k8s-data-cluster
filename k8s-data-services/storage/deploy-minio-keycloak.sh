#!/usr/bin/env bash
set -Eeuo pipefail

NAMESPACE="storage"
MINIO_PUBLIC_URL="https://minio.datalabutehy.com"
SCRIPT_PATH="$0"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"

log() {
  printf '\n[storage-deploy] %s\n' "$*"
}

need_file() {
  if [ ! -f "$1" ]; then
    echo "Missing required file: $1" >&2
    exit 1
  fi
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

wait_job_complete() {
  job_name="$1"
  kubectl -n "$NAMESPACE" wait --for=condition=complete "job/$job_name" --timeout=180s
}

show_job_logs_redacted() {
  job_name="$1"
  kubectl -n "$NAMESPACE" logs "job/$job_name" \
    | sed -E 's/(client_secret=)[^ ]+/\1***redacted***/g; s/(CLIENT_SECRET=).*/\1***redacted***/g; s/(password=)[^ ]+/\1***redacted***/Ig' || true
}

cd "$SCRIPT_DIR"

need_cmd kubectl
need_cmd sed
need_cmd grep

need_file 00-minio-headless-service.yaml
need_file 01-minio-service.yaml
need_file 02-minio-sts.yaml
need_file 03-minio-secret.yaml
need_file 05-keycloak-minio-setup-secret.yaml
need_file 06-keycloak-minio-client-job.yaml
need_file 10-minio-keycloak-idp-config-job.yaml

log "Applying MinIO services and secret"
kubectl apply -f 00-minio-headless-service.yaml
kubectl apply -f 01-minio-service.yaml
kubectl apply -f 03-minio-secret.yaml

log "Applying MinIO StatefulSet"
kubectl apply -f 02-minio-sts.yaml
kubectl -n "$NAMESPACE" rollout status sts/minio --timeout=240s

log "Applying Keycloak setup secret"
kubectl apply -f 05-keycloak-minio-setup-secret.yaml

log "Removing obsolete OIDC env objects if they still exist"
kubectl -n "$NAMESPACE" delete configmap minio-oidc --ignore-not-found
kubectl -n "$NAMESPACE" delete secret minio-oidc minio-oidc-config --ignore-not-found

log "Creating or updating Keycloak client, mapper, and MinIO roles"
kubectl -n "$NAMESPACE" delete job keycloak-minio-client --ignore-not-found
kubectl apply -f 06-keycloak-minio-client-job.yaml
wait_job_complete keycloak-minio-client
show_job_logs_redacted keycloak-minio-client

log "Configuring MinIO OpenID through mc admin config"
kubectl -n "$NAMESPACE" delete job minio-keycloak-idp-config --ignore-not-found
kubectl apply -f 10-minio-keycloak-idp-config-job.yaml
wait_job_complete minio-keycloak-idp-config
show_job_logs_redacted minio-keycloak-idp-config

log "Restarting MinIO so the new OpenID config is loaded"
kubectl -n "$NAMESPACE" rollout restart sts/minio
kubectl -n "$NAMESPACE" rollout status sts/minio --timeout=240s

log "Checking MinIO pods"
kubectl -n "$NAMESPACE" get pods -l app=minio -o wide

log "Checking that old MINIO_IDENTITY_OPENID env injection is not present"
for pod in minio-0 minio-1; do
  if kubectl -n "$NAMESPACE" get pod "$pod" >/dev/null 2>&1; then
    if kubectl -n "$NAMESPACE" exec "$pod" -- printenv | grep '^MINIO_IDENTITY_OPENID' >/dev/null 2>&1; then
      echo "WARNING: $pod still has MINIO_IDENTITY_OPENID env variables" >&2
    else
      echo "$pod: no MINIO_IDENTITY_OPENID env variables"
    fi
  fi
done

log "Checking public MinIO login strategy"
if command -v curl >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  curl -ksS "$MINIO_PUBLIC_URL/api/v1/login" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print("loginStrategy=" + str(d.get("loginStrategy"))); rr=d.get("redirectRules") or []; print("redirect=" + (rr[0].get("redirect", "")[:180] if rr else ""))' || true
else
  echo "Skip public login check because curl or python3 is missing"
fi

log "Done. Open $MINIO_PUBLIC_URL and sign in with Keycloak realm data-team."
