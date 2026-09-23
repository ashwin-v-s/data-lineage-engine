import argparse
import json
from pathlib import Path

import psycopg2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/synthetic_runtime_events.json"),
    )
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as file:
        data = json.load(file)

    events = data["events"]

    password = input("PostgreSQL password: ")

    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="kairos",
        user="postgres",
        password=password,
    )

    inserted = 0
    existing = 0

    try:
        with connection:
            with connection.cursor() as cursor:
                for event in events:
                    datasets = event["inputs"] + event["outputs"]

                    for dataset in datasets:
                        namespace = dataset["namespace"]
                        name = dataset["name"]

                        cursor.execute(
                            """
                            INSERT INTO dataset (
                                source_system,
                                namespace,
                                database_name,
                                schema_name,
                                name,
                                asset_type
                            )
                            VALUES (
                                %s, %s, %s, %s, %s, %s
                            )
                            ON CONFLICT (
                                source_system,
                                namespace,
                                database_name,
                                schema_name,
                                name,
                                asset_type
                            )
                            DO NOTHING
                            RETURNING id
                            """,
                            (
                                "synthetic_openlineage",
                                namespace,
                                "",
                                "",
                                name,
                                "TABLE",
                            ),
                        )

                        if cursor.fetchone():
                            inserted += 1
                        else:
                            existing += 1

    finally:
        connection.close()

    print(
        f"Processed events: {len(events)} | "
        f"Inserted datasets: {inserted} | "
        f"Already existed: {existing}"
    )


if __name__ == "__main__":
    main()