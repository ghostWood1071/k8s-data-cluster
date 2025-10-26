from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from datetime import datetime

default_args = {"owner": "airflow", "retries": 0}

# Maven coordinates (Spark sẽ tự tải)
PACKAGES = ",".join([
    "io.delta:delta-spark_2.12:3.2.0",
    "org.apache.hadoop:hadoop-aws:3.3.4",
    "org.postgresql:postgresql:42.7.3",
    "org.apache.hive:hive-metastore:3.1.3",
    "org.apache.hive:hive-exec:3.1.3"
])

with DAG(
    dag_id="spark_create_customer_delta_tables",
    start_date=datetime(2025, 10, 19),
    schedule_interval=None,
    catchup=False,
    tags=["spark", "delta", "hive"]
) as dag:

    create_delta_job = SparkSubmitOperator(
        task_id="create_customer_demo",
        application="local:///opt/spark/app/create_customer_data.py",
        deploy_mode="cluster",
        name="spark-delta-create",
        conn_id="spark_k8s",
        conf={
            "spark.kubernetes.namespace": "compute",
            "spark.kubernetes.container.image": "ghostwood/spark-delta-samp-job:2.0.2",
            "spark.kubernetes.authenticate.driver.serviceAccountName": "spark",
            "spark.jars.packages": PACKAGES,
            "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
            "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            "spark.sql.catalogImplementation": "hive",
            "spark.hadoop.hive.metastore.uris": "thrift://hive-metastore.metastore.svc.cluster.local:9083",
            "spark.sql.warehouse.dir": "s3a://warehouse/",
            "spark.hadoop.fs.s3a.endpoint": "http://minio.storage.svc.cluster.local:9000",
            "spark.hadoop.fs.s3a.access.key": "minioadmin",
            "spark.hadoop.fs.s3a.secret.key": "minio@demo!",
            "spark.hadoop.fs.s3a.path.style.access": "true",
            "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
            "spark.sql.sources.partitionOverwriteMode": "dynamic",
            "conf spark.eventLog.dir": "s3a://spark-logs/events",
            "spark.driver.extraJavaOptions": "-Divy.cache.dir=/tmp -Divy.home=/tmp"
        },
        verbose=True
    )

    create_delta_job
