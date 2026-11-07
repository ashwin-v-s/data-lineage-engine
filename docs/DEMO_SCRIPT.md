# Kairos — Ten-demo runbook

**For:** the 2026-11-08 presentation

**Scope:** run the real local application against the shared Supabase project. This runbook distinguishes verified behavior from steps requiring external credentials.

## Before presenting

1. Start the backend and React frontend using the repository setup instructions. Confirm `/healthz` returns HTTP 200 and open the frontend through its configured dev server (not by opening an HTML file directly).
2. Sign in with a confirmed Supabase account. Check that API calls carry that user's access token. Never present the auth screen as proof of authentication by itself.
3. Import small, prepared files into a disposable workspace and confirm they appear in catalog/API readback. Do not populate the shared workspace with fabricated customer data.
4. Keep the readiness report open. If a required external integration is not configured, present its implementation and clearly label the step as awaiting credentials rather than pretending it ran live.

## Ten demo flows

| # | Demo | Presentation flow | Verified limit / prerequisite |
|---|---|---|---|
| 1 | Sign-in and workspace isolation | Sign in, show the welcome email in the account inbox, switch workspaces, and show workspace-scoped catalog/member access. | Welcome delivery requires SMTP and a public app URL in backend environment. Live database migrations and `kairos_app` RLS isolation are verified. Still run the separate two-real-user Supabase token check before claiming end-to-end auth isolation. |
| 2 | PostgreSQL source | Add one of the five disposable read-only PostgreSQL databases listed in `.demo-sources/README.md`, test it, scan/sync, and show discovered assets. | Five logical databases with synthetic tables and a read-only connector role are provisioned in the existing Supabase PostgreSQL cluster. The adapter scan and write denial are verified. Restart the backend to load the local token-encryption key, then complete test → preview → sync → catalog readback with a confirmed Kairos user. They are not five separate Supabase projects. |
| 3 | Local folder | Choose `docs/demo-fixtures/` explicitly in the browser, inspect the inventory, preview `metadata_graph.json`, validate, commit, then show catalog readback. | Directory access is limited to the user-selected folder; inventory alone does not ingest file contents. The sample files contain synthetic metadata only. |
| 4 | Private GitHub | Connect the installed Kairos GitHub App, select an authorized repository/branch, browse and preview a file. | Requires GitHub App ID/private key/client credentials, encryption key, callback URL, installation, and test repo. Preview is not catalog ingestion. |
| 5 | SQL parsing | Preview `docs/demo-fixtures/demo_revenue.sql`; inspect the declared target and source candidates, validate, commit, then read the catalog/evidence. | Parser output is static evidence, not proof that the query executed. Unsupported/plain SELECT does not imply a target or lineage edge. |
| 6 | dbt manifest | Preview `docs/demo-fixtures/manifest.json`, inspect the model and two sources, commit, and read back assets/lineage. | The included manifest is synthetic and intentionally small; it demonstrates declared dependencies, not a dbt run or test execution. |
| 7 | OpenLineage | Send a runtime event with the configured bearer secret; show run/evidence/lineage readback. | Requires `KAIROS_OPENLINEAGE_WEBHOOK_SECRET` and `KAIROS_OPENLINEAGE_WORKSPACE_ID` on the backend and matching producer configuration. Binding is single-workspace. |
| 8 | Coverage-aware lineage | Open lineage for an imported asset, inspect upstream/downstream edges and evidence. | Do not claim full column coverage or time-travel semantics unless demonstrated by an acceptance case; graph visibility alone is not coverage proof. |
| 9 | Freshness, quality, incidents | Open freshness and quality views, create/inspect an assertion or incident, demonstrate assignment and resolution. | Requires live workspace data and write/readback validation. Scheduled evaluation and notification delivery are not verified; scheduler ownership remains a team decision. |
| 10 | Governance | Create a term/domain/product/classification/contract using real selected assets, then reopen it from the API-backed view. In Workspace administration, invite an email, confirm delivery, accept the seven-day link while signed in with the same email, then switch to the invited workspace. | Invitation/welcome email requires SMTP and a public app URL. Migration and reads are verified. Validate mutation and readback in the presentation workspace before calling the full flow live. |

## Evidence commands

Run from the repository root in PowerShell:

```powershell
python scripts/test_connection.py
python scripts/db/check_migrations.py
python scripts/db/verify_applied.py
python scripts/db/verify_rls.py
python scripts/db/verify_workspace_isolation.py
python -m pytest -q
npm --prefix frontend test -- --reporter=dot
npm --prefix frontend run build
```

These commands verify repository and database state. They do not substitute for the external integration prerequisites in the table. Do not print or commit `.env`, tokens, OAuth secrets, or private keys.
