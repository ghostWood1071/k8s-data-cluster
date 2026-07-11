# DB-Only Airflow DAG với JSON-to-SQL Compiler

Tài liệu này hướng dẫn triển khai cơ chế **DB-only DAG** trên Apache Airflow. Thay vì tạo DAG bằng mã Python trong thư mục `dags`, hệ thống đọc cấu hình workflow từ JSON, biên dịch cấu hình thành dữ liệu metadata và ghi trực tiếp vào Airflow Metadata Database.

> [!IMPORTANT]
> Cơ chế này không tạo `DAG object`, Compiler phải ánh xạ cấu hình JSON thành các bản ghi phù hợp trong những bảng metadata cần thiết.

## 1. Kiến trúc hoạt động

```text
Workflow JSON trên máy local
  ↓
json_raw_sql_compiler.py
  ↓
Airflow Metadata Database
  ├── dag
  ├── serialized_dag
  └── dag_tag
  ↓
Airflow Scheduler
  ↓
KubernetesExecutor tạo task pod
  ↓
pod_mutation_hook chỉnh sửa command của task pod
  ↓
runtime_bootstrap.py đọc serialized_dag.data
  ↓
SparkSubmitOperator
  ↓
spark-submit
```

Luồng xử lý gồm hai giai đoạn chính:

1. **Compile time:** `json_raw_sql_compiler.py` đọc workflow JSON và ghi các bản ghi tương ứng vào Airflow Metadata Database.
2. **Runtime:** Khi DAG được trigger, KubernetesExecutor tạo task pod. `pod_mutation_hook` thay đổi command để task pod chạy `runtime_bootstrap.py`, đọc thông tin task và thực thi `SparkSubmitOperator`.

## 2. Thông tin môi trường

| Thành phần | Giá trị |
|---|---|
| Kubernetes namespace | `orchestration` |
| Airflow image | `linhdv2312/airflow:2.10.3-jars` |
| Airflow version | `2.10.3` |
| Helm chart | `apache-airflow/airflow` phiên bản `1.19.0` |
| Executor | `KubernetesExecutor` |
| DAG PVC | `airflow-dags` |

### Yêu cầu trước khi triển khai

- Compiler và task pod có đủ thông tin kết nối tới Airflow Metadata Database.

## 3. Triển khai Airflow

```bash
cd ./orchestration

kubectl apply -f role-binding.yaml
kubectl apply -f storage.yaml

helm repo add apache-airflow https://airflow.apache.org
helm repo update
```

Cài đặt mới hoặc cập nhật Airflow:

```bash
helm upgrade --install airflow apache-airflow/airflow --version 1.19.0 --namespace orchestration --values values.yaml
```

## 4. Chuẩn bị các file runtime

Hệ thống cần ba file Python runtime:

```text
airflow_local_settings.py
pod_command_patch.py
runtime_bootstrap.py
```

Các file được lưu trong thư mục sau bên trong Airflow pod:

```text
/opt/airflow/dags/json-sql-compiler/
```

Cấu trúc mong đợi:

```text
/opt/airflow/dags/
├── .airflowignore
└── json-sql-compiler/
    ├── airflow_local_settings.py
    ├── pod_command_patch.py
    └── runtime_bootstrap.py
```

## 5. Vai trò của các file runtime

### 5.1. `airflow_local_settings.py`

Đây là điểm vào để Airflow đăng ký hook tùy chỉnh.

Nhiệm vụ chính:

- Được Airflow Scheduler import khi khởi động.
- Cung cấp hàm `pod_mutation_hook`.
- Gọi hàm `patch_pod` trong `pod_command_patch.py` trước khi KubernetesExecutor tạo task pod.

### 5.2. `pod_command_patch.py`

File này điều chỉnh command của task pod dành cho DB-only DAG.

Nhiệm vụ chính:

- Nhận Kubernetes pod object từ Airflow Scheduler.
- Lấy các thông tin như `dag_id`, `task_id` và `run_id`.
- Xác định task có thuộc DB-only DAG hay không.
- Thay đổi command của task pod để chạy `runtime_bootstrap.py`.

