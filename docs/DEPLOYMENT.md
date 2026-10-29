# Kairos Deployment Runbook

This is the operational runbook for deploying the Kairos API + frontend. It
covers the shared **Supabase** project (Auth + hosted PostgreSQL), database
migrations, **Vercel** hosting, health verification, rollback, and the honest
list of things that are **not** production-ready yet.

It complements, and does not replace, [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md)
(project setup and feature status) and
[`../backend/migrations/README.md`](../backend/migrations/README.md)
(migration semantics and grants).

---

## 1. Prerequisites

- A Supabase project (the shared Kairos project). Do not create a per-person
  project.
- Vercel access to the team project, or the Vercel CLI (`npm i -g vercel`).
- Python 3.11+ and Node 20+/22 for local builds.
- The exact Supabase values below, copied from the dashboard, **never guessed**.

### Supabase project settings you need

| Setting | Where to find it | Used as |
| --- | --- | --- |
| Project URL | Project Settings → API (`https://PROJECT_REF.supabase.co`) | `SUPABASE_URL` |
| Publishable key (older projects: `anon`) | Project Settings → API | `SUPABASE_PUBLISHABLE_KEY` |
| Pooler connection string (URI) | Project Settings → Database → Connection string → **Transaction pooler** | `DATABASE_URL` |

The pooler URI already contains the project-specific host and database
password. The `service_role` key is **never** used by this application and must
never be placed in the browser or in a `VITE_*` variable.

Configure the project's Auth URL configuration and redirect allow-list for the
deployed frontend origin (and `http://127.0.0.1:8000` / `http://localhost:3000`
for local work).

---

## 2. Environment variables (authoritative)

Derived by reading the code (`os.getenv` / `import.meta` usage), not from
memory. `Secret?` marks whether the value may be handled as a secret.

| Variable | Read by | When | Secret? | If missing |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | `backend/app/db.py` (connection pool), `scripts/*`, `ingestion/openlineage/etl_demo.py` | **Runtime** (backend). Not needed to build the frontend. | **Yes** | Pool creation raises; every authenticated route fails. The API cannot serve data. |
| `SUPABASE_URL` | `backend/app/auth.py::supabase_auth_url`, `backend/app/main.py` (`/api/v1/auth/config`) | Runtime (backend) | No (public project URL) | `require_user` raises **503 AUTH_UNAVAILABLE**; no route can be used. |
| `SUPABASE_PUBLISHABLE_KEY` | `backend/app/auth.py` (sent as `apikey`), `/api/v1/auth/config` | Runtime (backend) | No (publishable/anon key; safe to expose, but keep it server-side config) | Auth verification still attempts without the `apikey` header; keep it set. |
| `VITE_SUPABASE_URL` | `backend/app/auth.py`, `backend/app/main.py` (fallbacks only) | Runtime (backend) | No | Optional. Only used if `SUPABASE_URL` is unset. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | `backend/app/auth.py`, `backend/app/main.py` (fallbacks only) | Runtime (backend) | No | Optional. Only used if `SUPABASE_PUBLISHABLE_KEY` is unset. |
| `FRONTEND_ORIGIN` | `backend/app/main.py` (CORS `allow_origins`) | Runtime (backend) | No | Defaults to `http://localhost:3000`; a deployed frontend on a different origin will fail CORS. |
| `KAIROS_LIVE_API_TESTS` | `tests/conftest.py` | Test-time only | No | Unset ⇒ live integration tests are skipped (the default, offline suite still runs). |
| `KAIROS_ENV` | — (declared in `.env.example`, not read by current code) | — | No | No effect today; reserved. |
| `KAIROS_LOG_LEVEL` | — (declared in `.env.example`, not read by current code) | — | No | No effect today; reserved. |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | — (not read by current code) | — | Yes (password) | No effect today; only relevant if the optional graph projection gate (D-06) is passed. |

### Frontend variables

The frontend has **no build-time environment variables**. It reads its Supabase
configuration at runtime from `GET /api/v1/auth/config` (see
`frontend/auth.js::boot`). Consequently `VITE_*` variables are **not** required
to build `frontend/dist`; they exist only as backend fallbacks.

