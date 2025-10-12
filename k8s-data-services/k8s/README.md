
# K8s Manifests (Flat, default namespace)

All resources are created in the **default** namespace (no namespace objects).

## Apply order
kubectl apply -f 00-minio.yaml

kubectl apply -f 10-postgres.yaml

kubectl apply -f 20-hive-metastore.yaml

kubectl apply -f 21-hive-server.yaml

kubectl apply -f 30-spark-master.yaml

kubectl apply -f 31-spark-worker.yaml

kubectl apply -f 40-trino-configmap.yaml

kubectl apply -f 41-trino-coordinator.yaml

kubectl apply -f 42-trino-worker.yaml

kubectl apply -f 50-redis.yaml

kubectl apply -f 60-airflow-configmap.yaml

kubectl apply -f 61-airflow.yaml

## Notes
- Exact images preserved. Iceberg removed; Spark loads Delta jars via initContainer, Trino uses delta-lake connector.
- Replace emptyDir volumes with PVCs or git-sync for persistence.
