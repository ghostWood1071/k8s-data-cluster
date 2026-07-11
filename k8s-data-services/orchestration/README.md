# Airflow Orchestration

This directory owns the Airflow deployment in namespace `orchestration`.

It does not deploy Keycloak, Spark, OpenMetadata, Longhorn, or ingress-nginx.
Those services are dependencies only.

## Current Architecture

- Helm release: `airflow`
- Namespace: `orchestration`
- Executor: `KubernetesExecutor`
- Internal URL: `http://airflow.k8s.tailnet:30296`
- Public URL: `https://airflow.datalabutehy.com`
- OIDC provider: Keycloak realm `data-team`
- Public Keycloak issuer: `https://keycloak.datalabutehy.com/realms/data-team`
- Internal Keycloak realm URL: `http://keycloak-service.keycloak.svc.cluster.local:8080/realms/data-team`
- Spark task namespace: `compute`
- Spark Airflow connection id: `spark_k8s`

## Files To Keep

Deployment:

- `restart-airflow-http.sh`: safely upgrades/restarts the existing Helm release.
- `values-keycloak-only-http.yaml`: Airflow web/ingress/OIDC overlay.
- `values-airflow-custom-image.yaml`: optional image overlay for the patched Airflow image.
- `storage.yaml`: existing PostgreSQL PVC.
- `postgres-nodeport.yaml`: optional NodePort for Airflow PostgreSQL access.
- `role-binding.yaml`: grants the Airflow worker service account access to Spark RBAC in namespace `compute`.
- `ingress-nginx-forwarded-headers.yaml`: ingress-nginx forwarded header config required behind Cloudflare Tunnel.

Custom image:

- `Dockerfile`: builds the Airflow image with Java, Spark/dbt dependencies, jars, and Airflow runtime patches.
- `requirements.txt`: Python packages installed into the custom image.
- `build-airflow-custom-image.sh`: local helper for building the image.
- `airflow-patches/airflow/utils/cli.py`: targeted Airflow `2.10.3` patch for DB-only DAG task execution.
- `create_spark_k8s_connection.py`: idempotently recreates the `spark_k8s` Airflow connection.

JSON-to-DB DAG runtime:

- `json_raw_sql_compiler.py`: compiles workflow JSON into Airflow metadata DB rows.
- `json-sql-compiler/`: runtime code mounted into Airflow DAGs/PYTHONPATH.
- `README_Json_To_DB_AIRFLOW.md`: details for the JSON-to-DB DAG mechanism.

Diagnostics:

- `test_airflow_keycloak_login.py`: optional end-to-end Keycloak login check.

## Standard Restart

Run from the master node or a machine with `kubectl`, `helm`, and cluster access:

```bash
cd k8s-data-services/orchestration
chmod +x restart-airflow-http.sh
./restart-airflow-http.sh
```

If `airflow-keycloak` does not exist yet:

```bash
read -s -p "Keycloak client secret: " KEYCLOAK_CLIENT_SECRET
echo
export KEYCLOAK_CLIENT_SECRET
./restart-airflow-http.sh
unset KEYCLOAK_CLIENT_SECRET
```

The script:

- verifies the existing Helm release exists;
- applies only `storage.yaml` and `postgres-nodeport.yaml`;
- creates required Airflow secrets if missing;
- reuses the currently installed chart version;
- applies `values-keycloak-only-http.yaml`;
- removes stale NGINX basic-auth annotations from Airflow ingress.

It intentionally refuses to install a brand-new release. That avoids accidentally replacing the
running image/chart with an unknown version.

## Deploy With Custom Image

The custom image is needed when DB-only DAG task pods must load DAG definitions from the Airflow
metadata database. The image contains a targeted patch for Airflow CLI behavior when `subdir` is
`DAGS_FOLDER/db-json:<path>`.

Build:

```bash
cd k8s-data-services/orchestration
IMAGE_REPOSITORY=ghostwood/airflow IMAGE_TAG=2.10.3-dbdag ./build-airflow-custom-image.sh
```

Recommended: push the image to a registry available to every Kubernetes node.

```bash
docker tag ghostwood/airflow:2.10.3-dbdag <registry>/airflow:2.10.3-dbdag
docker push <registry>/airflow:2.10.3-dbdag
```

If there is no registry, import the image into `containerd` on every node:

```bash
sudo docker save ghostwood/airflow:2.10.3-dbdag -o /tmp/airflow-2.10.3-dbdag.tar
sudo ctr -n k8s.io images import /tmp/airflow-2.10.3-dbdag.tar

scp /tmp/airflow-2.10.3-dbdag.tar slave01:/tmp/
scp /tmp/airflow-2.10.3-dbdag.tar slave02:/tmp/
ssh slave01 "echo 'Hduser@123' | sudo -S ctr -n k8s.io images import /tmp/airflow-2.10.3-dbdag.tar"
ssh slave02 "echo 'Hduser@123' | sudo -S ctr -n k8s.io images import /tmp/airflow-2.10.3-dbdag.tar"
```

Deploy with the extra image overlay:

```bash
EXTRA_VALUES_FILES=values-airflow-custom-image.yaml ./restart-airflow-http.sh
```

After rollout, ensure the Spark connection exists:

```bash
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- \
  python /opt/airflow/scripts/create_spark_k8s_connection.py
```

## Public SSO Through Cloudflare Tunnel

Cloudflare Tunnel should route the public host to the internal ingress:

```yaml
ingress:
  - hostname: airflow.datalabutehy.com
    service: http://airflow.k8s.tailnet:30296
  - service: http_status:404
```

Do not override `Host` to `airflow.k8s.tailnet` for the public route. The browser-facing host must
remain `airflow.datalabutehy.com` so Airflow, Keycloak redirect URIs, and OAuth callbacks agree.

The ingress-nginx controller must preserve forwarded headers:

```bash
kubectl apply -f ingress-nginx-forwarded-headers.yaml
kubectl rollout restart deployment/ingress-nginx-controller -n load-balancer
```

Keycloak client `airflow` in realm `data-team` needs:

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

Expected:

- Airflow pods are `Running`.
- Public response does not include `WWW-Authenticate: Basic`.
- Login redirects to Keycloak public issuer.
- `spark_k8s` host is `k8s://https://kubernetes.default.svc`.

## Cleanup Policy

Do not keep generated Helm snapshots in this directory. `restart-airflow-http.sh` writes backups to
`/tmp` by default.

Do not patch Airflow containers by hand. Runtime patching is not persistent and can break scheduler
parsing. Use the custom image path instead.
