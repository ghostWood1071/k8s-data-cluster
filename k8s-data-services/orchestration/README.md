# Airflow Orchestration

This directory is split by responsibility:

- `build-image/`: build the patched Airflow image used by DB-only JSON-SQL DAGs.
- `deploy-k8s/`: deploy or restart the Airflow Helm release in namespace `orchestration`.

Use `build-image/` first when Airflow runtime code or Airflow patches change. Use
`deploy-k8s/` when applying the image and Kubernetes/Helm configuration to the cluster.

## Recommended Flow

```bash
cd k8s-data-services/orchestration/build-image
IMAGE_REPOSITORY=ghostwood/airflow IMAGE_TAG=2.10.3-dbdag ./build-airflow-custom-image.sh
docker push ghostwood/airflow:2.10.3-dbdag

cd ../deploy-k8s
EXTRA_VALUES_FILES=values-airflow-custom-image.yaml ./restart-airflow-http.sh
```

## Current Runtime Model

- Helm release: `airflow`
- Namespace: `orchestration`
- Executor: `KubernetesExecutor`
- Airflow public URL: `https://airflow.datalabutehy.com`
- Airflow internal URL: `http://airflow.k8s.tailnet:30296`
- Spark namespace: `compute`
- Spark connection id: `spark_k8s`

The custom image packages the JSON-SQL runtime under:

```text
/opt/airflow/json-sql-compiler/
```

The deploy overlay sets `PYTHONPATH` and `JSON_SQL_RUNTIME_BOOTSTRAP` so Kubernetes
task pods use that image-packaged runtime instead of relying on manual edits inside
running containers.
