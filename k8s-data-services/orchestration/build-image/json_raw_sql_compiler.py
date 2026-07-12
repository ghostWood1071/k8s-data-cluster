#!/usr/bin/env python3
"""
json_raw_sql_compiler.py

Raw SQL compiler for DB-only Airflow DAGs.

This file DOES NOT import Airflow.

Input:
  - Local workflow JSON files

Output:
  - Airflow metadata DB tables:
      dag
      serialized_dag
      dag_tag

Runtime design:
  - JSON is used only at compile time.
  - runtime_bootstrap.py should read task configuration from serialized_dag.data.
  - No workflow JSON needs to be copied into the Airflow PVC.
  - No custom workflow table is created.
  - No Airflow variable is used to store workflow JSON.

Supported workflow task shape:

{
  "task_id": "source2bronze_Orders_Retail3A",
  "operator": "SparkSubmitOperator",
  "params": {
    "application": "s3a://asset/spark-jobs/entry_point.py",
    "conn_id": "spark_k8s",
    "name": "source2bronze_Orders_Retail3A",
    "application_args": ["--job_asset_bucket", "asset"],
    "conf": {}
  },
  "downstream": ["bronze2silver_Orders_Retail3A"]
}
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


SPARK_TEMPLATE_FIELDS = [
    "application",
    "conf",
    "files",
    "py_files",
    "jars",
    "driver_class_path",
    "packages",
    "exclude_packages",
    "keytab",
    "principal",
    "proxy_user",
    "name",
    "application_args",
    "env_vars",
    "properties_file",
]


SUPPORTED_OPERATORS = {
    "SparkSubmitOperator": {
        "task_type": "SparkSubmitOperator",
        "task_module": "airflow.providers.apache.spark.operators.spark_submit",
        "ui_color": "#FF9933",
        "template_fields": SPARK_TEMPLATE_FIELDS,
    }
}


# ============================================================
# Basic helpers
# ============================================================

def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://"):]
    if url.startswith("postgres+psycopg2://"):
        return "postgresql://" + url[len("postgres+psycopg2://"):]
    return url


def connect(db_url: str):
    return psycopg2.connect(
        normalize_db_url(db_url),
        cursor_factory=RealDictCursor,
    )


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def stable_json(data: Any) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_dag_hash(serialized_data: dict[str, Any]) -> str:
    return hashlib.md5(stable_json(serialized_data).encode("utf-8")).hexdigest()


def stable_fileloc_hash(fileloc: str) -> int:
    """
    Airflow stores fileloc_hash as BIGINT.

    The exact Airflow internal hash is not required for this DB-only DAG
    approach. We only need a deterministic signed-safe BIGINT for the
    pseudo fileloc.
    """
    h = hashlib.sha1(fileloc.encode("utf-8")).hexdigest()
    return int(h[:15], 16)


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}

    return bool(value)


def parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    try:
        return int(value)
    except Exception:
        return default


def parse_retry_delay_seconds(value: Any, default: float = 300.0) -> float:
    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        raw = value.strip()

        try:
            return float(raw)
        except Exception:
            pass

        if not raw:
            return default

        unit = raw[-1].lower()
        number = raw[:-1]

        try:
            n = float(number)
            if unit == "s":
                return n
            if unit == "m":
                return n * 60
            if unit == "h":
                return n * 3600
            if unit == "d":
                return n * 86400
        except Exception:
            pass

    return default


def parse_start_date_to_timestamp(value: Any) -> float:
    if value is None:
        return dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp()

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        raw = value.strip()

        # Example: 2025-01-01T00:00:00+00:00 or 2025-01-01T00:00:00Z
        try:
            parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc).timestamp()
        except Exception:
            pass

        # Example: 2025-01-01
        try:
            parsed = dt.datetime.strptime(raw, "%Y-%m-%d")
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.timestamp()
        except Exception:
            pass

    raise ValueError(f"Invalid start_date: {value!r}")


def listify(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        if not value:
            return []
        return [value]

    if isinstance(value, list):
        return [str(x) for x in value]

    if isinstance(value, tuple):
        return [str(x) for x in value]

    return [str(value)]


# ============================================================
# DB helpers
# ============================================================

def get_table_columns(conn, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        return {r["column_name"] for r in cur.fetchall()}


def adapt_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return Json(value)
    return value


def upsert_row(
    conn,
    table_name: str,
    row: dict[str, Any],
    conflict_cols: list[str],
) -> None:
    table_cols = get_table_columns(conn, table_name)
    clean = {k: v for k, v in row.items() if k in table_cols}

    if not clean:
        raise RuntimeError(f"No valid columns for table {table_name}")

    cols = list(clean.keys())
    placeholders = [f"%({c})s" for c in cols]

    update_cols = [c for c in cols if c not in conflict_cols]

    if update_cols:
        update_sql = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
        sql = f"""
        INSERT INTO {table_name} ({", ".join(cols)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT ({", ".join(conflict_cols)})
        DO UPDATE SET {update_sql}
        """
    else:
        sql = f"""
        INSERT INTO {table_name} ({", ".join(cols)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT ({", ".join(conflict_cols)})
        DO NOTHING
        """

    params = {k: adapt_value(v) for k, v in clean.items()}

    with conn.cursor() as cur:
        cur.execute(sql, params)


def replace_dag_tags(conn, dag_id: str, tags: list[str]) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dag_tag WHERE dag_id = %s", (dag_id,))

        for tag in tags:
            cur.execute(
                """
                INSERT INTO dag_tag (name, dag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (tag, dag_id),
            )


# ============================================================
# Workflow readers
# ============================================================

def find_workflow_files(path: str | Path, recursive: bool) -> list[Path]:
    p = Path(path)

    if p.is_file():
        if p.suffix.lower() != ".json":
            raise RuntimeError(f"Config file is not JSON: {p}")
        return [p]

    if not p.exists():
        raise RuntimeError(f"Path does not exist: {p}")

    if not p.is_dir():
        raise RuntimeError(f"Path is not a file or directory: {p}")

    files = sorted(p.rglob("*.json") if recursive else p.glob("*.json"))
    return [f for f in files if f.is_file()]


def get_default_args(workflow: dict[str, Any]) -> dict[str, Any]:
    value = workflow.get("default_args")
    return value if isinstance(value, dict) else {}


def get_owner(workflow: dict[str, Any]) -> str:
    return (
        workflow.get("owner")
        or get_default_args(workflow).get("owner")
        or "airflow"
    )


def get_email(workflow: dict[str, Any]) -> list[str]:
    value = workflow.get("email", get_default_args(workflow).get("email", []))

    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return [str(x) for x in value]

    return []


def get_retries(workflow: dict[str, Any]) -> int:
    value = workflow.get("retries", get_default_args(workflow).get("retries", 0))
    return parse_int(value, default=0)


def get_retry_delay_seconds(workflow: dict[str, Any]) -> float:
    value = workflow.get("retry_delay", get_default_args(workflow).get("retry_delay", 300))
    return parse_retry_delay_seconds(value, default=300.0)


def get_tags(workflow: dict[str, Any]) -> list[str]:
    tags = workflow.get("tags", [])

    if tags is None:
        return []

    if isinstance(tags, str):
        return [tags]

    if isinstance(tags, list):
        return [str(t) for t in tags]

    return []


def get_tasks(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = workflow.get("tasks")

    if not isinstance(tasks, list) or not tasks:
        raise RuntimeError(f"Workflow {workflow.get('dag_id')} must contain non-empty tasks list")

    return tasks


def get_task_id(task: dict[str, Any]) -> str:
    task_id = task.get("task_id")

    if not task_id:
        raise RuntimeError(f"Task missing task_id: {task}")

    return str(task_id)


def get_task_params(task: dict[str, Any]) -> dict[str, Any]:
    """
    Supports JSON shapes:

    {
      "task_id": "...",
      "operator": "SparkSubmitOperator",
      "params": {
        "application": "...",
        "conn_id": "...",
        "application_args": [],
        "conf": {}
      },
      "downstream": []
    }

    Also supports:
      task_params
      operator_params
      operator_kwargs
      spark
      spark_submit
      spark_config
      config
    """
    container_keys = {
        "params",
        "task_params",
        "operator_params",
        "operator_kwargs",
        "spark",
        "spark_submit",
        "spark_config",
        "config",
    }

    merged: dict[str, Any] = {}

    for k, v in task.items():
        if k not in container_keys:
            merged[k] = v

    def merge_dict(d: dict[str, Any]) -> None:
        for k, v in d.items():
            if k in container_keys and isinstance(v, dict):
                merge_dict(v)
            else:
                merged[k] = v

    for key in container_keys:
        value = task.get(key)
        if isinstance(value, dict):
            merge_dict(value)

    return merged


def get_param(params: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in params and params[name] is not None:
            return params[name]
    return default


def get_operator_name(task: dict[str, Any]) -> str:
    params = get_task_params(task)

    op = (
        task.get("operator")
        or task.get("operator_class")
        or task.get("type")
        or params.get("operator")
        or params.get("operator_class")
        or "SparkSubmitOperator"
    )

    return str(op)


def get_application(params: dict[str, Any]) -> Any:
    return get_param(
        params,
        "application",
        "application_file",
        "main_application_file",
        "main_file",
        "app",
        "job_file",
        "entrypoint",
        "entry_point",
    )


def get_application_args(params: dict[str, Any]) -> list[Any]:
    value = get_param(
        params,
        "application_args",
        "app_args",
        "args",
        "arguments",
        default=[],
    )

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        return [value]

    if isinstance(value, tuple):
        return list(value)

    return [value]


def get_spark_conf(params: dict[str, Any]) -> dict[str, Any]:
    value = get_param(
        params,
        "conf",
        "spark_conf",
        "spark_config",
        "sparkConf",
        default={},
    )

    if value is None:
        return {}

    if not isinstance(value, dict):
        raise RuntimeError("Spark conf must be a dict")

    return value


def get_explicit_upstreams(task: dict[str, Any]) -> list[str]:
    params = get_task_params(task)

    candidates = [
        task.get("depends_on"),
        task.get("depend_on"),
        task.get("dependencies"),
        task.get("upstream"),
        task.get("upstreams"),
        task.get("upstream_task_ids"),
        params.get("depends_on"),
        params.get("depend_on"),
        params.get("dependencies"),
        params.get("upstream"),
        params.get("upstreams"),
        params.get("upstream_task_ids"),
    ]

    result: list[str] = []

    for candidate in candidates:
        for item in listify(candidate):
            if item not in result:
                result.append(item)

    return result


def get_explicit_downstreams(task: dict[str, Any]) -> list[str]:
    params = get_task_params(task)

    candidates = [
        task.get("downstream"),
        task.get("downstreams"),
        task.get("downstream_task_ids"),
        task.get("next"),
        params.get("downstream"),
        params.get("downstreams"),
        params.get("downstream_task_ids"),
        params.get("next"),
    ]

    result: list[str] = []

    for candidate in candidates:
        for item in listify(candidate):
            if item not in result:
                result.append(item)

    return result


def build_dependency_map(
    tasks: list[dict[str, Any]],
    sequential_if_no_deps: bool = False,
) -> dict[str, list[str]]:
    task_ids = [get_task_id(t) for t in tasks]
    known = set(task_ids)

    downstreams: dict[str, set[str]] = {tid: set() for tid in task_ids}
    has_any_dependency = False

    for task in tasks:
        tid = get_task_id(task)

        for down in get_explicit_downstreams(task):
            if down not in known:
                raise RuntimeError(f"Unknown downstream task_id {down!r} referenced by {tid!r}")
            downstreams[tid].add(down)
            has_any_dependency = True

        for up in get_explicit_upstreams(task):
            if up not in known:
                raise RuntimeError(f"Unknown upstream task_id {up!r} referenced by {tid!r}")
            downstreams[up].add(tid)
            has_any_dependency = True

    if sequential_if_no_deps and not has_any_dependency and len(task_ids) > 1:
        for a, b in zip(task_ids, task_ids[1:]):
            downstreams[a].add(b)

    return {tid: sorted(list(values)) for tid, values in downstreams.items()}


# ============================================================
# Validation
# ============================================================

def validate_workflow(workflow: dict[str, Any], source: Path) -> None:
    dag_id = workflow.get("dag_id")

    if not dag_id:
        raise RuntimeError(f"Missing dag_id in {source}")

    tasks = get_tasks(workflow)

    seen_task_ids: set[str] = set()

    for task in tasks:
        tid = get_task_id(task)

        if tid in seen_task_ids:
            raise RuntimeError(f"Duplicate task_id={tid!r} in dag_id={dag_id!r}")

        seen_task_ids.add(tid)

        operator = get_operator_name(task)

        if operator not in SUPPORTED_OPERATORS:
            raise RuntimeError(
                f"Unsupported operator {operator!r} in task {tid!r}. "
                f"Supported operators: {list(SUPPORTED_OPERATORS.keys())}"
            )

        params = get_task_params(task)

        if not get_application(params):
            raise RuntimeError(
                f"Task {tid!r} missing Spark application. "
                f"Use params.application or task_params.application"
            )

        raw_args = get_param(params, "application_args", "app_args", "args", "arguments")

        if raw_args is not None and not isinstance(raw_args, (list, str, tuple)):
            raise RuntimeError(
                f"Task {tid!r} application_args/app_args/args must be list, tuple, or string"
            )

        raw_conf = get_param(params, "conf", "spark_conf", "spark_config", "sparkConf")

        if raw_conf is not None and not isinstance(raw_conf, dict):
            raise RuntimeError(
                f"Task {tid!r} conf/spark_conf/spark_config must be a dict"
            )

    build_dependency_map(tasks, sequential_if_no_deps=False)


def validate_all(files: list[Path]) -> list[dict[str, Any]]:
    workflows: list[dict[str, Any]] = []
    seen_dag_ids: dict[str, Path] = {}

    for file in files:
        workflow = load_json(file)
        validate_workflow(workflow, file)

        dag_id = workflow["dag_id"]

        if dag_id in seen_dag_ids:
            raise RuntimeError(
                f"Duplicate dag_id={dag_id!r}\n"
                f"  - {seen_dag_ids[dag_id]}\n"
                f"  - {file}"
            )

        seen_dag_ids[dag_id] = file
        workflows.append(workflow)

    return workflows


# ============================================================
# Serialized DAG builder
# ============================================================

def build_timetable(workflow: dict[str, Any]) -> dict[str, Any]:
    schedule = workflow.get("schedule") or workflow.get("schedule_interval")
    timezone_name = workflow.get("timezone") or "UTC"

    if schedule:
        return {
            "__type": "airflow.timetables.interval.CronDataIntervalTimetable",
            "__var": {
                "expression": str(schedule),
                "timezone": timezone_name,
            },
        }

    return {
        "__type": "airflow.timetables.simple.NullTimetable",
        "__var": {},
    }


def build_default_args(workflow: dict[str, Any]) -> dict[str, Any]:
    retry_delay = get_retry_delay_seconds(workflow)

    return {
        "__var": {
            "owner": get_owner(workflow),
            "email": get_email(workflow),
            "retries": get_retries(workflow),
            "retry_delay": {
                "__var": retry_delay,
                "__type": "timedelta",
            },
        },
        "__type": "dict",
    }


def build_task_group(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    children = {}

    for task in tasks:
        tid = get_task_id(task)
        children[tid] = ["operator", tid]

    return {
        "_group_id": None,
        "prefix_group_id": True,
        "tooltip": "",
        "ui_color": "CornflowerBlue",
        "ui_fgcolor": "#000",
        "children": children,
        "upstream_group_ids": [],
        "downstream_group_ids": [],
        "upstream_task_ids": [],
        "downstream_task_ids": [],
    }


def build_serialized_task(
    workflow: dict[str, Any],
    task: dict[str, Any],
    downstream_task_ids: list[str],
) -> dict[str, Any]:
    tid = get_task_id(task)
    params = get_task_params(task)

    operator = get_operator_name(task)
    op_meta = SUPPORTED_OPERATORS[operator]

    workflow_retry_delay = get_retry_delay_seconds(workflow)

    retry_delay = parse_retry_delay_seconds(
        get_param(params, "retry_delay", default=workflow_retry_delay),
        default=workflow_retry_delay,
    )

    retries = parse_int(
        get_param(params, "retries", default=get_retries(workflow)),
        default=get_retries(workflow),
    )

    email = get_param(params, "email", default=get_email(workflow))

    if isinstance(email, str):
        email = [email]

    if not isinstance(email, list):
        email = []

    owner = get_param(params, "owner", default=get_owner(workflow))

    application = get_application(params)
    conf = get_spark_conf(params)

    conn_id = get_param(params, "conn_id", default="spark_k8s")
    name = get_param(params, "name", default=tid)
    application_args = get_application_args(params)

    task_var = {
        "on_failure_fail_dagrun": parse_bool(
            get_param(params, "on_failure_fail_dagrun"),
            default=False,
        ),
        "task_id": tid,
        "template_ext": get_param(params, "template_ext", default=[]),
        "downstream_task_ids": downstream_task_ids,
        "retry_delay": retry_delay,
        "_needs_expansion": False,
        "email": email,
        "retries": retries,
        "pool": get_param(params, "pool", default="default_pool"),
        "start_from_trigger": False,
        "ui_color": get_param(params, "ui_color", default=op_meta["ui_color"]),
        "template_fields": op_meta["template_fields"],
        "owner": owner,
        "is_setup": False,
        "weight_rule": get_param(params, "weight_rule", default="downstream"),
        "_log_config_logger_name": "airflow.task.operators",
        "is_teardown": False,
        "template_fields_renderers": get_param(params, "template_fields_renderers", default={}),
        "ui_fgcolor": get_param(params, "ui_fgcolor", default="#000"),
        "_task_type": op_meta["task_type"],
        "_task_module": op_meta["task_module"],
        "_is_empty": False,
        "start_trigger_args": None,

        # Runtime reads these fields from serialized_dag.data.
        "conn_id": conn_id,
        "_conn_id": conn_id,
        "application": application,
        "conf": conf,
        "name": name,
        "application_args": application_args,
    }

    optional_fields = [
        "files",
        "py_files",
        "jars",
        "driver_class_path",
        "packages",
        "exclude_packages",
        "keytab",
        "principal",
        "proxy_user",
        "env_vars",
        "properties_file",
    ]

    for field in optional_fields:
        if field in params:
            task_var[field] = params[field]

    return {
        "__var": task_var,
        "__type": "operator",
    }


def build_serialized_dag(
    workflow: dict[str, Any],
    fileloc_prefix: str,
    sequential_if_no_deps: bool,
) -> dict[str, Any]:
    dag_id = workflow["dag_id"]
    tasks = get_tasks(workflow)
    dependency_map = build_dependency_map(
        tasks,
        sequential_if_no_deps=sequential_if_no_deps,
    )

    fileloc = f"{fileloc_prefix.rstrip('/')}/{dag_id}"
    timezone_name = workflow.get("timezone") or "UTC"

    start_date_value = (
        workflow.get("start_date")
        or get_default_args(workflow).get("start_date")
    )

    start_date = parse_start_date_to_timestamp(start_date_value)

    serialized_tasks = []

    for task in tasks:
        tid = get_task_id(task)
        serialized_tasks.append(
            build_serialized_task(
                workflow=workflow,
                task=task,
                downstream_task_ids=dependency_map[tid],
            )
        )

    dag = {
        "timetable": build_timetable(workflow),
        "edge_info": workflow.get("edge_info") or {},
        "fileloc": fileloc,
        "default_args": build_default_args(workflow),
        "is_paused_upon_creation": parse_bool(
            workflow.get("is_paused_upon_creation"),
            default=False,
        ),
        "_description": workflow.get("description") or "",
        "_task_group": build_task_group(tasks),
        "start_date": start_date,
        "_dag_id": dag_id,
        "_processor_dags_folder": workflow.get("_processor_dags_folder") or "/opt/airflow/dags",
        "tags": get_tags(workflow),
        "timezone": timezone_name,
        "catchup": parse_bool(workflow.get("catchup"), default=False),
        "max_active_runs": parse_int(workflow.get("max_active_runs"), default=1),
        "tasks": serialized_tasks,
        "dag_dependencies": workflow.get("dag_dependencies") or [],
        "params": workflow.get("params") or [],
    }

    if workflow.get("max_active_tasks") is not None:
        dag["max_active_tasks"] = parse_int(workflow.get("max_active_tasks"), default=16)

    return {
        "__version": 1,
        "dag": dag,
    }


# ============================================================
# Airflow DB row builders
# ============================================================

def resolve_is_paused(workflow: dict[str, Any], unpause: bool) -> bool:
    if unpause:
        return False

    if "is_paused" in workflow:
        return parse_bool(workflow.get("is_paused"), default=True)

    if "is_paused_upon_creation" in workflow:
        return parse_bool(workflow.get("is_paused_upon_creation"), default=True)

    return True


def build_dag_row(
    workflow: dict[str, Any],
    serialized_data: dict[str, Any],
    fileloc: str,
    processor_subdir: str,
    unpause: bool,
) -> dict[str, Any]:
    schedule = workflow.get("schedule") or workflow.get("schedule_interval")

    return {
        "dag_id": workflow["dag_id"],
        "dag_display_name": workflow["dag_id"],
        "root_dag_id": None,
        "is_paused": resolve_is_paused(workflow, unpause=unpause),
        "is_subdag": False,
        "is_active": True,
        "last_parsed_time": now_utc(),
        "last_pickled": None,
        "last_expired": None,
        "scheduler_lock": None,
        "pickle_id": None,
        "fileloc": fileloc,
        "processor_subdir": processor_subdir,
        "owners": get_owner(workflow),
        "description": workflow.get("description") or "",
        "default_view": workflow.get("default_view") or "grid",
        "schedule_interval": json.dumps(schedule) if schedule is not None else None,
        "timetable_description": str(schedule) if schedule else None,
        "dataset_expression": None,
        "max_active_tasks": parse_int(workflow.get("max_active_tasks"), default=16),
        "max_active_runs": parse_int(workflow.get("max_active_runs"), default=1),
        "max_consecutive_failed_dag_runs": parse_int(
            workflow.get("max_consecutive_failed_dag_runs"),
            default=0,
        ),
        "has_task_concurrency_limits": False,
        "has_import_errors": False,
        "next_dagrun": None,
        "next_dagrun_data_interval_start": None,
        "next_dagrun_data_interval_end": None,
        "next_dagrun_create_after": None,
    }


def build_serialized_dag_row(
    workflow: dict[str, Any],
    serialized_data: dict[str, Any],
    fileloc: str,
    processor_subdir: str,
) -> dict[str, Any]:
    return {
        "dag_id": workflow["dag_id"],
        "fileloc": fileloc,
        "fileloc_hash": stable_fileloc_hash(fileloc),
        "data": serialized_data,
        "data_compressed": None,
        "last_updated": now_utc(),
        "dag_hash": stable_dag_hash(serialized_data),
        "processor_subdir": processor_subdir,
    }


# ============================================================
# Apply workflow
# ============================================================

def apply_workflow(
    conn,
    workflow: dict[str, Any],
    fileloc_prefix: str,
    processor_subdir: str,
    unpause: bool,
    sequential_if_no_deps: bool,
    emit_json_dir: str | None,
) -> None:
    dag_id = workflow["dag_id"]

    serialized_data = build_serialized_dag(
        workflow=workflow,
        fileloc_prefix=fileloc_prefix,
        sequential_if_no_deps=sequential_if_no_deps,
    )

    fileloc = serialized_data["dag"]["fileloc"]

    dag_row = build_dag_row(
        workflow=workflow,
        serialized_data=serialized_data,
        fileloc=fileloc,
        processor_subdir=processor_subdir,
        unpause=unpause,
    )

    serialized_row = build_serialized_dag_row(
        workflow=workflow,
        serialized_data=serialized_data,
        fileloc=fileloc,
        processor_subdir=processor_subdir,
    )

    if emit_json_dir:
        out_dir = Path(emit_json_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{dag_id}.serialized_dag.json"

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(serialized_data, f, indent=2, ensure_ascii=False)

        print("EMIT:", out_file)

    task_ids = [get_task_id(t) for t in get_tasks(workflow)]

    print("--------------------------------------------------")
    print("UPSERT DAG:", dag_id)
    print("fileloc:", fileloc)
    print("tasks:", task_ids)
    print("tags:", get_tags(workflow))

    upsert_row(conn, "dag", dag_row, ["dag_id"])
    upsert_row(conn, "serialized_dag", serialized_row, ["dag_id"])
    replace_dag_tags(conn, dag_id, get_tags(workflow))

    print("OK:", dag_id)


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Compile JSON workflows into Airflow metadata DB using raw SQL. No Airflow imports."
    )

    parser.add_argument(
        "--db-url",
        default=os.getenv("AIRFLOW_DB_URL") or os.getenv("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"),
        help="Airflow metadata DB URL. Or set AIRFLOW_DB_URL.",
    )

    parser.add_argument("--config", help="Single workflow JSON file.")
    parser.add_argument("--apply-dir", help="Directory containing workflow JSON files.")
    parser.add_argument("--recursive", action="store_true", help="Search workflow JSON recursively.")
    parser.add_argument("--validate-only", action="store_true", help="Validate only. Do not write DB.")

    parser.add_argument("--unpause", action="store_true", help="Set dag.is_paused = false.")
    parser.add_argument("--fileloc-prefix", default="db-json://source2silver", help="Serialized DAG fileloc prefix.")
    parser.add_argument("--processor-subdir", default="json-sql-compiler", help="processor_subdir value.")

    parser.add_argument(
        "--sequential-if-no-deps",
        action="store_true",
        help="If no dependency field exists, connect tasks sequentially by list order.",
    )

    parser.add_argument(
        "--emit-json-dir",
        help="Write generated serialized_dag.data JSON files to local directory for debugging.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.config and not args.apply_dir:
        print("ERROR: use --config or --apply-dir", file=sys.stderr)
        return 2

    files = find_workflow_files(args.config or args.apply_dir, recursive=args.recursive)
    workflows = validate_all(files)

    print("==================================================")
    print("RAW SQL JSON COMPILER")
    print("No Airflow imports")
    print("workflow files:", len(files))

    for f in files:
        print(" -", f)

    print("validate_only:", args.validate_only)
    print("unpause:", args.unpause)
    print("fileloc_prefix:", args.fileloc_prefix)
    print("processor_subdir:", args.processor_subdir)
    print("runtime source: serialized_dag.data")
    print("==================================================")

    if args.validate_only:
        for workflow in workflows:
            print(
                "VALID:",
                workflow["dag_id"],
                "tasks:",
                [get_task_id(t) for t in get_tasks(workflow)],
            )

        print("VALIDATION OK")
        return 0

    if not args.db_url:
        print("ERROR: missing --db-url or AIRFLOW_DB_URL", file=sys.stderr)
        return 2

    conn = connect(args.db_url)

    try:
        for workflow in workflows:
            apply_workflow(
                conn=conn,
                workflow=workflow,
                fileloc_prefix=args.fileloc_prefix,
                processor_subdir=args.processor_subdir,
                unpause=args.unpause,
                sequential_if_no_deps=args.sequential_if_no_deps,
                emit_json_dir=args.emit_json_dir,
            )

        conn.commit()
        print("==================================================")
        print("ALL DONE")
        return 0

    except Exception as e:
        conn.rollback()
        print("FAILED:", repr(e), file=sys.stderr)
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
