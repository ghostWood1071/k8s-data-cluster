FROM ghostwood/airflow:2.0.3

ARG AIRFLOW_VERSION=2.10.3

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jdk-headless \
        gcc g++ \
        libpq-dev \
        default-libmysqlclient-dev \
        python3-dev \
        postgresql-client \
        curl ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

RUN mkdir -p /opt/airflow/jars /opt/airflow/scripts \
    && chown -R airflow:root /opt/airflow/scripts

RUN curl -L -o /opt/airflow/jars/hadoop-aws-3.3.4.jar \
    https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar

RUN curl -L -o /opt/airflow/jars/aws-java-sdk-bundle-1.12.367.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar

RUN curl -L -o /opt/airflow/jars/delta-spark_2.12-3.2.0.jar \
    https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.0/delta-spark_2.12-3.2.0.jar

RUN curl -L -o /opt/airflow/jars/delta-storage-3.2.0.jar \
    https://repo1.maven.org/maven2/io/delta/delta-storage/3.2.0/delta-storage-3.2.0.jar

RUN curl -L -o /opt/airflow/jars/postgresql-42.7.3.jar \
    https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar

RUN curl -L -o /opt/airflow/jars/ojdbc11-23.7.0.25.01.jar \
    https://repo1.maven.org/maven2/com/oracle/database/jdbc/ojdbc11/23.7.0.25.01/ojdbc11-23.7.0.25.01.jar

RUN curl -L -o /opt/airflow/jars/hive-metastore-3.1.3.jar \
    https://repo.maven.apache.org/maven2/org/apache/hive/hive-metastore/3.1.3/hive-metastore-3.1.3.jar

RUN curl -L -o /opt/airflow/jars/hive-exec-3.1.3.jar \
    https://repo.maven.apache.org/maven2/org/apache/hive/hive-exec/3.1.3/hive-exec-3.1.3.jar

RUN curl -L -o /opt/airflow/jars/kafka-clients-3.4.1.jar \
    https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar

RUN curl -L -o /opt/airflow/jars/spark-sql-kafka-0-10_2.12-3.5.7.jar \
    https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.7/spark-sql-kafka-0-10_2.12-3.5.7.jar

RUN curl -L -o /opt/airflow/jars/spark-token-provider-kafka-0-10_2.12-3.5.7.jar \
    https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.7/spark-token-provider-kafka-0-10_2.12-3.5.7.jar

RUN curl -L -o /opt/airflow/jars/commons-pool2-2.11.1.jar \
    https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar

RUN curl -L -o /opt/airflow/jars/lz4-java-1.8.0.jar \
    https://repo1.maven.org/maven2/org/lz4/lz4-java/1.8.0/lz4-java-1.8.0.jar

RUN curl -L -o /opt/airflow/jars/snappy-java-1.1.10.5.jar \
    https://repo1.maven.org/maven2/org/xerial/snappy/snappy-java/1.1.10.5/snappy-java-1.1.10.5.jar

RUN curl -L -o /opt/airflow/jars/jsr305-3.0.0.jar \
    https://repo1.maven.org/maven2/com/google/code/findbugs/jsr305/3.0.0/jsr305-3.0.0.jar

RUN curl -L -o /opt/airflow/jars/starrocks-spark-connector-3.5_2.12-1.1.3.jar \
    https://repo1.maven.org/maven2/com/starrocks/starrocks-spark-connector-3.5_2.12/1.1.3/starrocks-spark-connector-3.5_2.12-1.1.3.jar

COPY --chown=airflow:root requirements.txt /requirements.txt

USER airflow

RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /requirements.txt \
    && pip check

COPY --chown=airflow:root airflow-patches/airflow/utils/cli.py /home/airflow/.local/lib/python3.11/site-packages/airflow/utils/cli.py
COPY --chown=airflow:root create_spark_k8s_connection.py /opt/airflow/scripts/create_spark_k8s_connection.py
COPY --chown=airflow:root json-sql-compiler/ /opt/airflow/json-sql-compiler/

RUN python -m py_compile /home/airflow/.local/lib/python3.11/site-packages/airflow/utils/cli.py \
    && python -m py_compile /opt/airflow/scripts/create_spark_k8s_connection.py \
    && python -m py_compile /opt/airflow/json-sql-compiler/airflow_local_settings.py \
    && python -m py_compile /opt/airflow/json-sql-compiler/pod_command_patch.py \
    && python -m py_compile /opt/airflow/json-sql-compiler/runtime_bootstrap.py
