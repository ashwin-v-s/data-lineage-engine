import argparse
import getpass
import hashlib
import json
from pathlib import Path

import psycopg2


def payload_hash(event):
    canonical = json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def event_id(event):
    if event.get("eventId"):
        return str(event["eventId"])
    return payload_hash(event)


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
                    eid = event_id(event)
                    phash = payload_hash(event)

                    cursor.execute(
                        """
                        INSERT INTO raw_event (
                            event_id,
                            payload,
                            payload_hash,
                            source_system
                        )
                        SELECT %s, %s::jsonb, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM raw_event
                            WHERE event_id = %s
                               OR payload_hash = %s
                        )
                        """,
                        (
                            eid,
                            json.dumps(event),
                            phash,
                            "synthetic_openlineage",
                            eid,
                            phash,
                        ),
                    )

                    if cursor.rowcount == 1:
                        inserted += 1
                    else:
                        skipped += 1
    finally:
        connection.close()

    print(
        f"Processed: {len(events)} | "
        f"Inserted: {inserted} | "
        f"Skipped duplicates/retries: {skipped}"
    )


if __name__ == "__main__":
    main()
