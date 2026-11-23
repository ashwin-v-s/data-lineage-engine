# KAIROS — Complete Demo Guide (click-by-click)

Everything below was executed on 2026-11-21 against
`https://data-lineage-engine-5i2x.vercel.app` with a real session. Where a step
is **NOT VERIFIED**, it says so; do not present unverified steps as working.

**Golden rules for the presenter**

1. Navigate by **clicking the sidebar**, never by editing the URL. A URL change
   reloads the whole dashboard and takes 12–19 s.
2. Wait for the provenance badge to read **LIVE** before speaking about data. A
   spinning **CONNECTING** badge means the catalog request is still running.
3. Never read a number without opening the record behind it.
4. Say "synthetic demonstration data" once, at the start, and point at the
   fixture file when asked where it came from.

---

## 0. Sign in

**A. What it is.** Supabase-hosted authentication with a personal workspace
provisioned on first login.

**B. Preparation.** A confirmed account. The repository's test identity is
documented in `scripts/get_test_token.py`; the workspace used for this
preparation is **Personal workspace** (`d91f7d80…`), which already contains the
enterprise demo data.

**C. Steps.**
1. Open the deployed URL.
2. Sign in with email and password (or Google/GitHub if configured).
3. Wait for the shell: the provenance badge must reach **LIVE**.

**D. Expected.** Dashboard with greeting, KPI tiles, catalog table; sidebar
bottom shows Data provenance = LIVE, Workspace mode = LIVE,
Data source = Connected.

**E. Script.** "Kairos authenticates against Supabase and provisions a personal
workspace on first login. The badge you see is not decorative: the shell only
says LIVE after the authenticated catalog request succeeds."

**F. Verification.** `GET /api/v1/me/workspaces` returns your membership; the
browser's Network tab shows `200 /api/v1/catalog`.

**G. Recovery.** If the badge stays CONNECTING past 30 s, reload once; if the
catalog request 401s, sign out and back in (the access token expired).

---

## 1. Overview / dashboard

**A.** Executive summary of the persisted workspace: asset count, edges,
evidence coverage, recognised runs, metadata attention.

**B/C.** Sidebar → **Home**. Wait for LIVE. Point at the KPI row, then the
"Assets discovered" table.

**D (verified).** With the demo workspace after identity reconciliation: 17
active assets, 23 dataset edges plus 19 column edges, 42 evidence rows and 4
persisted pipeline runs; the table lists `customers`, `orders_feed`,
`fct_daily_revenue`, dashboards, etc.

**E.** "Every number here is computed from the same `/api/v1/catalog` payload the
rest of the app uses. Nothing is hard-coded."

**F.** Compare the KPI with the catalog API response (`assets.length`,
`edges.length`).

**G.** If the table is empty, confirm the workspace selector is on the prepared
workspace (Workspace switcher at the top of the sidebar).

---

## 2. All assets (catalog list)

**A.** The inventory view: filters by type, domain, owner, platform, tags,
search, CSV export.

**B/C.** Sidebar → **Catalog → All assets**. Type `fct` in the search field;
open the row's name.

**D (verified).** 7,150 characters of table content, 30 rows; the filtered row
opens the asset profile.

**E.** "Filters are applied over persisted metadata; the export streams the same
rows."

**F.** Click **Export CSV** and confirm the row count matches the table.

**G.** If a filter returns nothing, clear every select (including Domain and
Trust) — filters combine.

---

## 3. Asset profile

**A.** One page per asset: description, owner, tags, columns, lineage,
evidence, capability-driven tabs.

**B/C.** All assets → click `customers`. Try the **Overview / Lineage /
Evidence** tabs. Open the column list if the asset has columns.

**D (verified).** The asset header renders; lineage tab shows the graph; columns
appear on the single logical asset. BUG-01 is fixed: tables, views, models and
sources of one dataset are reconciled into one row, so `customers` exposes its
six columns regardless of which adapter imported them.

**E.** "Kairos shows only what was imported. A missing column list is reported as
unavailable rather than guessed."

**F.** `GET /api/v1/assets/{id}/capabilities` → `schema.available` explains the
tab's state.

**G.** If the page is blank, go back to All assets and re-open; the detail view
depends on `selected` state.

---

## 4. Catalog structure

**A.** Schema/namespace grouping with owners.

**B/C.** Sidebar → **Catalog → Catalog structure**.

