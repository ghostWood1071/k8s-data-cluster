import os

def get_hostname():
    """
    Return a static hostname for Airflow scheduler API,
    fetched from environment variable AIRFLOW_SCHEDULER_SERVICE_NAME.
    """
    return os.getenv("AIRFLOW_SCHEDULER_SERVICE_NAME", "airflow-scheduler-service")
