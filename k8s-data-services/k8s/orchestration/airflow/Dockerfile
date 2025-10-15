# Base image từ phiên bản bạn đang dùng
FROM nlhtungg/mbs-poc-airflow:1.0.0

# Tạo thư mục config và copy file vào
USER root
RUN mkdir -p /opt/airflow/config
COPY config/hostname_callable.py /opt/airflow/config/hostname_callable.py
COPY config/airflow.cfg /opt/airflow/airflow.cfg
RUN chown -R airflow: /opt/airflow/config
USER airflow

