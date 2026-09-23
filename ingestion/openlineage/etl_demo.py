import json
import os
import uuid
from datetime import datetime, timezone

import psycopg2

from openlineage.client import OpenLineageClient
from openlineage.client.event_v2 import (
    InputDataset,
    Job,
    OutputDataset,
    Run,
    RunEvent,
    RunState,
)
from openlineage.client.transport.file import FileConfig, FileTransport


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/kairos",
)

EVENT_FILE = "runtime_events.json"


def run_etl():
    run_id = str(uuid.uuid4())

    # --------------------------------------------------
    # 1. Connect to PostgreSQL
    # --------------------------------------------------
    connection = psycopg2.connect(DATABASE_URL)

    try:
        cursor = connection.cursor()

        # --------------------------------------------------
        # 2. Create a small input table
        # --------------------------------------------------
        cursor.execute("""
            DROP TABLE IF EXISTS employees_a;

            CREATE TABLE employees_a (
                country TEXT,
                salary INTEGER
            );

            INSERT INTO employees_a (country, salary)
            VALUES
                ('US', 50000),
                ('IN', 40000),
                ('US', 70000),
                ('UK', 45000);
        """)

        # --------------------------------------------------
        # 3. Run the actual ETL transformation
        # --------------------------------------------------
        cursor.execute("""
            DROP TABLE IF EXISTS out_adjusted;

            CREATE TABLE out_adjusted AS
            SELECT
                country,
                CASE
                    WHEN country = 'US' THEN salary
                    ELSE 0
                END AS adjusted_salary
            FROM employees_a;
        """)

        connection.commit()

        print("ETL completed successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

    # --------------------------------------------------
    # 4. Create OpenLineage client
    # --------------------------------------------------
    transport = FileTransport(
        FileConfig(
            log_file_path=EVENT_FILE,
            append=True,
        )
    )

    client = OpenLineageClient(transport=transport)

    job = Job(
        namespace="kairos",
        name="employee_salary_adjustment",
    )

    run = Run(runId=run_id)

    input_dataset = InputDataset(
        namespace="postgresql://localhost:5432/kairos",
        name="employees_a",
    )

    output_dataset = OutputDataset(
        namespace="postgresql://localhost:5432/kairos",
        name="out_adjusted",
    )

    producer = "kairos-m2-runtime-ingestion"

    # --------------------------------------------------
    # 5. Emit START event
    # --------------------------------------------------
    client.emit(
        RunEvent(
            eventType=RunState.START,
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=run,
            job=job,
            producer=producer,
        )
    )

    # --------------------------------------------------
    # 6. Emit COMPLETE event
    # --------------------------------------------------
    client.emit(
        RunEvent(
            eventType=RunState.COMPLETE,
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=run,
            job=job,
            producer=producer,
            inputs=[input_dataset],
            outputs=[output_dataset],
        )
    )

    client.close()

    print(f"OpenLineage events written to: {EVENT_FILE}")
    print(f"Run ID: {run_id}")


if __name__ == "__main__":
    run_etl()