### 5.3. `runtime_bootstrap.py`

Đây là chương trình được thực thi bên trong task pod.

Nhiệm vụ chính:

- Nhận `dag_id`, `task_id` và `run_id`.
- Kết nối tới Airflow Metadata Database.
- Đọc bản ghi tương ứng trong bảng `serialized_dag`.
- Phân tích trường `serialized_dag.data`.
- Tìm đúng cấu hình của task cần chạy.
- Khởi tạo `SparkSubmitOperator` từ dữ liệu đã đọc.
- Gọi `operator.execute()` để thực thi tác vụ Spark.

## 6. Cấu hình `.airflowignore`

### 6.1. Mục đích

Thư mục `json-sql-compiler` chứa các file Python runtime, không phải DAG Python truyền thống. Nếu không ignore thư mục này, Airflow Scheduler có thể quét và parse các file runtime như DAG file, gây log cảnh báo hoặc lỗi parse không cần thiết.

File `.airflowignore` giúp Scheduler bỏ qua thư mục runtime và các thư mục cache của Python.

### 6.2. Tạo pod tạm để mount PVC

Khai báo namespace:

```bash
export NS="orchestration"
```

Tạo manifest cho pod tạm:

```bash
cat > /tmp/airflow-dags-cleaner.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: airflow-dags-cleaner
  namespace: ${NS}
spec:
  restartPolicy: Never
  securityContext:
    runAsUser: 0
    runAsGroup: 0
  containers:
    - name: cleaner
      image: linhdv2312/airflow:2.10.3-jars
      command: ["bash", "-lc", "echo 'Cleaner is ready'; sleep 3600"]
      volumeMounts:
        - name: airflow-dags
          mountPath: /mnt/airflow-dags
  volumes:
    - name: airflow-dags
      persistentVolumeClaim:
        claimName: airflow-dags
EOF
```

Khởi tạo pod và chờ tới khi pod sẵn sàng:

```bash
kubectl apply -f /tmp/airflow-dags-cleaner.yaml

kubectl wait \
  --namespace "$NS" \
  --for=condition=Ready \
  pod/airflow-dags-cleaner 
```

### 6.3. Tạo file `.airflowignore`

```bash
kubectl exec \
  --namespace "$NS" \
  airflow-dags-cleaner \
  --container cleaner \
  -- bash -lc '
set -e

mkdir -p /mnt/airflow-dags/json-sql-compiler

cat > /mnt/airflow-dags/.airflowignore <<EOF
json-sql-compiler/.*
.*/json-sql-compiler/.*
__pycache__/.*
.*/__pycache__/.*
EOF

cat /mnt/airflow-dags/.airflowignore
'
```

## 7. Sao chép file runtime vào PVC

Giả sử ba file runtime đang nằm tại thư mục local `~/json-sql-compiler`:

```bash
tar -C ~/json-sql-compiler -cf - \
  airflow_local_settings.py \
  pod_command_patch.py \
  runtime_bootstrap.py \
| kubectl exec \
    --stdin \
    --namespace "$NS" \
    airflow-dags-cleaner \
    --container cleaner \
    -- tar -C /mnt/airflow-dags/json-sql-compiler -xf -
```

Cập nhật quyền truy cập, xóa cache và kiểm tra cấu trúc file:

```bash
kubectl exec \
  --namespace "$NS" \
  airflow-dags-cleaner \
  --container cleaner \
  -- bash -lc '
set -e

chown -R airflow:root /mnt/airflow-dags
chmod -R 755 /mnt/airflow-dags/json-sql-compiler
rm -rf /mnt/airflow-dags/json-sql-compiler/__pycache__

find /mnt/airflow-dags -maxdepth 3 -print | sort
'
```

Sau khi hoàn tất, xóa pod tạm:

```bash
kubectl delete pod airflow-dags-cleaner --namespace "$NS" --force --grace-period=0
```

