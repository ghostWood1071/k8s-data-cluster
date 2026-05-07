FROM apache/hive:4.0.0

USER root
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

ENV HIVE_AUX_JARS_PATH=/opt/hive/lib
RUN mkdir -p ${HIVE_AUX_JARS_PATH}
WORKDIR /tmp/jars

# Versions
ARG PG_JDBC_VER=42.7.7
ARG HADOOP_AWS_VER=3.3.6
ARG AWS_SDK_BUNDLE_VER=1.12.262
# Delta (read-only; không đảm bảo cho Hive 4)
ARG DELTA_VER=3.3.2

# PostgreSQL JDBC
RUN curl -fsSL -O https://repo1.maven.org/maven2/org/postgresql/postgresql/${PG_JDBC_VER}/postgresql-${PG_JDBC_VER}.jar

# S3A / MinIO
RUN curl -fsSL -O https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_VER}/hadoop-aws-${HADOOP_AWS_VER}.jar \
 && curl -fsSL -O https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_BUNDLE_VER}/aws-java-sdk-bundle-${AWS_SDK_BUNDLE_VER}.jar

# Delta (test read-only)
RUN curl -fsSL -O https://repo1.maven.org/maven2/io/delta/delta-hive_2.12/${DELTA_VER}/delta-hive_2.12-${DELTA_VER}.jar \
 && curl -fsSL -O https://repo1.maven.org/maven2/io/delta/delta-standalone_2.12/${DELTA_VER}/delta-standalone_2.12-${DELTA_VER}.jar \
 && curl -fsSL -O https://repo1.maven.org/maven2/io/delta/delta-storage/${DELTA_VER}/delta-storage-${DELTA_VER}.jar

RUN cp -v /tmp/jars/*.jar ${HIVE_AUX_JARS_PATH}/ && rm -rf /tmp/jars

USER hive
WORKDIR /opt/hive