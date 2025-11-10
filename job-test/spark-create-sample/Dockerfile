from apache/spark:3.5.7-scala2.12-java17-python3-ubuntu

RUN apt-get update && apt-get install -y curl
RUN curl -L -o /opt/spark/jars/hadoop-aws-3.3.4.jar https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar
RUN curl -L -o /opt/spark/jars/aws-java-sdk-1.11.901.jar https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk/1.11.901/aws-java-sdk-1.11.901.jar
RUN curl -L -o /opt/spark/jars/delta-spark_2.12-3.2.0.jar https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.0/delta-spark_2.12-3.2.0.jar
RUN curl -L -o /opt/spark/jars/postgresql-42.7.3.jar https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar
RUN curl -L -o /opt/spark/jars/hive-metastore-3.1.3.jar https://repo.maven.apache.org/maven2/org/apache/hive/hive-metastore/3.1.3/hive-metastore-3.1.3.jar
RUN curl -L -o /opt/spark/jars/hive-exec-3.1.3.jar https://repo.maven.apache.org/maven2/org/apache/hive/hive-exec/3.1.3/hive-exec-3.1.3.jar
