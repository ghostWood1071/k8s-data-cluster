FROM apache/airflow:2.10.0-python3.11

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jdk-headless \
        gcc g++ \
        libpq-dev \
        default-libmysqlclient-dev \
        python3-dev \
        curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

COPY requirements.txt /requirements.txt
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt


WORKDIR /opt/airflow
