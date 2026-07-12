# JSON-to-DB Airflow DAGs

This document covers the DB-only DAG mechanism used by the Airflow deployment in
namespace `orchestration`.

## Goal

Instead of writing a Python DAG file for each workflow, `json_raw_sql_compiler.py`
reads a workflow JSON definition and writes Airflow metadata records directly.

At runtime, Kubernetes task pods execute a small bootstrap script that recreates
the right operator from serialized metadata and runs it.

## Flow

```text
workflow JSON
  -> json_raw_sql_compiler.py
  -> Airflow metadata DB
     - dag
     - serialized_dag
     - dag_tag
  -> Airflow scheduler
  -> KubernetesExecutor task pod
  -> pod_mutation_hook
  -> runtime_bootstrap.py
  -> SparkSubmitOperator
  -> spark-submit on Kubernetes
```

## Runtime Files

These files are packaged into the custom Airflow image under:

```text
/opt/airflow/json-sql-compiler/
```

The deploy overlay also keeps `/opt/airflow/dags/json-sql-compiler` in
`PYTHONPATH` as a fallback for temporary debugging, but the durable source of
truth is the custom image.

Legacy DAG-volume location:

```text
/opt/airflow/dags/json-sql-compiler/
```

Required files:

- `airflow_local_settings.py`
- `pod_command_patch.py`
- `runtime_bootstrap.py`

If you temporarily place runtime files on the DAG volume, use this layout:

```text
/opt/airflow/dags/
  .airflowignore
  json-sql-compiler/
    airflow_local_settings.py
    pod_command_patch.py
    runtime_bootstrap.py
```

The `.airflowignore` file should exclude runtime helper code from normal DAG parsing:

```text
json-sql-compiler/.*
json-sql-compiler/*
__pycache__
.*\.pyc
```

## Airflow Requirements

The Helm values used by the running release must include:

```yaml
extraEnv: |
  - name: PYTHONPATH
    value: /opt/airflow/json-sql-compiler:/opt/airflow/dags/json-sql-compiler:/opt/airflow/config

  - name: AIRFLOW__KUBERNETES_EXECUTOR__POD_MUTATION_HOOK
    value: airflow_local_settings.pod_mutation_hook

  - name: JSON_SQL_RUNTIME_BOOTSTRAP
    value: /opt/airflow/json-sql-compiler/runtime_bootstrap.py
```

The custom Airflow image is recommended because task commands can receive a
serialized file location like:

```text
DAGS_FOLDER/db-json:<dag-path>
```

The image patch in `airflow-patches/airflow/utils/cli.py` makes Airflow load
those DAGs from the metadata DB without changing scheduler DAG discovery.

## Spark Connection

DB-only Spark tasks use Airflow connection:

```text
spark_k8s
```

Create or refresh it after deploy:

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

## Compile A Workflow JSON

Run the compiler from a machine or pod that can reach the Airflow metadata DB.
Use `--help` to see the current arguments:

```bash
python json_raw_sql_compiler.py --help
```

The compiler writes directly to Airflow metadata tables, so review the target DB
connection before running it.

## Verify

```bash
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow dags list
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow connections get spark_k8s
kubectl get pods -n orchestration --sort-by=.metadata.creationTimestamp
```

For a triggered DB-only DAG, the Kubernetes task pod should have annotation:

```text
json-sql/patched=true
```

and its command should execute:

```text
python /opt/airflow/json-sql-compiler/runtime_bootstrap.py --dag-id ... --task-id ... --run-id ... --execute
```

## Do Not Use

Do not patch every `DagBag(...)` call in running containers. That breaks normal
scheduler/webserver DAG discovery and disappears on pod restart.

Use the custom image patch instead.
