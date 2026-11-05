# Supabase feature fit for Kairos

**Verified against the shared project:** 2026-10-29  
**Purpose:** use Supabase features where they support the Kairos product architecture; keep project features that lack a safe, implemented consumer out of the request path.

## Current live state

- Supabase Auth responds successfully. Email sign-in is enabled and email confirmation is required. The project has no registered Auth users. Google, GitHub, and Azure/Microsoft are disabled.
- Supabase Postgres is the authoritative product database. Migrations 0001–0003 are applied. The 17 business tables have forced workspace RLS; existing records remain in the private legacy workspace. The restricted `kairos_app` role sees no rows without workspace context.
- The PostgREST Data API is reachable, but Kairos browser catalog reads go through FastAPI so the server can set the verified workspace context before querying RLS tables.
- A `supabase_realtime` publication exists with no published tables.
- Supabase Storage is available, with no buckets.
- Installed Postgres extensions include `uuid-ossp`, `pgcrypto`, and `supabase_vault`. Vault has no Kairos integration or stored source credentials.
- No Supabase Management API token, service-role/secret API key, SMTP credentials, or Google/GitHub/Microsoft OAuth client credentials are configured in the local environment.

## Adoption decisions

| Supabase capability | Kairos use | Decision and reason |
|---|---|---|
| Hosted Postgres | Catalog, lineage, evidence, audit, personal workspaces | **Use.** It is the system of record. FastAPI transactions set the server-derived workspace context and switch to `kairos_app`. |
| Auth | Email/password, confirmation, OAuth identity | **Use.** Existing frontend and backend call Supabase Auth. Email confirmation is required. Social providers stay unavailable until provider client credentials and callback configuration are supplied. |
| PostgREST / generated APIs | Direct SQL-backed browser data access | **Do not use for catalog reads.** Current workspace RLS depends on a transaction-local database setting populated by FastAPI. A browser JWT does not set that value, so direct browser queries would not have the correct workspace context. Keep authenticated catalog access behind FastAPI. |
| Storage | Retention of uploaded source files | **Optional; leave unused for the current demo.** The architecture calls for parsing a selected local artifact and persisting normalized metadata/provenance; the current UI only previews locally and the import endpoint is not implemented. No original-file retention requirement exists. Add a private bucket and owner-scoped Storage policies if one is adopted. Never make a source bucket public. |
| Realtime | Live import progress or catalog refresh | **Defer.** There is no implemented persistent import-status API yet, no tables in the Realtime publication, and direct table subscriptions do not receive the FastAPI transaction-local workspace context. Revisit after M3 defines an authenticated event path and proves tenant-safe authorization. |
| Edge Functions | API and ingestion compute | **Do not duplicate FastAPI.** Kairos keeps ingestion adapters, validation, and product APIs in Python as the architecture specifies. Consider a small Edge Function only for a concrete Supabase-hosted webhook/Auth-hook use case. |
| Vault | External database/source credentials | **Available for a later connector.** No source-connection management flow currently stores or retrieves credentials. Add only with a server-side connector, access controls, rotation, and audit trail. Never store credentials in browser storage or plain metadata. |
| Cron / Queues | Scheduled ingestion and asynchronous retries | **Defer.** The current milestone has no scheduled connector or durable background job contract. Use these when a measured workflow requires it. |
| Vector / Analytics buckets / GraphQL | Search embeddings, lake analytics, or direct graph API | **Not needed for the current product path.** Kairos has no vector-search or lake workload, and GraphQL would duplicate the existing versioned API. |

## Remaining setup and implementation gates

1. Configure custom SMTP and verify the confirmation/reset email flow with a real test account. Hosted Supabase's built-in email service is restricted for production use; use the Auth dashboard's SMTP settings for broader delivery.
2. Enable Google, GitHub, and Microsoft only after creating OAuth applications, adding their client IDs/secrets in Supabase Auth, and registering exact callback/redirect URLs.
3. M3 owns the shared import envelope and persistent preview/commit endpoint. A local draft `backend/migrations/0004_ingestion_import_runs.sql` exists but is **not applied**; M3 must review its fields before shared deployment.
4. Add Storage only if product requirements call for retained originals. Add Realtime only after an event authorization design fits workspace isolation.
5. Keep management/service-role secrets out of `VITE_*` variables, source control, and chat. Database credentials pasted into chat should be rotated.

## Official Supabase references

- [Supabase Platform](https://supabase.com/docs/guides/platform)
- [Auth](https://supabase.com/docs/guides/auth)
- [Custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp)
- [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Storage](https://supabase.com/docs/guides/storage)
- [Realtime](https://supabase.com/docs/guides/realtime)
- [Edge Functions](https://supabase.com/docs/guides/functions)
- [Database Vault](https://supabase.com/docs/guides/database/vault)
