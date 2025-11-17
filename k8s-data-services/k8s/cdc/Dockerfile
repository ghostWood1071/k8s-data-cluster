FROM flink:1.18.1-scala_2.12-java17
RUN apt-get update && apt-get install -y curl && apt-get install -y telnet
RUN curl -L -o /opt/flink/lib/flink-sql-connector-kafka-3.1.0-1.18.jar https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar
RUN curl -L -o /opt/flink/lib/flink-connector-starrocks-1.2.10_flink-1.18.jar https://repo1.maven.org/maven2/com/starrocks/flink-connector-starrocks/1.2.10_flink-1.18/flink-connector-starrocks-1.2.10_flink-1.18.jar
RUN curl -L -o /opt/flink/lib/flink-json-1.18.1.jar https://repo1.maven.org/maven2/org/apache/flink/flink-json/1.18.1/flink-json-1.18.1.jar