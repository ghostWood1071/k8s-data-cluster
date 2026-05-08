FROM flink:1.18.1-java17
RUN wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/starrocks/flink-connector-starrocks/1.2.10_flink-1.18/flink-connector-starrocks-1.2.10_flink-1.18.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-json/1.18.1/flink-json-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-table-api-java-bridge/1.18.1/flink-table-api-java-bridge-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-streaming-java/1.18.1/flink-streaming-java-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-java/1.18.1/flink-java-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-core/2.17.1/jackson-core-2.17.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-databind/2.17.1/jackson-databind-2.17.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-annotations/2.17.1/jackson-annotations-2.17.1.jar \
    && wget -P /opt/flink/lib https://repository.cloudera.com/repository/libs-release-local/org/apache/flink/flink-sql-runner/1.18.1-csaop1.0.0/flink-sql-runner-1.18.1-csaop1.0.0.jar
RUN curl -L -o /opt/flink/lib/hadoop-aws-3.3.4.jar https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar
RUN curl -L -o /opt/flink/lib/aws-java-sdk-bundle-1.12.367.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar
RUN curl -L -o /opt/flink/lib/org.apache.hadoop_hadoop-client-api-3.3.4.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-client-api/3.3.4/hadoop-client-api-3.3.4.jar
RUN curl -L -o /opt/flink/lib/org.apache.hadoop_hadoop-client-runtime-3.3.4.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-client-runtime/3.3.4/hadoop-client-runtime-3.3.4.jar
RUN curl -L -o /opt/flink/lib/flink-s3-fs-hadoop-1.18.1.jar https://repo1.maven.org/maven2/org/apache/flink/flink-s3-fs-hadoop/1.18.1/flink-s3-fs-hadoop-1.18.1.jar

COPY cdc-kafka-starrocks-1.0-SNAPSHOT.jar /opt/flink/lib