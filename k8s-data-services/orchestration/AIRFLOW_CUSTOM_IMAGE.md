# Custom Airflow Image

Muc tieu: tao image Airflow co san patch runtime, thay vi exec vao pod va sua file trong
container. Source Airflow da kiem tra tai:

```text
C:\Users\thinh\OneDrive\Desktop\airflow\airflow-2.10.3
```

Thu muc nay dung ban Airflow `2.10.3`. Tuy nhien voi thay doi hien tai, khong can build lai
toan bo Airflow wheel. Cach an toan hon la build image tu Dockerfile cua project va overlay dung
file da patch.

## Patch Dang Ap Dung

File overlay:

```text
k8s-data-services/orchestration/airflow-patches/airflow/utils/cli.py
```

Patch chi doc DAG tu database khi Airflow CLI nhan `subdir` dang:

```text
DAGS_FOLDER/db-json:<dag-path>
```

Khong patch tat ca loi goi `DagBag(...)`, vi cach do lam scheduler/webserver khong parse duoc DAG
tu thu muc DAG binh thuong.

Image cung copy script tao lai connection Spark:

```text
/opt/airflow/scripts/create_spark_k8s_connection.py
```

Connection `spark_k8s` nam trong Airflow metadata DB, vi vay nen tao bang script/job sau deploy,
khong nen bake truc tiep connection vao image.

## Build Tren May Master

May Windows hien tai chua co Docker CLI, nhung `master` co Docker. Build tren `master`:

```bash
cd ~/k8s-data-cluster/k8s-data-services/orchestration
docker build -t ghostwood/airflow:2.10.3-dbdag .
```

Neu cac worker node khong keo image tu local Docker cua `master`, push image len registry ma cluster
truy cap duoc:

```bash
docker tag ghostwood/airflow:2.10.3-dbdag <registry>/airflow:2.10.3-dbdag
docker push <registry>/airflow:2.10.3-dbdag
```

## Deploy Image Moi

Cluster dang dung `containerd`. Image build bang Docker tren `master` chua tu dong co trong
`containerd` cua Kubernetes node. Co hai cach deploy:

- Khuyen nghi: push image len registry ma tat ca node keo duoc.
- Neu chua co registry: import image vao `containerd` tren tat ca node va de `pullPolicy:
  IfNotPresent`.

Overlay image:

```text
k8s-data-services/orchestration/values-airflow-custom-image.yaml
```

Lay chart values hien tai truoc khi doi image:

```bash
helm get values airflow -n orchestration -o yaml > /tmp/airflow-values-current.yaml
```

Neu image da nam tren registry:

```bash
helm upgrade airflow apache-airflow/airflow \
  -n orchestration \
  --reuse-values \
  -f values-keycloak-only-http.yaml \
  -f values-airflow-custom-image.yaml \
  --wait \
  --timeout 30m
```

Neu chua co registry, import image vao tung node truoc:

```bash
sudo docker save ghostwood/airflow:2.10.3-dbdag -o /tmp/airflow-2.10.3-dbdag.tar
sudo ctr -n k8s.io images import /tmp/airflow-2.10.3-dbdag.tar

scp /tmp/airflow-2.10.3-dbdag.tar slave01:/tmp/
scp /tmp/airflow-2.10.3-dbdag.tar slave02:/tmp/
ssh slave01 "echo 'Hduser@123' | sudo -S ctr -n k8s.io images import /tmp/airflow-2.10.3-dbdag.tar"
ssh slave02 "echo 'Hduser@123' | sudo -S ctr -n k8s.io images import /tmp/airflow-2.10.3-dbdag.tar"
```

Sau khi pod len lai, tao/refresh connection:

```bash
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- \
  python /opt/airflow/scripts/create_spark_k8s_connection.py
```

Kiem tra:

```bash
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow version
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow dags list
kubectl exec -n orchestration deploy/airflow-scheduler -c scheduler -- airflow connections get spark_k8s
```

## Khi Nao Moi Build Wheel Airflow?

Chi nen build wheel tu source Airflow khi muon maintain fork lon hon hoac sua nhieu module core.
Voi patch hien tai, overlay mot file trong image de audit va rollback de hon.