> Rule: never prefix a real secret with `VITE_`. Anything named `VITE_*` is
> intended to be safe to ship to the browser. A database password, a
> `service_role` key, or any server-only credential must never use that prefix.

---

## 3. Database migrations

Migrations are **forward-only** and must be applied in numeric order by a
single migration owner using a **privileged** connection (the Supabase project
owner / `postgres` role, or a role that can create roles, policies, and
security-definer functions).

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0001_core.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0002_audit_ownership_metadata.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0003_personal_workspaces.sql
```

- `0001_core.sql` — foundational schema (datasets, columns, jobs, runs, raw
  events, evidence, lineage edges, bitemporal versions, execution state).
- `0002_audit_ownership_metadata.sql` — ownership, description, audit, version,
  and rollback tables used by the governance API.
- `0003_personal_workspaces.sql` — personal workspace provisioning, forced
  row-level security, and the `kairos_workspace_isolation` policy. **Required
  for any authenticated route to work**: without it, `require_user` fails closed
  with **503** when it cannot provision a workspace.
- `0004_ingestion_import_runs.sql` — **NOT applied**. It is a local proposal
  for the M3 persistent import/import-run record and must be reviewed and
  authorized by M3 before deployment.

> ⚠️ **Do not run destructive or reset commands against the shared project.**
> Never run `DROP`, `TRUNCATE`, `DELETE` without a `WHERE`, `ALTER ... DROP`,
> `prisma migrate reset`, or a local "recreate from scratch" flow against the
> shared database. Test destructive experiments on a separate Supabase
> project/branch or an isolated local database.

The API's database login must be a member of `kairos_app` and able to execute
`public.kairos_ensure_personal_workspace(uuid)`. See the grants section of
[`../backend/migrations/README.md`](../backend/migrations/README.md).

---

## 4. Vercel deployment

- **Project root:** the repository root. `vercel.json` lives there.
- **Build command / output directory:** taken from `vercel.json`
  (`npm --prefix frontend ci && npm --prefix frontend run build`;
  output `frontend/dist`). Do not override these in the dashboard.
- **Serverless function:** `backend/api/index.py` exports the FastAPI `app`
  (see `pyproject.toml` → `[tool.vercel] entrypoint =
  "backend.api.index:app"`). It re-exports the same `app` object, with no
  import-time side effects beyond constructing the FastAPI instance.
- **Routing / rewrites** (`vercel.json` → `rewrites`):
  - `/healthz` → the Python function (unauthenticated liveness probe).
  - `/api/(.*)` → the Python function (all `/api/v1/...` routes).
  - `/ingestion.html` → the Python function (auth-gated ingestion page).
  - Everything else is served as static files from `frontend/dist`.
  - ⚠️ A **new top-level route** on the Python function (anything not under
    `/api/`) requires a matching `rewrites` entry, or it will be treated as a
    missing static file and return 404.

### Environment variables to set in the Vercel dashboard

Set these for the **Production** (and Preview, as needed) environment:

- `DATABASE_URL` — the Supabase transaction-pooler URI (**secret**).
- `SUPABASE_URL` — project URL.
- `SUPABASE_PUBLISHABLE_KEY` — publishable/anon key.
- `FRONTEND_ORIGIN` — the deployed frontend origin, e.g.
  `https://kairos.example.com` (no trailing slash; CORS compares exactly one
  origin).
- Optional: `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (fallbacks).

`DATABASE_URL` and the pooler password are secrets — store them as Vercel
encrypted environment variables and never commit them.

### Deploying

```bash
vercel            # preview deployment
vercel --prod     # production deployment
```

Or connect the Git repository so pushes deploy automatically. CI does **not**
deploy (see `.github/workflows/ci.yml`); release is a manual/team decision.

---

## 5. Verifying a deployment is healthy

1. **Liveness (unauthenticated, no database):**

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://<deployment>/healthz
   # expect 200, body {"status":"ok","service":"kairos-api"}
   ```

   A 200 here means the Python function is running. It says nothing about the
   database or Supabase.