## 8. Khởi động lại các thành phần Airflow

Khởi động lại Scheduler:

```bash
kubectl rollout restart deployment --namespace orchestration --selector component=scheduler
kubectl rollout status deployment --namespace orchestration --selector component=scheduler --timeout=300s
```

Khởi động lại Webserver:

```bash
kubectl rollout restart deployment --namespace orchestration --selector component=webserver
kubectl rollout status deployment --namespace orchestration --selector component=webserver --timeout=300s
```

## 9. Biên dịch workflow JSON vào metadata database

Biên dịch toàn bộ file JSON trong một thư mục:

```bash
python3 ~/json_raw_sql_compiler.py \
  --apply-dir "/path/to/json-workflows hoặc ~/file.json" \
  --recursive \
  --unpause
```

## 10. Trigger DAG để kiểm thử

Khai báo namespace, DAG ID và run ID:

```bash
export NS="orchestration"
export DAG_ID="your_dag_id"
export RUN_ID="manual__test_$(date -u +%Y%m%dT%H%M%SZ)"
```

Lấy tên Scheduler pod đang chạy:

```bash
export SCHED_POD="$(
  kubectl get pods -n "$NS" --no-headers \
  | awk '/scheduler/ && /Running/ {print $1; exit}'
)"
```

Trigger DAG từ Scheduler pod:

```bash
kubectl exec --namespace "$NS" "$SCHED_POD" --container scheduler -- airflow dags trigger "$DAG_ID" --run-id "$RUN_ID"
```

## 11. Theo dõi task pod và log

Liệt kê các pod mới nhất trong namespace:

```bash
kubectl get pods --namespace "$NS" --sort-by=.metadata.creationTimestamp
```

Gán tên task pod cần kiểm tra:

```bash
export TASK_POD="your-task-pod-name"
```

Theo dõi log theo thời gian thực:

```bash
kubectl logs --namespace "$NS" "$TASK_POD" --follow
```

## Lưu ý vận hành

- File json mẫu source2silver.json phải giữa nguyên cấu trúc chỉ được thay đổi các giá trị cấu hình
```bash
{
  "dag_id": "source2silver_test1",
  "description": "source -> bronze -> silver",
  "owner": "data_team",
  "email": ["abc@gmail.com"],
  "timezone": "UTC",
  "start_date": "2025-01-01T00:00:00+00:00",
  "schedule": "0 18 * * *",
  "catchup": false,
  "is_paused": false,
  "max_active_runs": 1,
  "max_active_tasks": 16,
  "retries": 2,
  "retry_delay": 300,
  "tags": ["source2bronze", "bronze2silver"],
  "tasks": [
    {
      "task_id": "source2bronze_Orders_Retail3A",
      "operator": "SparkSubmitOperator",
      "module": "airflow.providers.apache.spark.operators.spark_submit",
      "params": {
        "application": "s3a://asset/spark-jobs/entry_point.py",
        "conn_id": "spark_k8s",
        "name": "source2bronze_Orders_Retail3A",
        "application_args": [
          "--job_asset_bucket", "asset",
          "--job_input_path", "job-input/source2bronze.json"
        ],
        "conf": {}
      },
      "downstream": ["bronze2silver_Orders_Retail3A"]
    },
    {
      "task_id": "bronze2silver_Orders_Retail3A",
      "operator": "SparkSubmitOperator",
      "module": "airflow.providers.apache.spark.operators.spark_submit",
      "params": {
        "application": "s3a://asset/spark-jobs/entry_point.py",
        "conn_id": "spark_k8s",
        "name": "bronze2silver_Orders_Retail3A",
        "application_args": [
          "--job_asset_bucket", "asset",
          "--job_input_path", "job-input/bronze2silver.json"
        ],
        "conf": {}
      },
      "downstream": []
    }
  ]
}
```
- Schema của các bảng metadata có thể thay đổi giữa các phiên bản Airflow. Compiler sử dụng cho Airflow `2.10.3`.