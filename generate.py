# Generate a "flat" Kubernetes manifest set with NO namespaces (uses the default namespace),
# keeping the same images and Delta Lake setup. Also write a simple folder tree.
import pathlib

base = pathlib.Path("k8s-data-services")
manif = base / "k8s"
manif.mkdir(parents=True, exist_ok=True)

def w(name, content):
    p = manif / name
    p.write_text(content.strip() + "\n")
    return str(p)

# MinIO
w("00-minio.yaml", """
apiVersion: v1
kind: Secret
metadata:
  name: minio-secret
type: Opaque
stringData:
  MINIO_ROOT_USER: "minio"
  MINIO_ROOT_PASSWORD: "minio@123"
---
apiVersion: v1
kind: Service
metadata:
  name: minio
spec:
  ports:
    - name: api
      port: 9000
      targetPort: 9000
    - name: console
      port: 9001
      targetPort: 9001
  selector:
    app: minio
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: minio
spec:
  serviceName: minio
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: minio/minio
          args: ["server", "--console-address", ":9001", "/data"]
          envFrom:
            - secretRef:
                name: minio-secret
          ports:
            - containerPort: 9000
            - containerPort: 9001
          volumeMounts:
            - name: data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 20Gi
""")

# Postgres (metastore + airflow db)
w("10-postgres.yaml", """
apiVersion: v1
kind: Service
metadata:
  name: postgres-metastore
spec:
  ports:
    - port: 5432
      targetPort: 5432
  selector:
    app: postgres-metastore
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pg-metastore-pvc
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 10Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-metastore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres-metastore
  template:
    metadata:
      labels:
        app: postgres-metastore
    spec:
      containers:
        - name: postgres
          image: postgres:14
          env:
            - name: POSTGRES_USER
              value: "hive"
            - name: POSTGRES_PASSWORD
              value: "hive"
            - name: POSTGRES_DB
              value: "metastore"
            - name: POSTGRES_HOST_AUTH_METHOD
              value: "password"
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: pgdata
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: pgdata
          persistentVolumeClaim:
            claimName: pg-metastore-pvc
""")

# Hive Metastore + hive-site ConfigMap
w("20-hive-metastore.yaml", """
apiVersion: v1
kind: ConfigMap
metadata:
  name: hive-site
data:
  hive-site.xml: |
    <?xml version="1.0"?>
    <configuration>
      <property>
        <name>javax.jdo.option.ConnectionURL</name>
        <value>jdbc:postgresql://postgres-metastore:5432/metastore</value>
      </property>
      <property>
        <name>javax.jdo.option.ConnectionDriverName</name>
        <value>org.postgresql.Driver</value>
      </property>
      <property>
        <name>javax.jdo.option.ConnectionUserName</name>
        <value>hive</value>
      </property>
      <property>
        <name>javax.jdo.option.ConnectionPassword</name>
        <value>hive</value>
      </property>
      <property>
        <name>datanucleus.autoCreateSchema</name>
        <value>true</value>
      </property>
    </configuration>
---
apiVersion: v1
kind: Service
metadata:
  name: hive-metastore
spec:
  ports:
    - port: 9083
      targetPort: 9083
  selector:
    app: hive-metastore
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hive-metastore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hive-metastore
  template:
    metadata:
      labels:
        app: hive-metastore
    spec:
      initContainers:
        - name: fetch-jars
          image: curlimages/curl:8.10.1
          command: ["/bin/sh","-c"]
          args:
            - >
              set -e;
              mkdir -p /opt/hive/lib;
              curl -L -o /opt/hive/lib/postgresql-42.6.2.jar https://repo1.maven.org/maven2/org/postgresql/postgresql/42.6.2/postgresql-42.6.2.jar;
              curl -L -o /opt/hive/lib/hadoop-aws-3.3.4.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar;
              curl -L -o /opt/hive/lib/aws-java-sdk-bundle-1.12.367.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar;
          volumeMounts:
            - name: hive-lib
              mountPath: /opt/hive/lib
      containers:
        - name: metastore
          image: apache/hive:4.0.0
          env:
            - name: SERVICE_NAME
              value: "metastore"
            - name: HIVE_METASTORE_DB_TYPE
              value: "postgres"
            - name: HIVE_METASTORE_USER
              value: "hive"
            - name: HIVE_METASTORE_PASSWORD
              value: "hive"
            - name: HIVE_METASTORE_DB_HOST
              value: "postgres-metastore"
            - name: HIVE_METASTORE_DB_NAME
              value: "metastore"
            - name: DB_DRIVER
              value: "postgres"
          ports:
            - containerPort: 9083
          volumeMounts:
            - name: hive-conf
              mountPath: /opt/hive/conf
            - name: hive-lib
              mountPath: /opt/hive/lib
      volumes:
        - name: hive-conf
          configMap:
            name: hive-site
        - name: hive-lib
          emptyDir: {}
""")

