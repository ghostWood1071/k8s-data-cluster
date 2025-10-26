from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, date_format

spark = (
    SparkSession.builder
    .appName("CreateDeltaTables")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .enableHiveSupport()
    .getOrCreate()
)

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")

data_customer = [
    (1, "Alice", "alice1@gmail.com", ),
    (2, "Bob", "bob.lol@gmail.com"),
    (3, "Charlie", "charlice_hi@gmail.com")
]

df_customer = spark.createDataFrame(data_customer, ["id", "name", "email"]).withColumn("created_at", current_timestamp())
df_customer = df_customer.withColumn("partition_date", date_format(df_customer["created_at"], "yyyy-MM-dd"))

(df_customer.write
   .format("delta")
   .mode("append")
   .partitionBy("partition_date")
   .saveAsTable("bronze.customer_raw"))

print("✅ Created Delta tables and registered in Hive.")
spark.stop()