**D (verified).** 742 characters; groups for `raw_enterprise`, `staging`,
`analytics`, `executive`, `reporting`, `filesystem`.

**E.** "This is the same metadata, grouped the way a data engineer thinks about
it."

---

## 5. Import metadata (the ingestion demo)

**A.** The real ingestion pipeline: choose files, preview the parsed result,
commit atomically, verify readback.

**B.** Fixtures live in `demo-authenticated-ingestion/`. The demo workspace
already contains their committed output, so this is a *re-run* demo.

**C (UI path).** Sidebar → **Operations → Import metadata** (opens
`/ingestion.html`) → choose `enterprise_metadata_graph.json` → **Preview** →
inspect assets/relationships/columns → **Commit** → return to **All assets** and
open `fct_daily_revenue`.

**C (API path, fully verified this session).** `POST /api/v1/ingest/preview`
then `/commit` with `{kind, filename, content, idempotency_key}`.

**D (verified).**
- metadata graph: 9 assets, 9 relationships, 41 columns, status COMMITTED,
  `import_id cc782dcb-…`
- SQL: 8 assets, 6 edges, `2ac950e6-…`
- dbt: 8 assets, 8 edges, `b33f21f5-…` (one version warning)
- CSV: 1 asset, 10 columns, `e958f1a0-…`
- inventory: 4 file assets, `477e8d47-…`
- replaying the same idempotency key: `replayed: true`, same id.

**E.** "Ingestion is a two-phase protocol: preview validates and normalises with
no writes, commit revalidates and persists in one transaction. Re-sending the
same key replays instead of duplicating."

**F.** `GET /api/v1/ingest/runs` lists the import; `GET /api/v1/catalog` shows
the assets; the database has matching `dataset`/`lineage_edge` rows.

**G.** If commit returns 503, ingestion storage is missing (migration 0004). If
commit returns 409, the idempotency key was reused with different content —
change the key.

---

## 6. Lineage explorer

**A.** Evidence-aware dataset graph around one asset, expandable upstream and
downstream, 2D and 3D.

**B/C.** Sidebar → **Lineage**. Pick `fct_daily_revenue`. Expand depth 3–4.
Click an edge to inspect its evidence.

**D (verified).** Graph around the mart: 8 nodes / 8 edges; edge inspector
returns STATIC_DEPENDENCY evidence with the source file in
`diagnostics.provenance`. Downstream impact for `customers`: 4 affected assets.

**E.** "Every edge is a claim with evidence attached — file, adapter, parser
status. Static imports are DECLARED metadata, not runtime observation."

**F.** `GET /api/v1/assets/{id}/lineage` and
`/api/v1/lineage/edges/{edge}/evidence` reproduce the screen.

**G.** Empty graph → the workspace has no edges; confirm you are in the demo
workspace. Column-level lineage is available: the SQL projection backfill
produced 19 mappings for the demo workspace (BUG-03 fixed). Show them with
`GET /api/v1/column-lineage`.

---

## 7. Evidence & reasoning

**A.** The evidence ledger and four-state reasoning (OBSERVED / POSSIBLE /
REFUTED_FOR_RUN / UNKNOWN).

**B/C.** Sidebar → **Trust & governance → Evidence & reasoning**. Sort or filter
by state; open one row.

**D (verified).** 6,487 characters rendered; rows carry `evidence_type`,
`parser_status`, `diagnostics`, `ingestion_time`, `raw_event_id`
(`kairos-import:<uuid>`).

**E.** "Absence is not evidence. Kairos only stores positive observations and
declared dependencies; UNKNOWN is shown as unknown."

---

## 8. Time travel

**A.** Bitemporal queries: business-valid time vs system-recorded time.

**B/C.** Sidebar → **Lineage → Time travel**. Set both dates to today, run.

**D (verified, populated).** With both timestamps at today, the query returns
`included: 8, undated_valid_time: 34`. The eight rows are the dbt dependencies,
whose valid time is the manifest's own `metadata.generated_at`
(`2026-11-17T21:00:00Z`); they were recorded at the import time
(`2026-11-21T11:32:59Z`). The table shows three hops, e.g.
`analytics.fct_daily_revenue → exposure.daily_revenue_kpi`.

**E.** "The mechanism separates when something was true from when we learned it.
The dbt manifest declared its generation time, so those dependencies have a real
valid interval. SQL, CSV and file evidence carry no source time and are reported
as 34 undated records instead of being faked into a date."

