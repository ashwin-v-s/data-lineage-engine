# Kairos: Five-Person Working Session (2–3 Hours)

**Shared target:** deliver one honest end-to-end demo slice using the team's shared Supabase project: authenticated personal workspace → validate/preview a small metadata graph JSON file → explicitly import once → read persisted assets/relationships back in the dashboard. Architecture contract: [`KAIROS_FINAL_ARCHITECTURE.md`](KAIROS_FINAL_ARCHITECTURE.md). The implementation branch is `codex/supabase-auth-hardening`.

## Before parallel work (first 15 minutes)

1. Everyone pulls the branch and reads the architecture plus their numbered workstream file. Use the shared Supabase project for product data; local PostgreSQL setup is not part of this demo.
2. Agree the smallest `kairos.ingest.v1` JSON fixture and field meanings. The backend workstream owns changes to the draft contract; adapter/UI workers report proposed changes before changing it.
3. Agree one shared Supabase project and API base URL. Apply schema migrations once through the migration owner. Do not share `.env`, OAuth secrets, database passwords, or private source tokens in chat/Git.
4. Assign one migration owner to check the shared project's migration state and apply any missing migration once. Assign one person to merge and run the acceptance checklist; workers commit to separate branches and open PRs. Do not edit the same files across tracks.

## Workstreams

| Person | Plan | Independent ownership | End-of-session deliverable |
|---|---|---|---|
| 1 | [`workstreams/M1_STATIC_AND_FILE_ADAPTERS.md`](workstreams/M1_STATIC_AND_FILE_ADAPTERS.md) | File inventory, metadata graph, SQL/dbt adapters | A deterministic adapter result and fixtures; no database writes |
| 2 | [`workstreams/M2_OPENLINEAGE_RUNTIME_ADAPTER.md`](workstreams/M2_OPENLINEAGE_RUNTIME_ADAPTER.md) | OpenLineage event normalization and semantics | Event fixtures and normalized evidence; no product DB or UI edits |
| 3 | [`workstreams/M3_INGESTION_API_AND_STORAGE.md`](workstreams/M3_INGESTION_API_AND_STORAGE.md) | Versioned preview/commit API, persistence, RLS | Authenticated idempotent import/readback endpoint tested against the shared Supabase project |
| 4 | [`workstreams/M4_RESEARCH_INTEGRITY_AND_EVALUATION.md`](workstreams/M4_RESEARCH_INTEGRITY_AND_EVALUATION.md) | Four-state rules, ground-truth isolation, acceptance evidence | Regression tests for semantics and a clear test report |
| 5 | [`workstreams/M5_FRONTEND_DEMO_FLOW.md`](workstreams/M5_FRONTEND_DEMO_FLOW.md) | React/Vite import/preview flow and catalog readback | Usable UI wired to the agreed API contract; no mock “successful import” |

## Timebox

- **0:00–0:15** Pull, ownership, contract and fixture agreement.
- **0:15–1:30** Independent implementation with a short check-in at 0:55.
- **1:30–2:15** Merge in this order: M3 contract/API → M1/M2 adapters → M5 UI → M4 integrity gate. Resolve interface differences before polish.
- **2:15–3:00** Run the demo using a fresh user/workspace in the shared Supabase project; capture failures, exact commands, and remaining manual setup. Do not claim end-to-end success if the Supabase project or migration has not been configured.

## Stop conditions

- If migration 0003 is not applied to the shared Supabase DB, keep the database import integration behind a clearly reported setup dependency; never bypass RLS for the demo.
- Do not run local database install, drop, reset, or seed commands as a substitute for the shared Supabase project. Use only a separate isolated database for research-specific experiments.
- If OAuth providers are not configured, email/password may be used if available. Do not fake a provider sign-in.
- If a file format does not validate, show diagnostics and use the agreed sample fixture. Do not silently turn unsupported content into an empty successful import.
- Keep the public GitHub browser as discovery/preview until an actual authenticated import route is complete.
