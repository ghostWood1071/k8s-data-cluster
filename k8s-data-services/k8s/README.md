# K8s manifests (Delta, no MinIO)

## Apply
kubectl apply -f 00-namespaces.yaml
kubectl apply -f 01-secrets-configs/
kubectl apply -f metastore/
kubectl apply -f query/
kubectl apply -f compute/
kubectl apply -f orchestration/

## Check
kubectl get ns
kubectl -n query get pods -o wide
kubectl -n compute get pods -o wide
kubectl -n orchestration get pods -o wide

## Port-forward
kubectl -n query         port-forward svc/trino         8080:8080
kubectl -n compute       port-forward svc/spark-master  8080:8080
kubectl -n orchestration port-forward svc/airflow-web   8088:8080