**F.** `GET /api/v1/evidence-at-time?valid_as_of=…&recorded_as_of=…`.

**G (the time-travel moment).** Set both dates to today → eight rows. Change
valid time to **2026-11-16** → zero rows, because the manifest did not exist yet.
Change it to **2026-11-18** → eight rows again. Change recorded time to before
**2026-11-21T11:32Z** → zero rows, because Kairos had not learned it yet. Say:
"Same business date, different recorded date: this is bitemporal, not a filter."

---

## 8a. Pipeline runs (Operations)

**A.** Persisted job/run records from the catalog API, with outcome, duration,
environment and stored-event count.

**B/C.** Sidebar → **Operations → Pipeline runs**.

**D (verified live).** The demo workspace returns four runs:

| Run | Pipeline | Status | Duration | Environment | Events |
| --- | --- | --- | ---: | --- | ---: |
| `demo-run-legacy-export-20261123-0315` | Legacy warehouse export | FAILED | 65.0 s | production | 1 |
| `demo-run-revenue-quality-20261123-0300` | Revenue quality gate | WARNING | 135.0 s | staging | 1 |
| `demo-run-customer360-20261123-0230` | Customer 360 refresh | SUCCESS | 670.0 s | production | 1 |
| `demo-run-revenue-20261123-0200` | Revenue daily pipeline | SUCCESS | 522.0 s | production | 1 |

The cards read **2 successful, 1 warning, 1 failed, 4 runs shown**. Search by
`demo-run` or filter to `FAILED`; **Inspect** opens the stored run identity,
start, duration, environment and counts.

**E.** "These are persisted run records, not live orchestration. Assets stay
zero because this workspace has no normalized per-run evidence for these jobs;
the page reports that instead of inventing observed assets. The stored source
event is counted separately."

**F.** `GET /api/v1/catalog` → `runs[]` (`run_id`, `pipeline_name`, `status`,
`started_at`, `duration_ms`, `asset_count`, `event_count`, `environment_name`).

---

## 9. Data quality

**A.** Quality assertions over metadata (schema completeness, uniqueness,
validity, freshness), with stored results.

**B/C.** Sidebar → **Trust & governance → Data quality**.

**D (verified live).** An assertion exists
("Revenue mart schema contract", `480a9715-…`) and evaluating it stored a PASS
result (`54a0cd91-…`). The catalog payload now returns the latest result per
assertion, so the page shows Recorded 1 · Passed 1 (BUG-02 fixed and deployed).

**Present it honestly:** the page reads `quality_checks`; the same row is
reproducible with `GET /quality/assertions/{id}/results`.

**G.** Scored checks are not invented: metadata assertions store `score: null`
and the UI shows the count, not a fake average.

---

## 10. Freshness

**A.** Freshness SLAs, evaluation states and confirmations.

**B/C.** Sidebar → **Trust & governance → Freshness**.

**D (verified).** SLA for `fct_daily_revenue`: warn 48, error 60, stale 120
minutes, signal `manual`, schedule `manual`. Status is UNKNOWN because no
runtime activity signal exists.

**E.** "An SLA without a signal is honestly UNKNOWN. Kairos does not invent
freshness."

**F.** `GET /api/v1/governance/freshness`.

**G.** Body `{...}` errors mention migration 0011 → storage missing.

---

## 11. Incidents

**A.** Incident lifecycle: open → acknowledge → investigate → resolve, with
comments, owner assignment and a dedupe key.

**B/C.** Sidebar → **Trust & governance → Incident console**.

**D (verified empty).** 0 incidents, because no freshness breach ever fired.

**E.** "Incidents are opened by the freshness engine when a stored evaluation
breaches the SLA — not by the UI."

**G.** To create one legitimately you need a runtime signal
(OpenLineage/dbt/manual confirmation) plus an evaluation.

---

## 12. Glossary

**A.** Business terms with definitions, approval state and asset links.

**B/C.** Sidebar → **Trust & governance → Glossary**.

**D (verified).** `Gross Merchandise Value (GMV)` is APPROVED (`fce04495…`) and
linked to `fct_daily_revenue`. Other terms exist.

**E.** "A term is only approved after a steward review, and the link to the
dataset is what makes the definition enforceable."

**F.** `GET /api/v1/governance/terms` → `status: APPROVED`.

**G.** If the page shows NOT CONNECTED, click **Refresh** and wait — the panel
loads its catalog and terms sequentially.

---

## 13. Domains

