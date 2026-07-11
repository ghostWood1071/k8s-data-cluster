#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import zlib
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator


class TeeStream:

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            try:
                stream.write(data)
                stream.flush()
            except Exception:
                pass

    def flush(self):
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                pass


def setup_airflow_ui_log(dag_id: str, task_id: str, run_id: str | None) -> Path:

    base_log_folder = (
        os.getenv("AIRFLOW__LOGGING__BASE_LOG_FOLDER")
        or os.getenv("AIRFLOW_BASE_LOG_FOLDER")
        or "/opt/airflow/logs"
    )

    safe_run_id = run_id or os.getenv("AIRFLOW_CTX_DAG_RUN_ID") or "manual__unknown"

    try_number = (
        os.getenv("AIRFLOW_CTX_TRY_NUMBER")
        or os.getenv("AIRFLOW_TRY_NUMBER")
        or "1"
    )

    map_index = os.getenv("AIRFLOW_CTX_MAP_INDEX", "-1")

    log_dir = (
        Path(base_log_folder)
        / f"dag_id={dag_id}"
        / f"run_id={safe_run_id}"
        / f"task_id={task_id}"
    )

    if map_index not in ("", "-1", "None", None):
        log_dir = log_dir / f"map_index={map_index}"

    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"attempt={try_number}.log"

    file_stream = open(log_file, "a", encoding="utf-8", buffering=1)

    sys.stdout = TeeStream(sys.stdout, file_stream)
    sys.stderr = TeeStream(sys.stderr, file_stream)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    logging.getLogger("airflow").addHandler(file_handler)
    logging.getLogger("airflow.providers.apache.spark").addHandler(file_handler)

    print("==================================================")
    print("AIRFLOW UI LOG ENABLED")
    print("base_log_folder:", base_log_folder)
    print("log_file:", log_file)
    print("==================================================")

    return log_file


def normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://"):]
    if url.startswith("postgres+psycopg2://"):
        return "postgresql://" + url[len("postgres+psycopg2://"):]
    return url


def get_db_url() -> str:
    url = (
        os.getenv("AIRFLOW_DB_URL")
        or os.getenv("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN")
        or os.getenv("AIRFLOW__CORE__SQL_ALCHEMY_CONN")
    )

    if not url:
        raise RuntimeError("Missing Airflow DB URL env")

    return normalize_db_url(url)


def load_serialized_dag(dag_id: str) -> dict[str, Any]:
    conn = psycopg2.connect(get_db_url(), cursor_factory=RealDictCursor)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT data, data_compressed
                FROM serialized_dag
                WHERE dag_id = %s
                """,
                (dag_id,),
            )
            row = cur.fetchone()

        if not row:
            raise RuntimeError(f"serialized_dag not found for dag_id={dag_id}")

        data = row.get("data")

        if data is not None:
            if isinstance(data, str):
                return json.loads(data)
            return data

        compressed = row.get("data_compressed")

        if compressed is None:
            raise RuntimeError(
                f"serialized_dag.data and data_compressed are both null for dag_id={dag_id}"
            )

        if isinstance(compressed, memoryview):
            compressed = compressed.tobytes()

        if isinstance(compressed, str):
            compressed = compressed.encode("utf-8")

        raw = zlib.decompress(compressed)
        return json.loads(raw.decode("utf-8"))

    finally:
        conn.close()


def find_task_var(serialized_dag: dict[str, Any], task_id: str) -> dict[str, Any]:
    dag = serialized_dag.get("dag", {})
    tasks = dag.get("tasks", [])

    for task in tasks:
        task_var = task.get("__var", {})
        if task_var.get("task_id") == task_id:
            return task_var

    raise RuntimeError(f"task_id={task_id} not found in serialized_dag.data")


def build_operator_from_task_var(task_var: dict[str, Any]) -> SparkSubmitOperator:
    task_id = task_var["task_id"]

    application = task_var.get("application")
    if not application:
        raise RuntimeError(f"Missing application in serialized task: {task_id}")

    conn_id = (
        task_var.get("conn_id")
        or task_var.get("_conn_id")
        or "spark_k8s"
    )

    kwargs = {
        "task_id": task_id,
        "conn_id": conn_id,
        "application": application,
        "name": task_var.get("name") or task_id,
        "application_args": task_var.get("application_args") or [],
        "conf": task_var.get("conf") or {},
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
        value = task_var.get(field)
        if value is not None:
            kwargs[field] = value

    return SparkSubmitOperator(**kwargs)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dag-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    setup_airflow_ui_log(
        dag_id=args.dag_id,
        task_id=args.task_id,
        run_id=args.run_id,
    )

    print("==================================================")
    print("JSON SQL RUNTIME LOG START")
    print("RUNTIME BOOTSTRAP EXECUTE")
    print("dag_id:", args.dag_id)
    print("task_id:", args.task_id)
    print("run_id:", args.run_id)
    print("workflow_source: serialized_dag.data")
    print("==================================================")

    serialized_dag = load_serialized_dag(args.dag_id)
    task_var = find_task_var(serialized_dag, args.task_id)
    operator = build_operator_from_task_var(task_var)

    print("operator_class:", operator.__class__)
    print("conn_id:", operator._conn_id)
    print("application:", operator.application)
    print("name:", operator.name)
    print("application_args:", operator.application_args)
    print("conf_keys:", sorted(list((operator.conf or {}).keys())))

    if not args.execute:
        print("DRY RUN ONLY")
        return 0

    context = {
        "dag_id": args.dag_id,
        "task_id": args.task_id,
        "run_id": args.run_id,
    }

    operator.execute(context=context)

    print("JSON SQL RUNTIME LOG END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())