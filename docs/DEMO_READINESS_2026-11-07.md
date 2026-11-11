# Kairos: ten-demo readiness

This is a code and environment audit for the ten-demo brief supplied on 2026-11-07. A feature is called **working** only where the current implementation supports the full flow and the relevant tests/environment checks pass. A UI placeholder or parser unit test alone is not a complete demo.

## Status summary

| # | Demo | Current status | What is still needed for an honest live demo |
|---|---|---|---|
| 1 | Sign-in, workspace isolation, profile | **Partial; database isolation verified** | Supabase Auth and personal workspace provisioning exist. Profile identity fields save to Supabase Auth metadata; picture/preferences remain browser-local. All tracked migrations through 0011 are applied. `kairos_app` is confirmed non-BYPASSRLS; all 42 scoped tables have forced RLS and workspace policies. A rollback-only live test proves cross-workspace reads/inserts/updates are blocked. Still validate two real Supabase users and their normal API tokens end to end. |
| 2 | PostgreSQL source discovery | **Partial; five disposable sources provisioned and adapter verified** | Five isolated logical databases were created in the existing Supabase PostgreSQL project with a read-only connector role. The actual PostgreSQL adapter discovered both tables and columns on each source twice with stable content hashes; write attempts were denied. A local token-encryption key is now present in the ignored `.env`; restart the backend to load it. The signed-in UI/API flow for test → preview → sync → catalog readback still needs a real user session. These are databases on one Supabase cluster, not separate Supabase projects. |
| 3 | Local folder/file ingestion | **Partial; implementation expanded in this branch** | Browser directory selection now displays a real local tree, previews locally, imports inventory, and can ingest a selected file. SQL files go through the SQLGlot adapter. Browser folder access is permission-scoped to the selected directory, not a background scan of the whole machine. Import persistence requires the live `import_run` migration and authenticated session. |
| 4 | GitHub repository browsing | **Implemented; live setup gated** | The Integrations screen supports the authenticated GitHub App connect/callback, workspace connection list/disconnect, authorized repository and branch selection, tree browsing, UTF-8 preview, validated import preview, and explicit idempotent catalog commit for supported metadata graph, SQL, dbt manifest, and CSV header files. Public repo browse remains separate. Configure the GitHub App and encryption key, install it for a test repository, and exercise the flow on the deployed callback URL. |
| 5 | SQL parsing and lineage candidates | **Partial; parser wired in this branch** | Selected `.sql` files now parse through SQLGlot. `CREATE TABLE … AS SELECT` and `INSERT … SELECT` create static table candidates and preserve SQL in raw import evidence. A plain `SELECT` does not invent a target or lineage edge. Column-level mapping and canonical asset reconciliation remain incomplete. Parsing is not runtime evidence. |
| 6 | dbt manifest | **Parser implemented; live path partial** | The pure manifest parser is registered with the authenticated import preview/commit API. Exercise a new manifest through preview, commit, catalog, lineage, and evidence on the live schema; confirm tests are represented as expected before claiming the full brief's test-definition acceptance. |
| 7 | OpenLineage runtime event | **Secured; workspace-bound; live setup gated** | Event ingest now requires both the bearer secret and `KAIROS_OPENLINEAGE_WORKSPACE_ID`, then scopes all writes through `kairos_app` RLS. The deployment binding is single-workspace; it is not the multi-tenant webhook credential registry needed for a shared hosted service. Configure both values on backend and the secret on producer, then validate event readback. |
| 8 | Coverage-aware lineage | **Partial** | Lineage and evidence APIs/views exist and the observatory interaction defects fixed in this branch are covered by UI tests. Do not equate graph visibility with complete evidence-based coverage, column lineage, or time travel; those need explicit live acceptance cases. |
| 9 | Freshness, quality, incident lifecycle | **Partial** | `sync_job` is present after migration 0010; freshness, quality and incident read routes return 200 against the live schema. Writes/readback for the whole lifecycle, scheduler execution, and notification delivery remain unverified. Scheduler decision is pending the M1/M2 owners. |
| 10 | Glossary, PII, domains, products | **Storage applied; live user-flow unverified** | The governance migration is now applied and verified in the shared database with forced workspace RLS. React governance screens and APIs exist for terms, classifications, domains, products, and contracts. A real signed-in user flow still must be exercised before claiming the demo complete. |

