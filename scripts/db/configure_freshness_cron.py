"""Install the 15-minute scheduled freshness trigger in Supabase.

The job calls ``POST /api/v1/internal/freshness/run`` with the secret stored in
Supabase Vault. The secret is never printed or written into cron.job.

Required environment:
    DATABASE_URL                 Supabase Postgres connection
    KAIROS_CRON_SECRET           same value configured on the deployment
    KAIROS_PUBLIC_APP_URL        deployed HTTPS origin

Run:
    python scripts/db/configure_freshness_cron.py
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

JOB_NAME = "kairos-freshness-every-15-minutes"
SECRET_NAME = "kairos_cron_secret"
SCHEDULE = "*/15 * * * *"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> None:
    database_url = _required("DATABASE_URL")
    cron_secret = _required("KAIROS_CRON_SECRET")
    app_url = _required("KAIROS_PUBLIC_APP_URL").rstrip("/")
    parsed = urlsplit(app_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("KAIROS_PUBLIC_APP_URL must be an HTTPS origin")

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_net")

            cur.execute("SELECT id FROM vault.secrets WHERE name = %s", (SECRET_NAME,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "SELECT vault.update_secret(%s, %s, %s, %s)",
                    (
                        existing[0],
                        cron_secret,
                        SECRET_NAME,
                        "Kairos scheduled freshness trigger credential",
                    ),
                )
            else:
                cur.execute(
                    "SELECT vault.create_secret(%s, %s, %s)",
                    (
                        cron_secret,
                        SECRET_NAME,
                        "Kairos scheduled freshness trigger credential",
                    ),
                )

            cur.execute("SELECT 1 FROM cron.job WHERE jobname = %s", (JOB_NAME,))
            if cur.fetchone():
                cur.execute("SELECT cron.unschedule(%s)", (JOB_NAME,))

            endpoint = f"{app_url}/api/v1/internal/freshness/run"
            command = f"""
                SELECT net.http_post(
                    url := '{endpoint}',
                    headers := jsonb_build_object(
                        'Content-Type', 'application/json',
                        'X-Kairos-Cron-Secret',
                        (SELECT decrypted_secret FROM vault.decrypted_secrets
                         WHERE name = '{SECRET_NAME}')
                    ),
                    body := '{{}}'::jsonb,
                    timeout_milliseconds := 25000
                ) AS request_id;
            """
            cur.execute("SELECT cron.schedule(%s, %s, %s)", (JOB_NAME, SCHEDULE, command))
            job_id = cur.fetchone()[0]

            cur.execute(
                "SELECT jobid, schedule, active FROM cron.job WHERE jobid = %s",
                (job_id,),
            )
            print("scheduled", cur.fetchone())
            print("endpoint", endpoint)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
