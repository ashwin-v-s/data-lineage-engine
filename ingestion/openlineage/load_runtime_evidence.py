import argparse
import getpass
import json
from datetime import datetime
from pathlib import Path

import psycopg2


def parse_event_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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

    password = getpass.getpass("PostgreSQL password: ")

    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="kairos",
        user="postgres",
        password=password,
    )

    inserted = 0
    skipped = 0

    try:
        with connection:
            with connection.cursor() as cursor:
                for event in events:
                    run_id = event["run"]["runId"]
                    event_time = parse_event_time(event["eventTime"])
                    event_id = event.get("eventId")

                    if not event_id:
                        import hashlib

                        canonical = json.dumps(
                            event,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        event_id = hashlib.sha256(
                            canonical.encode("utf-8")
                        ).hexdigest()

                    evidence_id = f"runtime:{event_id}"

                    source = event["inputs"][0]
                    target = event["outputs"][0]

                    cursor.execute(
                        """
                        SELECT id
                        FROM dataset
                        WHERE source_system = %s
                          AND namespace = %s
                          AND name = %s
                        """,
                        (
                            "synthetic_openlineage",
                            source["namespace"],
                            source["name"],
                        ),
                    )
                    source_row = cursor.fetchone()

                    cursor.execute(
                        """
                        SELECT id
                        FROM dataset
                        WHERE source_system = %s
                          AND namespace = %s
                          AND name = %s
                        """,
                        (
                            "synthetic_openlineage",
                            target["namespace"],
                            target["name"],
                        ),
                    )
                    target_row = cursor.fetchone()

                    if not source_row or not target_row:
                        raise RuntimeError(
                            f"Dataset missing for event {event_id}"
                        )

                    cursor.execute(
                        """
                        INSERT INTO evidence (
                            evidence_id,
                            evidence_type,
                            source_system,
                            run_id,
                            source_dataset_id,
                            target_dataset_id,
                            granularity,
                            parser_status,
                            coverage,
                            event_time,
                            effective_time,
                            diagnostics,
                            raw_event_id
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s,
                            %s::jsonb, %s, %s, %s::jsonb, %s
                        )
                        ON CONFLICT (evidence_id)
                        DO NOTHING
                        """,
                        (
                            evidence_id,
                            "RUNTIME_OBSERVED",
                            "synthetic_openlineage",
                            run_id,
                            source_row[0],
                            target_row[0],
                            "DATASET",
                            "SYNTHETIC_RUNTIME",
                            json.dumps({
                                "inputs": 1,
                                "outputs": 1,
                                "column_level": False,
                            }),
                            event_time,
                            event_time,
                            json.dumps([
                                "SYNTHETIC - shaped like OpenLineage, "
                                "not from a live pipeline."
                            ]),
                            event_id,
                        ),
                    )

                    if cursor.rowcount == 1:
                        inserted += 1
                    else:
                        skipped += 1

    finally:
        connection.close()

    print(
        f"Processed events: {len(events)} | "
        f"Inserted evidence: {inserted} | "
        f"Skipped duplicates: {skipped}"
    )


if __name__ == "__main__":
    main()