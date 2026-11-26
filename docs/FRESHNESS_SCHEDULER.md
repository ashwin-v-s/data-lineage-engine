# Scheduled freshness evaluation

Kairos evaluates due freshness SLAs every 15 minutes. The scheduler runs inside
the shared Supabase Postgres project with `pg_cron`, calls a secret-protected
API route with `pg_net`, and evaluates each target under its own workspace RLS
scope.

## Runtime path

1. `cron.job` runs `kairos-freshness-every-15-minutes`.
2. The job posts to `POST /api/v1/internal/freshness/run` with
   `X-Kairos-Cron-Secret`, read from Supabase Vault.
3. `backend/app/services/freshness_runner.py` selects due, non-paused,
   non-manual SLAs across workspaces.
4. Each SLA is evaluated after `set_workspace_id(workspace_id)`, so the normal
   `kairos_app` RLS scope applies.
5. A breach opens or reuses one incident, writes the `DETECTED` event, creates
   the in-app notification, and dispatches its email copy after commit.

Scheduled evaluations are stored with `evaluation_mode = 'SCHEDULED'` and no
human actor on the incident event. Manual evaluations remain `MANUAL`.

## Cadence

The database job wakes every 15 minutes. It only evaluates SLAs whose latest
evaluation is older than their configured interval:

| SLA schedule | Minimum interval between evaluations |
| --- | --- |
| `15m` | 15 minutes |
| `hourly` | 60 minutes |
| `daily` | 24 hours |
| `manual` | never scheduled |

A failed target is logged and skipped; the remaining workspaces still run.

## Configuration

The deployment needs:

| Variable | Purpose |
| --- | --- |
| `KAIROS_CRON_SECRET` | Shared secret required by the internal route |
| `KAIROS_FRESHNESS_SCHEDULE_ENABLED=true` | Reports non-manual SLAs as `SCHEDULED` instead of `BLOCKED` |
| `KAIROS_PUBLIC_APP_URL` | HTTPS origin used by the cron job |

After deploying the code and setting those variables, install or update the
database job:

```bash
python scripts/db/configure_freshness_cron.py
```

The script enables `pg_cron` and `pg_net`, stores the secret in Supabase Vault,
removes an older copy of the job, and schedules a fresh one. It does not print
the secret or write it into `cron.job`.

## Verification

```bash
# The job exists and is active
psql "$DATABASE_URL" -c \
  "select jobid, jobname, schedule, active from cron.job where jobname = 'kairos-freshness-every-15-minutes';"

# Recent runs and HTTP responses
psql "$DATABASE_URL" -c \
  "select status, return_message, start_time from cron.job_run_details order by start_time desc limit 5;"
psql "$DATABASE_URL" -c \
  "select status_code, content, created from net._http_response order by created desc limit 5;"
```

The internal route fails closed with `503` when `KAIROS_CRON_SECRET` is absent
and `401` when the supplied header does not match.
