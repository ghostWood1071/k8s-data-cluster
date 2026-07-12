# Deploy Airflow To Kubernetes

This folder owns the Airflow deployment in namespace `orchestration`.

It does not deploy Keycloak, Spark, OpenMetadata, Longhorn, or ingress-nginx.
Those services are dependencies.

## Files

- `restart-airflow-http.sh`: upgrades/restarts the existing Helm release safely.
- `values-keycloak-only-http.yaml`: public/internal Airflow ingress and Keycloak OIDC overlay.
- `values-airflow-custom-image.yaml`: custom image and JSON-SQL runtime overlay.
- `storage.yaml`: existing PostgreSQL PVC.
- `postgres-nodeport.yaml`: optional NodePort for Airflow PostgreSQL access.
- `role-binding.yaml`: grants Airflow worker access to Spark RBAC in namespace `compute`.
- `ingress-nginx-forwarded-headers.yaml`: forwarded header config for Cloudflare Tunnel.
- `test_airflow_keycloak_login.py`: optional browser-level login diagnostic.

## Prerequisites

- Helm release `airflow` already exists in namespace `orchestration`.
- StorageClass `longhorn` exists.
- Custom Airflow image is built and pushed if using `values-airflow-custom-image.yaml`.
- Keycloak client `airflow` exists in realm `data-team`.

## Standard Restart

```bash
cd k8s-data-services/orchestration/deploy-k8s
chmod +x restart-airflow-http.sh
./restart-airflow-http.sh
```

If secret `airflow-keycloak` does not exist yet:

```bash
read -s -p "Keycloak client secret: " KEYCLOAK_CLIENT_SECRET
echo
export KEYCLOAK_CLIENT_SECRET
./restart-airflow-http.sh
unset KEYCLOAK_CLIENT_SECRET
```

The script:

- verifies release `airflow` already exists;
- applies only Airflow-owned resources from this folder;
- creates required Airflow secrets if missing;
- reuses the installed chart version;
- removes stale NGINX basic-auth annotations from Airflow ingress.

## Deploy With Custom Image

Build and push the image first:

```bash
cd ../build-image
IMAGE_REPOSITORY=ghostwood/airflow IMAGE_TAG=2.10.3-dbdag ./build-airflow-custom-image.sh
docker push ghostwood/airflow:2.10.3-dbdag
```

Then deploy:

```bash
cd ../deploy-k8s
EXTRA_VALUES_FILES=values-airflow-custom-image.yaml ./restart-airflow-http.sh
```

The custom image overlay sets:

```text
defaultAirflowRepository=ghostwood/airflow
defaultAirflowTag=2.10.3-dbdag
PYTHONPATH=/opt/airflow/json-sql-compiler:/opt/airflow/dags/json-sql-compiler:/opt/airflow/config
JSON_SQL_RUNTIME_BOOTSTRAP=/opt/airflow/json-sql-compiler/runtime_bootstrap.py
```

## Spark Connection

After rollout, ensure the Airflow connection exists:

```bash
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- \
  python /opt/airflow/scripts/create_spark_k8s_connection.py
```

Expected values:

- `conn_type`: `spark`
- `host`: `k8s://https://kubernetes.default.svc`
- `extra.deploy-mode`: `cluster`
- `extra.spark-binary`: `spark-submit`
- `extra.namespace`: `compute`

## Public SSO Through Cloudflare Tunnel

Cloudflare Tunnel should route the public host to the internal ingress:

```yaml
ingress:
  - hostname: airflow.datalabutehy.com
    service: http://airflow.k8s.tailnet:30296
  - service: http_status:404
```

Do not override `Host` to `airflow.k8s.tailnet` for the public route. The browser-facing
host must remain `airflow.datalabutehy.com`.

Apply forwarded headers if needed:

```bash
kubectl apply -f ingress-nginx-forwarded-headers.yaml
kubectl rollout restart deployment/ingress-nginx-controller -n load-balancer
```

Keycloak client `airflow` needs:

- Valid redirect URI: `https://airflow.datalabutehy.com/oauth-authorized/keycloak`
- Web origin: `https://airflow.datalabutehy.com`
- Client roles mapped to Airflow roles:
  - `airflow_admin`
  - `airflow_op`
  - `airflow_user`
  - `airflow_viewer`
  - `airflow_public`

## Verify

```bash
helm status airflow -n orchestration
kubectl get pods,svc,ingress,pvc -n orchestration -o wide
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow version
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow dags list
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow connections get spark_k8s
curl -kI https://airflow.datalabutehy.com
```

For DB-only JSON-SQL DAGs, check task logs for:

```text
task_instance_state_update: ... -> running
task_instance_state_update: ... -> success
```

## Cleanup

Do not keep generated Helm snapshots in this folder. `restart-airflow-http.sh`
writes backups to `/tmp` by default.

Do not patch Airflow containers by hand for permanent fixes. Put runtime changes
in `../build-image/`, build a new image, then deploy that image here.
