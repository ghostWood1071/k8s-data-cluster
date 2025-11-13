from apache/spark:3.5.7-scala2.12-java17-python3-ubuntu
USER root
RUN apt-get update && apt-get install -y curl && apt-get install -y telnet
RUN curl -L -o /opt/spark/jars/hadoop-aws-3.3.4.jar https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar
RUN curl -L -o /opt/spark/jars/aws-java-sdk-bundle-1.12.367.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar
RUN curl -L -o /opt/spark/jars/delta-spark_2.12-3.2.0.jar https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.0/delta-spark_2.12-3.2.0.jar
RUN curl -L -o /opt/spark/jars/postgresql-42.7.3.jar https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar
RUN curl -L -o /opt/spark/jars/hive-metastore-3.1.3.jar https://repo.maven.apache.org/maven2/org/apache/hive/hive-metastore/3.1.3/hive-metastore-3.1.3.jar
RUN curl -L -o /opt/spark/jars/hive-exec-3.1.3.jar https://repo.maven.apache.org/maven2/org/apache/hive/hive-exec/3.1.3/hive-exec-3.1.3.jar
RUN curl -L https://repo1.maven.org/maven2/com/google/code/findbugs/jsr305/3.0.0/jsr305-3.0.0.jar -o /opt/spark/jars/com.google.code.findbugs_jsr305-3.0.0.jar
RUN curl -L https://repo1.maven.org/maven2/com/starrocks/starrocks-spark-connector-3.5_2.12/1.1.3/starrocks-spark-connector-3.5_2.12-1.1.3.jar -o /opt/spark/jars/com.starrocks_starrocks-spark-connector-3.5_2.12-1.1.3.jar
RUN curl -L https://repo1.maven.org/maven2/commons-logging/commons-logging/1.1.3/commons-logging-1.1.3.jar -o /opt/spark/jars/commons-logging_commons-logging-1.1.3.jar
RUN curl -L https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar -o /opt/spark/jars/org.apache.commons_commons-pool2-2.11.1.jar
RUN curl -L https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-client-api/3.3.4/hadoop-client-api-3.3.4.jar -o /opt/spark/jars/org.apache.hadoop_hadoop-client-api-3.3.4.jar
RUN curl -L https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-client-runtime/3.3.4/hadoop-client-runtime-3.3.4.jar -o /opt/spark/jars/org.apache.hadoop_hadoop-client-runtime-3.3.4.jar
RUN curl -L https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar -o /opt/spark/jars/org.apache.kafka_kafka-clients-3.4.1.jar
RUN curl -L https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.7/spark-sql-kafka-0-10_2.12-3.5.7.jar -o /opt/spark/jars/org.apache.spark_spark-sql-kafka-0-10_2.12-3.5.7.jar
RUN curl -L https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.7/spark-token-provider-kafka-0-10_2.12-3.5.7.jar -o /opt/spark/jars/org.apache.spark_spark-token-provider-kafka-0-10_2.12-3.5.7.jar
RUN curl -L https://repo1.maven.org/maven2/org/lz4/lz4-java/1.8.0/lz4-java-1.8.0.jar -o /opt/spark/jars/org.lz4_lz4-java-1.8.0.jar
RUN curl -L https://repo1.maven.org/maven2/org/slf4j/slf4j-api/2.0.7/slf4j-api-2.0.7.jar -o /opt/spark/jars/org.slf4j_slf4j-api-2.0.7.jar
RUN curl -L https://repo1.maven.org/maven2/org/xerial/snappy/snappy-java/1.1.10.5/snappy-java-1.1.10.5.jar -o /opt/spark/jars/org.xerial.snappy_snappy-java-1.1.10.5.jar
RUN curl -L -o /opt/spark/jars/delta-storage-3.2.0.jar https://repo1.maven.org/maven2/io/delta/delta-storage/3.2.0/delta-storage-3.2.0.jar
RUN curl -L -o /opt/spark/jars/ojdbc11-23.7.0.25.01.jar https://repo1.maven.org/maven2/com/oracle/database/jdbc/ojdbc11/23.7.0.25.01/ojdbc11-23.7.0.25.01.jar
RUN apt-get install -y iputils-ping 
USER spark