**A.** Organisational boundaries for assets and products.

**B/C.** Sidebar → **Trust & governance → Domains**.

**D (verified).** Badge LIVE after load; rows include
`Finance & Revenue` (`f480e033…`) with description and status.

**E.** "Domains are the ownership contract above individual tables."

---

## 14. Data products

**A.** Consumer-facing products bundling assets, contracts and assertions.

**B/C.** Sidebar → **Trust & governance → Data products**.

**D (verified).** `Executive Revenue Intelligence` (ACTIVE) bundles
`daily_revenue_kpi` and `fct_daily_revenue`; contract and assertion-link forms
are present.

**E.** "A data product is the unit a consumer subscribes to; contracts and
quality assertions hang off it."

---

## 15. PII classification

**A.** Evidence-backed sensitivity classes per column/dataset.

**B/C.** Sidebar → **Trust & governance → PII classification**. Choose a
dataset, then a column.

**D (verified).** The form loads; column lists come from
`/governance/datasets/{id}/columns`. The BUG-01 merge means `customers` is one
asset with six columns, so classification posts with provenance (origin + note)
and readback against the column's owning asset.

**E.** "Classification requires provenance: who classified it and on what
evidence. Inherited/Potential classes stay disabled until the evidence pipeline
can support them."

**G.** If the column list is empty, try the variant of the same dataset that
shows columns; otherwise demonstrate the API contract and state the gap.

---

## 16. Stewardship

**A.** Access requests and glossary proposals routed to owners.

**B/C.** Sidebar → **Trust & governance → Stewardship**.

**D (verified empty).** Forms render; 0 requests in this workspace.

**E.** "Requests are stored with an approver, not handled by email."

---

## 17. Sources & connections

**A.** Register a read-only PostgreSQL source, test it, discover schema, preview,
sync.

**B.** Requires a reachable PostgreSQL database, a read-only role, and
`KAIROS_TOKEN_ENCRYPTION_KEY` on the backend.

**D.** 0 `source_connection` rows; the connector is implemented and tested
offline but not configured in this deployment. **Blocked** for the live demo.

**E.** "Credentials are encrypted at rest and never displayed; the connector is
read-only by design."

---

## 18. Integrations & API

**A.** GitHub App connector status, public repository browsing, private-file
preview. Workspace API keys and webhooks live on **Workspace administration**
(§19), not on this page.

**B/C.** Sidebar → **System → Integrations & API**.

**D (verified).** Page renders; GitHub connector reports "not configured"
without an App installation. API keys and webhooks are demonstrated under
**System → Workspace administration**.

**E.** "Private repository import is a server-side OAuth app, not a browser
token; keys are scoped per workspace."

---

## 19. Workspace administration

**A.** Members, roles, invitations, workspace audit, API keys and webhooks.

**B/C.** Sidebar → **System → Workspace administration**.

**D (verified).** Member list with roles; invite form (viewer/editor/admin);
owner cannot be demoted or removed. 24 audit events globally.

**E.** "Roles are enforced server-side with a minimum-rank check; invitations
are bound to the invitee's email."

**G.** Invitation email requires SMTP; without it the link can still be copied
from the API response.

### API keys (verified live)

The demo workspace has one active key, **`ci-readonly-catalog`**, prefix
`kairos_sk_2bI-S26ksl`, scope **read only**, created 2026-11-23 and last used
when the catalog was read. Its secret is stored locally at
`.demo-sources/ci-readonly-catalog.key` (git-ignored) and is deliberately not
printed in any document.

1. Point at the row: name, masked prefix, `read only` scope, last-used time.
2. Create a second key, e.g. `demo-ci-key`; the secret is revealed once with a
   **Copy secret** button. Reload the page: the secret is gone, only the prefix
   remains.
3. Read the catalog with the key:

```bash
BASE=https://data-lineage-engine-5i2x.vercel.app
KEY=$(cat .demo-sources/ci-readonly-catalog.key)
curl -s "$BASE/api/v1/catalog?limit=100" \
  -H "Authorization: Bearer $KEY" | jq '.counts'
# {"assets":17,"edges":42,"evidence":42,"runs":4,...}
```

4. Prove read-only scope: the same key gets `403` from
   `POST /api/v1/ingest/preview` and `GET /api/v1/members`.
5. Revoke the key; the next catalog request returns `401`. Recreating the same
   name rotates the revoked row, so the old secret stays dead and the name can
   be reused (fixed 2026-11-23).