2. **Readiness (authenticated, database-backed):**

   ```bash
   curl -s -H "Authorization: Bearer <supabase-access-token>" \
     https://<deployment>/api/v1/health
   # expect 200 {"status":"ok","db":"connected"}
   ```

   `/api/v1/health` requires a valid Supabase session, so a `curl` without a
   token cannot use it as a platform probe — use `/healthz` for that.

3. **Telling a 401 from a 503** (both use the stable `{"error": {...}}`
   envelope and carry `X-Request-ID`):
   - **401 `UNAUTHENTICATED`** — Supabase was reachable but the request had no
     valid session (missing/expired token, or a rejected session).
   - **503 `AUTH_UNAVAILABLE`** — the auth/workspace layer is not ready:
     `SUPABASE_URL` is unset, the Auth service is unreachable, or the database
     / workspace provisioning failed (commonly **migration 0003 not applied**,
     or the API login is not a member of `kairos_app`).

   So: 401 = "you are not signed in"; 503 = "the server cannot verify you
   right now". A healthy signed-in request should be 200.

---

## 6. Rollback

- **Application (Vercel):** use the dashboard's *Instant Rollback* / promote a
  previous deployment, or redeploy a known-good Git commit with
  `vercel --prod`. Rolling back the app does **not** roll back the database.
- **Database:** migrations are forward-only. There is no down-migration. To
  recover, either restore from a Supabase backup/point-in-time recovery, or
  apply a new, reviewed migration that corrects the change. Do not attempt to
  reverse an applied migration in place.
- **Config/secrets:** environment variables are versioned by the hosting
  platform; revert them in the Vercel dashboard and redeploy.

---

## 7. Known limitations / not production-ready

Be explicit about these before treating any deployment as production:

- **Fail-closed authentication depends on Supabase being reachable.** Every
  route except `/api/v1/auth/config` and `/healthz` calls `require_user`, which
  performs a live Supabase `/auth/v1/user` verification. If Supabase Auth is
  down, all authenticated routes fail closed with 503.
- **Migration 0003 must be applied** for any authenticated route to work. It
  powers workspace provisioning and row-level isolation; without it the API
  returns 503 (see §3 and §5).
- **No Docker image** is provided; hosting is Vercel (Python function) +
  Supabase. There is no container build in this repository.
- **The persistent import API is not implemented.** Migration
  `0004_ingestion_import_runs.sql` is an unapplied proposal; the M3
  persistent import/preview flow is application work that is not done.
- **Serverless database pooling caveats.** `backend/app/db.py` uses a
  `psycopg2` `ThreadedConnectionPool` created lazily per process. Under
  serverless concurrency each function instance holds its own pool against the
  Supabase pooler; size the pooler limits accordingly.
- **Function timeout.** The Vercel function is configured with
  `maxDuration: 30`; long-running ingestion/research work should not run inside
  the request path.
- **Optional integrations are not wired.** Neo4j projection and Storage-based
  raw-file retention are design options, not part of the current request path
  (see [`SUPABASE_FEATURE_ADOPTION.md`](SUPABASE_FEATURE_ADOPTION.md)).

---

## 8. CORS and secrets

- **`FRONTEND_ORIGIN`** must equal the deployed frontend origin exactly (scheme
  + host, no trailing slash). `backend/app/main.py` builds
  `CORSMiddleware(allow_origins=[frontend_origin], allow_credentials=False)`.
  Locally it defaults to `http://localhost:3000`; set it for every hosted
  environment or browser calls to the API will be blocked.
- **Secrets:** `DATABASE_URL` (and its password) are secret. Store them only in
  the hosting platform's encrypted environment variables and in an untracked
  local `.env`. Never commit `.env`, never paste secrets into source, tests,
  docs, or chat.
- **Never prefix a secret with `VITE_`.** `VITE_*` values are treated as
  browser-visible. The Supabase **publishable/anon** key is safe to expose; the
  **`service_role`** key and any database credential are not, and must stay
  server-side (`SUPABASE_*` / `DATABASE_URL`, no `VITE_` prefix).
