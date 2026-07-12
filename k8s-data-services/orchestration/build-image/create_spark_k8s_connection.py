from __future__ import annotations

from airflow.models.connection import Connection
from airflow.settings import Session


CONN_ID = "spark_k8s"


def main() -> None:
    session = Session()
    try:
        session.query(Connection).filter(Connection.conn_id == CONN_ID).delete()
        conn = Connection(
            conn_id=CONN_ID,
            conn_type="spark",
            host="k8s://https://kubernetes.default.svc",
            extra={
                "deploy-mode": "cluster",
                "spark-binary": "spark-submit",
                "namespace": "compute",
            },
        )
        session.add(conn)
        session.commit()
        saved = session.query(Connection).filter(Connection.conn_id == CONN_ID).one()
        print(saved.get_uri())
    finally:
        session.close()


if __name__ == "__main__":
    main()