## Work completed on this branch

- A selected local directory is enumerated only after an explicit browser picker action. The browser shows the path, type, size, modified time, and SHA-256 when within scan limits. It does not silently traverse the user's disk.
- A chosen file can be previewed locally before upload. Import has an explicit button, rejects unsupported types and oversized content, and reports backend failures without substituting fixture data.
- A folder inventory import records file metadata; it does not pretend that the file bytes or lineage were ingested.
- A selected SQL file now enters the same authenticated preview/commit pipeline as other static imports. SQLGlot creates candidate edges only when a target is declared by supported DDL/DML.
- The profile editor now saves identity fields to Supabase Auth user metadata and hydrates the account profile from that metadata. It does not write authorization roles or workspace access to user-editable metadata.
- Governance forms use catalog/domain selections instead of asking users to copy UUIDs. PII column choices are fetched from a new authenticated dataset-columns endpoint, with the existing workspace RLS applied.
- The private GitHub App flow is wired into Integrations. OAuth state is bound to the signed-in Kairos user/workspace on the server and checked against the initiating browser session; tokens remain server-side and encrypted at rest. Repository reads use short-lived installation tokens and are limited to repositories exposed by that installation.
- Private GitHub files now use the same static adapter preview and explicit commit pipeline as uploads. The API records a server-verified GitHub repository/ref/path/blob origin, and repeated commits use the import idempotency key rather than creating duplicate import runs.
- Five disposable source databases were created in the existing Supabase PostgreSQL project with two synthetic tables each and a read-only role. The live PostgreSQL source adapter scanned all five sources twice; each scan returned two assets with stable content hashes, and write attempts were rejected. Local connection details are stored in the Git-excluded `.demo-sources/connections.json` file.
- A fresh AES-256 token-encryption key was added to the ignored local `.env` after confirming that the shared project had no saved source or GitHub connections. Restart the backend before using encrypted connector storage; configure the same key securely on any deployed backend that must decrypt records created with it.
- OpenLineage ingress now requires a configured bearer secret and rejects missing, invalid, or unconfigured webhook authentication before parsing the event body.
- OpenLineage event persistence now sets the server-configured workspace context before database access; missing/invalid workspace binding fails closed, preventing a global webhook key from allowing callers to choose a tenant.
- The observatory pointer/click and rendering defects from this working tree were corrected, and stale UI assertions were updated to match fail-closed behavior.
- Added safe synthetic import fixtures for CSV headers, SQL static lineage, a dbt model with two sources, and a Kairos metadata graph; all four pass their actual parser adapters. The demo runbook now points to these repeatable examples.
- Removed a hard-coded presenter identity from the dashboard greeting and corrected UI copy that incorrectly said existing Notifications/Governance/Incidents workflows had no API support.
- Fixed the membership lifecycle gap: migration 0013 backfills active owner membership for existing personal workspaces and adds it atomically on future workspace provisioning. It also provides workspace listing and email-bound invitation acceptance routines. Membership role changes/removal are role-gated, accepted members can select a workspace, and a privacy-conscious workspace audit feed is available.
- Added backend SMTP email delivery for seven-day workspace invitations and one welcome message per authenticated login session, with delivery status and duplicate suppression. Migration 0014 stores workspace-scoped welcome email idempotency state. Live email sending is still gated on mail provider credentials and a public `KAIROS_PUBLIC_APP_URL`.
- A browser walkthrough exposed a null-element write when the persisted catalog is empty or unavailable in the 3D observatory. The renderer now skips the selected-asset detail write when the empty-state view has no detail panel.
- Reviewed migrations 0010 and 0011 were applied transactionally to the shared Supabase database. Direct live verification found all 43 tracked tables present; new sync/governance tables have forced RLS, one workspace policy each, and restricted `kairos_app` SELECT grants.
- The RLS verifier now switches into `kairos_app`; it passes all 42 scoped tables and confirms the role cannot bypass RLS. A rollback-only database test with two temporary workspaces confirms cross-workspace reads/inserts/updates are denied and the own-workspace read succeeds. No test rows were retained.
- Live, read-only API smoke checks returned HTTP 200 for catalog, sources, glossary terms/domains/products/classifications, quality assertions, notifications/preferences, freshness, and incidents while database access ran through `kairos_app`. The request identity was injected for this diagnostic, so this does not prove Supabase JWT verification.
- Existing demo entry points were not reintroduced. All UI data claims must continue to come from authenticated API results.

