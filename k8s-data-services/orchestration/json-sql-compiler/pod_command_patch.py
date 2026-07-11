import json
import os
import shlex
from pathlib import Path

RUNTIME_BOOTSTRAP = "/opt/airflow/dags/json-sql-compiler/runtime_bootstrap.py"
CONFIG_DIR = os.getenv("JSON_SQL_CONFIG_DIR", "/opt/airflow/dags/workflow")


def _extract_task_run(container):
    command = list(container.command or [])
    args = list(container.args or [])
    tokens = command + args
    raw = " ".join(str(x) for x in tokens)

    # Case 1:
    # ["airflow","tasks","run", dag_id, task_id, run_id, ...]
    for i in range(len(tokens) - 5):
        if tokens[i:i+3] == ["airflow", "tasks", "run"]:
            return raw, tokens[i+3], tokens[i+4], tokens[i+5]

    # Case 2: command packed inside bash -c string
    try:
        split_tokens = shlex.split(raw)
    except Exception:
        split_tokens = raw.split()

    for i in range(len(split_tokens) - 5):
        if split_tokens[i:i+3] == ["airflow", "tasks", "run"]:
            return raw, split_tokens[i+3], split_tokens[i+4], split_tokens[i+5]

    return raw, None, None, None


def _is_json_sql_dag(dag_id, raw):
    if not dag_id:
        return False

    if "db-json:" in raw or "DAGS_FOLDER/db-json:" in raw:
        return True

    config_dir = Path(CONFIG_DIR)
    if not config_dir.exists():
        return False

    for p in config_dir.rglob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("dag_id") == dag_id:
                return True
        except Exception:
            pass

    return False


def patch_pod(pod):
    try:
        for container in pod.spec.containers or []:
            raw, dag_id, task_id, run_id = _extract_task_run(container)

            print("[JSON-SQL POD PATCH] raw:", raw)
            print("[JSON-SQL POD PATCH] dag_id:", dag_id)
            print("[JSON-SQL POD PATCH] task_id:", task_id)
            print("[JSON-SQL POD PATCH] run_id:", run_id)

            if not _is_json_sql_dag(dag_id, raw):
                print("[JSON-SQL POD PATCH] skip non json-sql pod")
                continue

            cmd = (
                f"python {shlex.quote(RUNTIME_BOOTSTRAP)} "
                f"--dag-id {shlex.quote(dag_id)} "
                f"--task-id {shlex.quote(task_id)} "
                f"--run-id {shlex.quote(run_id)} "
                "--execute"
            )

            container.command = ["bash", "-lc"]
            container.args = [cmd]

            pod.metadata.annotations = pod.metadata.annotations or {}
            pod.metadata.annotations["json-sql/patched"] = "true"
            pod.metadata.annotations["json-sql/dag_id"] = dag_id
            pod.metadata.annotations["json-sql/task_id"] = task_id
            pod.metadata.annotations["json-sql/run_id"] = run_id

            print("[JSON-SQL POD PATCH] PATCHED:", cmd)

        return pod

    except Exception as e:
        print("[JSON-SQL POD PATCH] ERROR:", repr(e))
        return pod