# HiveServer2 (optional)
w("21-hive-server.yaml", """
apiVersion: v1
kind: Service
metadata:
  name: hive-server
spec:
  ports:
    - port: 10000
      targetPort: 10000
  selector:
    app: hive-server
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hive-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hive-server
  template:
    metadata:
      labels:
        app: hive-server
    spec:
      containers:
        - name: hiveserver2
          image: apache/hive:4.0.0
          env:
            - name: SERVICE_NAME
              value: "hiveserver2"
          ports:
            - containerPort: 10000
          volumeMounts:
            - name: hive-conf
              mountPath: /opt/hive/conf
      volumes:
        - name: hive-conf
          configMap:
            name: hive-site
""")

# Spark (Delta Lake jars)
w("30-spark-master.yaml", """
apiVersion: v1
kind: Service
metadata:
  name: spark-master
spec:
  ports:
    - name: webui
      port: 8080
      targetPort: 8080
    - name: rpc
      port: 7077
      targetPort: 7077
  selector:
    app: spark-master
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spark-master
spec:
  replicas: 1
  selector:
    matchLabels:
      app: spark-master
  template:
    metadata:
      labels:
        app: spark-master
    spec:
      initContainers:
        - name: fetch-spark-jars
          image: curlimages/curl:8.10.1
          command: ["/bin/sh","-c"]
          args:
            - >
              set -e;
              mkdir -p /opt/spark/jars;
              curl -L -o /opt/spark/jars/hadoop-aws-3.3.4.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar;
              curl -L -o /opt/spark/jars/aws-java-sdk-bundle-1.12.367.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar;
              curl -L -o /opt/spark/jars/delta-spark_2.12-3.2.0.jar https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.0/delta-spark_2.12-3.2.0.jar;
              curl -L -o /opt/spark/jars/delta-storage-3.2.0.jar https://repo1.maven.org/maven2/io/delta/delta-storage/3.2.0/delta-storage-3.2.0.jar;
          volumeMounts:
            - name: spark-jars
              mountPath: /opt/spark/jars
      containers:
        - name: master
          image: spark:3.5.6-scala2.12-java11-python3-r-ubuntu
          env:
            - name: SPARK_MODE
              value: master
          ports:
            - containerPort: 8080
            - containerPort: 7077
          volumeMounts:
            - name: spark-jars
              mountPath: /opt/spark/jars
            - name: hive-site
              mountPath: /opt/spark/conf/hive-site.xml
              subPath: hive-site.xml
      volumes:
        - name: spark-jars
          emptyDir: {}
        - name: hive-site
          configMap:
            name: hive-site
""")

w("31-spark-worker.yaml", """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spark-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: spark-worker
  template:
    metadata:
      labels:
        app: spark-worker
    spec:
      initContainers:
        - name: fetch-spark-jars
          image: curlimages/curl:8.10.1
          command: ["/bin/sh","-c"]
          args:
            - >
              set -e;
              mkdir -p /opt/spark/jars;
              curl -L -o /opt/spark/jars/hadoop-aws-3.3.4.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar;
              curl -L -o /opt/spark/jars/aws-java-sdk-bundle-1.12.367.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar;
              curl -L -o /opt/spark/jars/delta-spark_2.12-3.2.0.jar https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.0/delta-spark_2.12-3.2.0.jar;
              curl -L -o /opt/spark/jars/delta-storage-3.2.0.jar https://repo1.maven.org/maven2/io/delta/delta-storage/3.2.0/delta-storage-3.2.0.jar;
          volumeMounts:
            - name: spark-jars
              mountPath: /opt/spark/jars
      containers:
        - name: worker
          image: spark:3.5.6-scala2.12-java11-python3-r-ubuntu
          env:
            - name: SPARK_MODE
              value: worker
            - name: SPARK_MASTER
              value: "spark://spark-master:7077"
          ports:
            - containerPort: 8081
          volumeMounts:
            - name: spark-jars
              mountPath: /opt/spark/jars
            - name: hive-site
              mountPath: /opt/spark/conf/hive-site.xml
              subPath: hive-site.xml
      volumes:
        - name: spark-jars
          emptyDir: {}
        - name: hive-site
          configMap:
            name: hive-site
""")

# Trino
w("40-trino-configmap.yaml", """
apiVersion: v1
kind: ConfigMap
metadata:
  name: trino-config
data:
  node.properties: |
    node.environment=production
    node.data-dir=/data/trino
    node.id=trino-coordinator-1
  jvm.config: |
    -Xmx4G
    -XX:+UseG1GC
  config.properties: |
    coordinator=true
    node-scheduler.include-coordinator=false
    http-server.http.port=8080
    discovery-server.enabled=true
    discovery.uri=http://trino-coordinator:8080
  catalog/delta.properties: |
    connector.name=delta-lake
    hive.metastore.uri=thrift://hive-metastore:9083
    delta.hide-non-delta-lakes=true
    filesystem.s3.aws-access-key=minio
    filesystem.s3.aws-secret-key=minio@123
    filesystem.s3.path-style-access=true
    filesystem.s3.endpoint=http://minio:9000
    fs.hadoop.enabled=true
""")

