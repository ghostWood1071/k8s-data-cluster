# Airflow orchestration only

Bộ file này chỉ cập nhật tài nguyên thuộc namespace `orchestration` và Helm release `airflow`.

Không deploy, scale hoặc sửa manifest của Keycloak. Airflow chỉ sử dụng Keycloak đang chạy thông qua OIDC.

## File sử dụng

- `restart-airflow-http.sh`: khởi động/cập nhật Helm release Airflow hiện có.
- `values-keycloak-only-http.yaml`: overlay HTTP và cấu hình đăng nhập Keycloak.
- `storage.yaml`: PVC PostgreSQL trong namespace `orchestration`.
- `postgres-nodeport.yaml`: Service PostgreSQL trong namespace `orchestration`.
- `Dockerfile`, `requirements.txt`: giữ lại để build custom image khi thật sự cần; script restart không build image.

`role-binding.yaml` không có trong gói vì file đó tạo RoleBinding ở namespace `compute`. Script này không sửa namespace `compute`.

`00-create-airflow.sql` không có trong gói vì Airflow hiện kết nối PostgreSQL bằng user `postgres` và file SQL đó không tham gia quá trình restart.

## Chạy

```bash
cd /srv/workspaces/tunglt1/k8s-data-cluster/k8s-data-services/orchestration
chmod +x restart-airflow-http.sh
./restart-airflow-http.sh
```

Nếu Secret `airflow-keycloak` chưa tồn tại:

```bash
read -s -p "Keycloak Client Secret: " KEYCLOAK_CLIENT_SECRET
echo
export KEYCLOAK_CLIENT_SECRET
./restart-airflow-http.sh
unset KEYCLOAK_CLIENT_SECRET
```

## Kiểm tra

```bash
helm status airflow -n orchestration
kubectl get pods,svc,ingress,pvc -n orchestration -o wide
curl -vI http://airflow.k8s.tailnet:30296
```

Script yêu cầu Helm release `airflow` vẫn tồn tại. Nếu release đã bị xóa, script chủ động dừng để tránh cài mới bằng image hoặc Airflow version không chắc chắn.
