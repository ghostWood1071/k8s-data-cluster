-- Tạo role/user airflow (login)
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow') THEN
      CREATE ROLE airflow LOGIN PASSWORD 'airflow';
   END IF;
END$$;

-- Tạo database airflow, set owner = airflow
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow') THEN
      CREATE DATABASE airflow OWNER airflow;
   END IF;
END$$;

-- Trao quyền tổng quát trên DB (owner đã đủ, nhưng grant thêm cho rõ ràng)
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;

-- Chuyển ngữ cảnh sang DB airflow để set quyền schema/tương lai
\connect airflow

-- Đảm bảo schema public thuộc về airflow
ALTER SCHEMA public OWNER TO airflow;

-- Đặt search_path mặc định
ALTER ROLE airflow SET search_path = public;

-- Mặc định quyền cho các object tạo mới trong tương lai
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO airflow;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO airflow;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO airflow;