**E.** "A key is a workspace-scoped read credential, not a user session. It can
read the catalog, assets, lineage and search, and cannot mutate anything. The
server stores only its SHA-256 hash."

### Webhooks (verified live)

The demo has one active endpoint, `https://httpbin.org/post`, labelled **Demo
echo receiver - replace with your HTTPS endpoint**, subscribed to all seven
events. **Send test** delivered a real signed `test.ping`: HTTP **200**, 26 ms,
recorded in History with the `X-Kairos-Signature` header echoed back. Its
signing secret is at `.demo-sources/webhook-signing-secret.txt` (git-ignored).

1. Point at the endpoint row: seven event pills, **DELIVERED · HTTP 200**.
2. Click **History** to show the `test.ping` attempt, HTTP 200, duration and the
   receiver's echoed headers.
3. Click **Send test** again; the delivery history adds a new signed attempt.
4. For a real receiver, register your own HTTPS URL, select events, and copy the
   one-time `whsec_…` signing secret. `httpbin.org` is only a public echo used
   to prove the delivery path; it does not verify signatures.

Receiver verification: compute `sha256=<hex>` over the **raw request body** with
HMAC-SHA256 using the endpoint secret and compare it to
`X-Kairos-Signature`. Also read `X-Kairos-Event` and `X-Kairos-Webhook-Id`.

```python
import hashlib, hmac
expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
assert hmac.compare_digest(expected, request.headers["X-Kairos-Signature"])
```

Payload shape:

```json
{"event":"test.ping","workspace_id":"d91f7d80-…","webhook_id":"d75d546d-…","sent_at":"2026-11-23T22:07:20Z","data":{"message":"Kairos webhook delivery test"}}
```

**E.** "The test button uses the same signed POST and audited delivery row as a
real event; failures are recorded, not swallowed. The endpoint is subscribed to
all seven event names; `test.ping` is the event the demo sends."

**G.** Only HTTPS public hosts are accepted; loopback, private, link-local and
DNS-rebound destinations are refused. A failed delivery remains visible in
History with its error.

---

## 20. Settings & preferences

**A.** Profile (name/avatar), local display preferences, notification
preferences.

**B/C.** Sidebar → **System → Settings & preferences**.

**D (verified).** Profile reads Supabase metadata; avatar and some preferences
are browser-local (stated on screen); notification preferences hit
`/notifications/preferences`.

**E.** "Identity lives in Supabase; purely local preferences never leave this
browser."

---

## 21. Catalog search

**A.** Keyword search across name, schema, owner, type, description, metadata.

**B/C.** Sidebar → **Catalog → Catalog search** (or Ctrl/⌘+K), search
`revenue`.

**D (verified).** `GET /api/v1/search?q=revenue` → 13 results.

**E.** "Search is workspace-scoped by RLS; it never crosses tenants."

---

## 22. 3D observatory

**A.** Optional spatial view of the same graph.

**B/C.** Sidebar → **Lineage → 3D observatory**.

**D (verified).** Renders 3,632 characters of controls with the persisted graph,
0 console errors. It is a visualisation, not a separate data source.

**G.** If WebGL is unavailable the page degrades; use the 2D lineage view.

---

## 23. Notifications

**A.** In-app notifications per event type, with read/unread state and
preferences.

**B/C.** Sidebar → **Trust & governance → Notifications**.

**D (verified empty).** 0 rows — no scheduler produced a `FRESHNESS_BREACH`,
`QUALITY_FAILURE` or `INCIDENT_CREATED` event.

**E.** "Notification records are written by the event that caused them; with no
scheduler running there is nothing to show, and we do not fake one."

---

## Cross-cutting failure recovery

| Symptom | Cause | Action |
| --- | --- | --- |
| Badge stuck CONNECTING | catalog request slow/failed | wait 30 s, then reload once; check Network for `/api/v1/catalog` |
| 401 on any API | expired session | sign out, sign in |
| Empty everywhere | wrong workspace selected | workspace switcher → prepared workspace |
| Governance panel NOT CONNECTED | catalogue request still in flight | click Refresh, wait 5 s |
| Quality page says "not available" | BUG-02 was fixed and deployed | hard reload once; if it persists, show the API + DB proof |
| Lineage has duplicate nodes | old rows from before migration 0018 | apply `0018_dataset_identity_reconciliation.sql`; new imports reconcile by schema + name |