w("41-trino-coordinator.yaml", """
apiVersion: v1
kind: Service
metadata:
  name: trino-coordinator
spec:
  ports:
    - port: 8080
      targetPort: 8080
  selector:
    app: trino-coordinator
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trino-coordinator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: trino-coordinator
  template:
    metadata:
      labels:
        app: trino-coordinator
    spec:
      containers:
        - name: trino
          image: trinodb/trino:441
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: trino-config
              mountPath: /etc/trino
      volumes:
        - name: trino-config
          configMap:
            name: trino-config
            items:
              - key: node.properties
                path: node.properties
              - key: jvm.config
                path: jvm.config
              - key: config.properties
                path: config.properties
              - key: catalog/delta.properties
                path: catalog/delta.properties
""")

w("42-trino-worker.yaml", """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trino-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: trino-worker
  template:
    metadata:
      labels:
        app: trino-worker
    spec:
      containers:
        - name: trino
          image: trinodb/trino:441
          volumeMounts:
            - name: trino-config
              mountPath: /etc/trino
      volumes:
        - name: trino-config
          configMap:
            name: trino-config
            items:
              - key: node.properties
                path: node.properties
              - key: jvm.config
                path: jvm.config
              - key: config.properties
                path: config.properties
              - key: catalog/delta.properties
                path: catalog/delta.properties
""")

# Redis
w("50-redis.yaml", """
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  ports:
    - port: 6379
      targetPort: 6379
  selector:
    app: redis
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7
          ports:
            - containerPort: 6379
""")

# Airflow (flat)
w("60-airflow-configmap.yaml", """
apiVersion: v1
kind: ConfigMap
metadata:
  name: airflow-env
data:
  AIRFLOW__CORE__EXECUTOR: CeleryExecutor
  AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://hive:hive@postgres-metastore:5432/airflow
  AIRFLOW__CELERY__BROKER_URL: redis://redis:6379/0
  AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://hive:hive@postgres-metastore:5432/airflow
  AIRFLOW__CORE__FERNET_KEY: 31E1-24OEkjXpTnzoypiTODWKtA3GUlRuqZjnkc9e20=
  AIRFLOW__CORE__LOAD_EXAMPLES: "False"
""")

w("61-airflow.yaml", """
apiVersion: v1
kind: Service
metadata:
  name: airflow-webserver
spec:
  ports:
    - port: 8080
      targetPort: 8080
  selector:
    app: airflow-webserver
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airflow-webserver
spec:
  replicas: 1
  selector:
    matchLabels:
      app: airflow-webserver
  template:
    metadata:
      labels:
        app: airflow-webserver
    spec:
      containers:
        - name: webserver
          image: apache-airflow:2.7.3-java11
          envFrom:
            - configMapRef:
                name: airflow-env
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: dags
              mountPath: /opt/airflow/dags
            - name: logs
              mountPath: /opt/airflow/logs
            - name: jobs
              mountPath: /opt/airflow/jobs
      volumes:
        - name: dags
          emptyDir: {}
        - name: logs
          emptyDir: {}
        - name: jobs
          emptyDir: {}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airflow-scheduler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: airflow-scheduler
  template:
    metadata:
      labels:
        app: airflow-scheduler
    spec:
      containers:
        - name: scheduler
          image: apache-airflow:2.7.3-java11
          envFrom:
            - configMapRef:
                name: airflow-env
          volumeMounts:
            - name: dags
              mountPath: /opt/airflow/dags
            - name: logs
              mountPath: /opt/airflow/logs
            - name: jobs
              mountPath: /opt/airflow/jobs
      volumes:
        - name: dags
          emptyDir: {}
        - name: logs
          emptyDir: {}
        - name: jobs
          emptyDir: {}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airflow-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: airflow-worker
  template:
    metadata:
      labels:
        app: airflow-worker
    spec:
      containers:
        - name: worker
          image: apache-airflow:2.7.3-java11
          envFrom:
            - configMapRef:
                name: airflow-env
          volumeMounts:
            - name: dags
              mountPath: /opt/airflow/dags
            - name: logs
              mountPath: /opt/airflow/logs
            - name: jobs
              mountPath: /opt/airflow/jobs
      volumes:
        - name: dags
          emptyDir: {}
        - name: logs
          emptyDir: {}
        - name: jobs
          emptyDir: {}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airflow-triggerer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: airflow-triggerer
  template:
    metadata:
      labels:
        app: airflow-triggerer
    spec:
      containers:
        - name: triggerer
          image: apache-airflow:2.7.3-java11
          envFrom:
            - configMapRef:
                name: airflow-env
          volumeMounts:
            - name: dags
              mountPath: /opt/airflow/dags
            - name: logs
              mountPath: /opt/airflow/logs
            - name: jobs
              mountPath: /opt/airflow/jobs
      volumes:
        - name: dags
          emptyDir: {}
        - name: logs
          emptyDir: {}
        - name: jobs
          emptyDir: {}
""")

# README
(manif / "README.md").write_text("""
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
""")

print("Wrote flat K8s manifests to:", str(manif))
