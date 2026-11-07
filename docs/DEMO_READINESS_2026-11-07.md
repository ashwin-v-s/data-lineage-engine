# Kairos: ten-demo readiness

This is a code and environment audit for the ten-demo brief supplied on 2026-11-07. A feature is called **working** only where the current implementation supports the full flow and the relevant tests/environment checks pass. A UI placeholder or parser unit test alone is not a complete demo.

## Status summary

| # | Demo | Current status | What is still needed for an honest live demo |
|---|---|---|---|
| 1 | Sign-in, workspace isolation, profile | **Partial** | Supabase Auth and personal workspace provisioning exist. This branch saves profile name/title/team/domain/manager/location to the signed-in Supabase Auth user's metadata; profile picture and display preferences remain browser-local. RLS declarations are present for 28 live tables under `kairos_app`; `sync_job` is missing. Owned-asset attribution is not queried by authenticated user. Run a real two-user cross-workspace test before claiming isolation. |
| 2 | PostgreSQL source discovery | **Partial** | Source connection UI/API and PostgreSQL adapter are present. A user-provided read-only source DB is needed to demonstrate test, scan, sync, and catalog readback. The current shared Kairos Supabase is the authority store; it is not itself evidence that an arbitrary customer source can be scanned. |
| 3 | Local folder/file ingestion | **Partial; implementation expanded in this branch** | Browser directory selection now displays a real local tree, previews locally, imports inventory, and can ingest a selected file. SQL files go through the SQLGlot adapter. Browser folder access is permission-scoped to the selected directory, not a background scan of the whole machine. Import persistence requires the live `import_run` migration and authenticated session. |
| 4 | GitHub repository browsing | **Partial** | OAuth/App connection and encrypted token storage are present. Confirm the authenticated server path lists the authorized repositories, branches, tree, and content before presenting private-repository browsing. Public GitHub API browsing is not proof of the user's granted private access. |
| 5 | SQL parsing and lineage candidates | **Partial; parser wired in this branch** | Selected `.sql` files now parse through SQLGlot. `CREATE TABLE … AS SELECT` and `INSERT … SELECT` create static table candidates and preserve SQL in raw import evidence. A plain `SELECT` does not invent a target or lineage edge. Column-level mapping and canonical asset reconciliation remain incomplete. Parsing is not runtime evidence. |
| 6 | dbt manifest | **Parser implemented; live path partial** | The pure manifest parser is registered with the authenticated import preview/commit API. Exercise a new manifest through preview, commit, catalog, lineage, and evidence on the live schema; confirm tests are represented as expected before claiming the full brief's test-definition acceptance. |
| 7 | OpenLineage runtime event | **Partial** | Authenticated event ingest stores raw events and normalizes run/evidence records. The route currently does not enforce an OpenLineage webhook signature/shared secret, so it is not ready for an internet-facing producer. Validate a new event and read back run/evidence/edge on a properly secured deployment. |
| 8 | Coverage-aware lineage | **Partial** | Lineage and evidence APIs/views exist and the observatory interaction defects fixed in this branch are covered by UI tests. Do not equate graph visibility with complete evidence-based coverage, column lineage, or time travel; those need explicit live acceptance cases. |
| 9 | Freshness, quality, incident lifecycle | **Partial** | On-demand freshness and incident APIs exist. Scheduler, notification delivery, and a complete assignment/quality-result lifecycle are not verified. `sync_job` is absent from the inspected shared schema. |
| 10 | Glossary, PII, domains, products | **UI/API implemented; live demo gated** | React governance screens and workspace-scoped APIs exist for terms, classifications, domains, products, and contracts. Forms now select real catalog assets/domains; PII column selection reads a new authenticated, workspace-scoped columns endpoint. The live 0011 governance migration is proposal-only/unapplied, so the shared project currently returns a controlled storage-unavailable response. |

## Work completed on this branch

- A selected local directory is enumerated only after an explicit browser picker action. The browser shows the path, type, size, modified time, and SHA-256 when within scan limits. It does not silently traverse the user's disk.
- A chosen file can be previewed locally before upload. Import has an explicit button, rejects unsupported types and oversized content, and reports backend failures without substituting fixture data.
- A folder inventory import records file metadata; it does not pretend that the file bytes or lineage were ingested.
- A selected SQL file now enters the same authenticated preview/commit pipeline as other static imports. SQLGlot creates candidate edges only when a target is declared by supported DDL/DML.
- The profile editor now saves identity fields to Supabase Auth user metadata and hydrates the account profile from that metadata. It does not write authorization roles or workspace access to user-editable metadata.
- Governance forms use catalog/domain selections instead of asking users to copy UUIDs. PII column choices are fetched from a new authenticated dataset-columns endpoint, with the existing workspace RLS applied.
- The observatory pointer/click and rendering defects from this working tree were corrected, and stale UI assertions were updated to match fail-closed behavior.
- Existing demo entry points were not reintroduced. All UI data claims must continue to come from authenticated API results.

## Verified checks and limits

The following checks passed during this work:

- Python suite: **547 passed, 85 skipped**.
- Frontend unit suite: **117 passed**.
- Frontend production build: passed.
- Playwright shell smoke: **2 passed**. These checks validate the shell, not end-to-end authentication against Supabase.
- Supabase connection: PostgreSQL 17.6 was reachable using the local environment. No credential values are recorded here.
- RLS declaration inspection as `kairos_app`: 28 declarations passed, zero failed, one missing (`sync_job`). This does **not** prove two-workspace data isolation.

The SQL adapter has three focused tests and the new column lookup has authenticated/authorized route checks. The current scoped Ruff run also reports pre-existing findings in untouched M1/M2 SQL/static-file adapter modules; see CI output rather than treating full lint as green.

```powershell
python -m pytest -q
npm --prefix frontend test -- --reporter=dot
npm --prefix frontend run build
npm --prefix frontend run test:e2e -- --reporter=line
```

## Live demo gate

Before saying all ten demos work, complete these environment-backed gates:

1. Apply and verify the reviewed pending migration(s), including `sync_job`; never apply proposal-only 0011 to the shared project without its migration owner approving it.
2. Create two real Supabase users and run a cross-workspace negative test using ordinary application tokens.
3. Use a disposable read-only PostgreSQL source to prove scan and repeat-sync behavior.
4. Connect a private test GitHub repository and prove only authorized repository content is fetched.
5. Preview, commit, and read back fresh file, SQL, and dbt imports from the catalog/evidence APIs.
6. Secure the OpenLineage ingress and prove an event reaches run, evidence, and lineage readback.
7. Exercise freshness, quality, incident assignment/resolution, and governance mutations against the live workspace schema.
8. Run deployed browser tests with a non-secret test account and capture the deployed URL.

These gates require service/account configuration or a reviewed shared-database migration. Source edits alone cannot complete them. Never use a Supabase service-role key in the browser or commit credentials.