## Verified checks and limits

The following checks passed during this work:

- Python suite: **560 passed, 85 skipped** after the membership lifecycle changes.
- Frontend unit suite: **117 passed**.
- Frontend production build: passed.
- After the final demo-copy and fixture changes: frontend unit suite **117 passed**, production build passed, Playwright shell smoke **2 passed**; all four demo fixture parser checks passed (SQL 4 assets/2 edges; dbt 3 assets/2 edges; metadata graph 2 assets/1 edge; CSV 1 asset).
- The workspace administration screen was visually exercised in Chromium with mocked Supabase/API responses: members, pending invite, workspace audit, workspace selector, and create-invite link all rendered; **0 browser page errors**. The DB owner/invite/workspace-switch test ran against live Postgres in a transaction and rolled back.
- Playwright shell smoke: **2 passed**. These checks validate the shell, not end-to-end authentication against Supabase or the private GitHub App flow. The local API proxy was unavailable during this run, so the browser checks exercised the expected disconnected state.
- Visual walkthrough: **19 demo-related screens inspected**, with **0 uncaught page errors** after the observatory fix. This used a synthetic browser session and HTTP 503 responses for application APIs, so it checks rendering and unavailable states only. The SQL screen was correctly hidden because the disconnected catalog contained no persisted SQL assets. The screenshots and report are in the local Git-excluded `.demo-sources/visual/` folder.
- Supabase connection: PostgreSQL 17.6 was reachable using the local environment. No credential values are recorded here.
- Live migration verification: 0001–0011 table presence passed (43 tables); `sync_job` plus all 13 M4 tables were directly checked for enabled/forced RLS, a workspace policy, and `kairos_app` SELECT grants. Migration 0013 is applied; owner memberships and its three database routines are verified, and the existing 42-table RLS check passes. Real-user JWT invitation acceptance remains outstanding.

The SQL adapter has three focused tests and the new column lookup has authenticated/authorized route checks. Full `python -m ruff check` currently fails with 148 findings across existing files (import ordering, unused imports, and related lint issues); no repository-wide autofix was applied.

```powershell
python -m pytest -q
npm --prefix frontend test -- --reporter=dot
npm --prefix frontend run build
npm --prefix frontend run test:e2e -- --reporter=line
```

## Live demo gate

Before saying all ten demos work, complete these environment-backed gates:

1. Create two real Supabase users and run a cross-workspace negative test using ordinary application tokens.
2. **Source provisioning and adapter scans are complete** (five databases; repeated scans stable; writes denied). Restart the backend to load the new local encryption key, then use a signed-in Kairos session to prove connector test, preview, repeat-sync idempotency, and catalog readback.
3. Connect a private test GitHub repository, prove only authorized repository content is fetched, and preview/commit/read back a supported file.
4. Preview, commit, and read back fresh file, SQL, and dbt imports from the catalog/evidence APIs.
5. Configure `KAIROS_OPENLINEAGE_WEBHOOK_SECRET` and `KAIROS_OPENLINEAGE_WORKSPACE_ID` on the single-workspace demo backend, plus the secret on the producer; prove an event reaches run, evidence, and lineage readback. Multi-tenant hosting needs per-workspace webhook credentials.
6. Exercise freshness, quality, incident assignment/resolution, and governance mutations against the live workspace schema.
7. Run deployed browser tests with a non-secret test account and capture the deployed URL.

These gates require service/account configuration or a reviewed shared-database migration. Source edits alone cannot complete them. Never use a Supabase service-role key in the browser or commit credentials.
