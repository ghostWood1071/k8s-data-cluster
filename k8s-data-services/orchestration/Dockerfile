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
    && rm -rf /var/lib/apt/lists/* \
    && install -d -o airflow -g root -m 0775 \
        /opt/airflow/json-sql-compiler

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV JSON_SQL_COMPILER_HOME=/opt/airflow/json-sql-compiler

COPY --chown=airflow:root requirements.txt /requirements.txt

USER airflow
RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /requirements.txt \
    && pip check
