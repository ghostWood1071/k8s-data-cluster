# Spark History Server

This deployment runs Spark History Server in namespace `compute` and reads event
logs directly from:

```text
s3a://spark-logs/events
```

It is exposed through nginx-ingress at:

```text
http://spark-history.datalabutehy.com
```

Cloudflare can terminate HTTPS for the public hostname.

## Deploy

```bash
kubectl apply -f spark-history-server.yaml
kubectl rollout status deploy/spark-history-server -n compute
kubectl get pods,svc,ingress -n compute -l app=spark-history-server
```

## Runtime

- Image: `ghostwood/spark-engine:1.0.2`
- Service account: `spark`
- UI port: `18080`
- MinIO endpoint: `http://minio-svc-private.storage.svc.cluster.local:9000`

The manifest currently uses the same MinIO default credentials as the rest of the
local platform manifests. Replace Secret `spark-history-minio` if credentials are
rotated.
