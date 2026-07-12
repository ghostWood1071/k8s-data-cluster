# Build Patched Airflow Image

This folder contains everything needed to build the Airflow image used by the
`orchestration` namespace.

## What Is Packaged

- `Dockerfile`: installs Java, Spark dependencies, Airflow `2.10.3`, jars, and runtime patches.
- `requirements.txt`: Python dependencies for Airflow providers and auth/runtime support.
- `airflow-patches/`: targeted Airflow source patches.
- `json-sql-compiler/`: DB-only DAG runtime used by Kubernetes task pods.
- `json_raw_sql_compiler.py`: helper that writes JSON workflows into Airflow metadata DB.
- `create_spark_k8s_connection.py`: idempotent helper for the `spark_k8s` connection.

The image copies the JSON-SQL runtime to:

```text
/opt/airflow/json-sql-compiler/
```

This means the runtime patch is built into the image. Avoid editing the same files
manually inside running pods except for short debugging.

## Runtime Fixes Included

- Airflow CLI patch for `DAGS_FOLDER/db-json:<path>` task execution.
- JSON-SQL pod mutation hook.
- `runtime_bootstrap.py` updates TaskInstance state to `running`, `success`, or
  `failed`, fixing pods that finish while Airflow remains stuck in `queued`.
- Default Spark Kubernetes settings for DB-only DAGs:
  - `spark.kubernetes.container.image=ghostwood/spark-engine:1.0.1`
  - `spark.kubernetes.authenticate.driver.serviceAccountName=spark`

Both defaults can be overridden at deploy time:

```yaml
extraEnv: |
  - name: JSON_SQL_SPARK_CONTAINER_IMAGE
    value: your-registry/spark-engine:tag
  - name: JSON_SQL_SPARK_SERVICE_ACCOUNT
    value: spark
```

## Build

```bash
cd k8s-data-services/orchestration/build-image
IMAGE_REPOSITORY=ghostwood/airflow IMAGE_TAG=2.10.3-dbdag ./build-airflow-custom-image.sh
```

The script builds with this folder as the Docker context, so every file needed by
the image is local to `build-image/`.

## Push

```bash
docker push ghostwood/airflow:2.10.3-dbdag
```

Every Kubernetes node must be able to pull this image. If Docker Hub is not
available from the cluster, import the image into each node's container runtime.

## Verify Image Locally

```bash
docker run --rm ghostwood/airflow:2.10.3-dbdag \
  python -m py_compile \
  /opt/airflow/json-sql-compiler/runtime_bootstrap.py
```

## After Build

Deploy the image from:

```bash
cd ../deploy-k8s
EXTRA_VALUES_FILES=values-airflow-custom-image.yaml ./restart-airflow-http.sh
```
