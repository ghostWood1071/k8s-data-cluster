# Bạn có thể dùng :latest hoặc chốt version (khuyên nên chốt, ví dụ 16)
FROM bitnami/postgresql:latest

# Thư mục init của Bitnami Postgres cũng chạy *.sql khi khởi tạo data directory lần đầu
COPY 00-create-airflow.sql /docker-entrypoint-initdb.d/00-create-airflow.sql
