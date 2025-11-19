FROM flink:1.18.1-java17
RUN wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/starrocks/flink-connector-starrocks/1.2.10_flink-1.18/flink-connector-starrocks-1.2.10_flink-1.18.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-json/1.18.1/flink-json-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-table-api-java-bridge/1.18.1/flink-table-api-java-bridge-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-streaming-java/1.18.1/flink-streaming-java-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/org/apache/flink/flink-java/1.18.1/flink-java-1.18.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-core/2.17.1/jackson-core-2.17.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-databind/2.17.1/jackson-databind-2.17.1.jar \
    && wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-annotations/2.17.1/jackson-annotations-2.17.1.jar