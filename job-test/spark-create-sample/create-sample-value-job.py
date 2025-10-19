from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp

spark = (
    SparkSession.builder
    .appName("CreateDeltaTables")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .enableHiveSupport()
    .getOrCreate()
)

data_customer = [(1, "Alice"), (2, "Bob"), (3, "Charlie")]
data_order = [(101, 1, 120.5), (102, 2, 320.0)]

df_customer = spark.createDataFrame(data_customer, ["id", "name"]).withColumn("created_at", current_timestamp())
df_order = spark.createDataFrame(data_order, ["order_id", "customer_id", "amount"]).withColumn("created_at", current_timestamp())

df_customer.write.format("delta").mode("overwrite").save("s3a://warehouse/delta/customer")
df_order.write.format("delta").mode("overwrite").save("s3a://warehouse/delta/orders")

spark.sql("CREATE DATABASE IF NOT EXISTS test_db")
spark.sql("CREATE TABLE IF NOT EXISTS test_db.customer USING DELTA LOCATION 's3a://warehouse/delta/customer'")
spark.sql("CREATE TABLE IF NOT EXISTS test_db.orders USING DELTA LOCATION 's3a://warehouse/delta/orders'")

print("✅ Created Delta tables and registered in Hive.")
spark.stop()
