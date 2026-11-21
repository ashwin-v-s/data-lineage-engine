# KAIROS — Feature Inventory (verified 2026-11-21)

Scope: the repository at `E:\EDI-Metadata_Lineage`, the deployed app
`https://data-lineage-engine-5i2x.vercel.app`, the shared Supabase Postgres
project (44 tables present, `scripts/db/verify_applied.py` PASS), and a real
signed-in session obtained through the Supabase password grant.

Status vocabulary used below:

| Status | Meaning |
| --- | --- |
| **Verified** | Executed against the deployed API or the shared database and the readback matched. |
| **Partial** | Works, but a documented gap limits what can be demonstrated. |
| **Blocked** | Requires an external credential, infrastructure or product work not present in this repository. |
| **Placeholder** | Visible in the UI but intentionally not backed by storage; it says so on screen. |

---

## 1. Application shell and navigation

| Feature | Location | Purpose | Backend dependency | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| Sign-in / sign-up / recovery / OAuth | `frontend/auth-stitch.html`, `frontend/auth.js` | Supabase Auth session for the browser | Supabase Auth, `/api/v1/auth/config` | **Verified** (password grant; browser session restored) | `/api/v1/auth/config` 200, `/healthz` 200 |
| Workspace switcher | `Sidebar > WorkspaceSwitcher` (`src/main.jsx`) | Switch between memberships | `GET /api/v1/me/workspaces` | **Verified** | Returns 1 workspace for the test account (`d91f7d80…`) |
| Personal workspace provisioning | `backend/app/auth.py` | First sign-in creates a workspace + owner membership | `kairos_workspace`, `workspace_member` | **Verified** in DB (11 workspaces, 12 memberships) | DB inspection |
| Data provenance badges | `src/components/DataModeLabel.jsx` | Never claim LIVE without a successful catalog response | `/api/v1/catalog` | **Verified** | Badge reached `LIVE`; CONNECTING spinner v308 deployed |
| Workspace health card | `Sidebar` bottom | Workspace mode, source, description | `/api/v1/catalog` | **Verified** | Screenshot `overview-ready.png` |
| Theme toggle, search overlay, help, mobile shell | `src/main.jsx`, `MobileShell.jsx`, `app.js` | UI chrome | none | **Verified** (rendered, 0 console errors) | Browser sweep |
| Global error surface | `app.js` `toast`, `#dataSourceBannerContainer` | Surface API failures without fixtures | every route | **Verified** | Banner and toasts observed |

## 2. Catalog

| Feature | Route / page | Purpose | Required data | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| Catalog snapshot | `GET /api/v1/catalog` → Overview, All assets | One payload for KPIs, tables, graph | `dataset`, `lineage_edge`, `evidence`, `execution_run` | **Verified** | 200, 30 assets / 23 edges / 23 evidence in the demo workspace |
| Asset list, search, filters, CSV export | `All assets` (`?view=assets`) | Browse persisted assets | catalog | **Verified** | 7,150 chars rendered, 0 errors |
| Asset detail + profile tabs | `Asset profile` (`?view=asset_detail`) | Columns, lineage, evidence, quality, runs, capabilities | `dataset`, `column_record`, capabilities | **Partial** | Duplicate assets split columns from lineage (see BUG-01) |
| Capability registry | `GET /api/v1/assets/{id}/capabilities` | Tells the UI which tabs are真实ly supported | dataset, columns, edges, quality | **Verified (API)** | Returns `supported/available/reason`; `schema.available=false` on duplicated nodes |
| Catalog structure | `?view=catalog` | Schema/owner grouping | catalog | **Verified** | 742 chars, no error |
| Keyword search | `GET /api/v1/search?q=` → `?view=search` | Persisted keyword search | catalog | **Verified** | `q=revenue` → 13 results |
| Hybrid/vector search | `GET /api/v1/search/hybrid` | pgvector + keyword | migration 0012, embeddings | **Partial** | Route exists; no embeddings were generated in the demo workspace |
| Raw event inspection | `GET /api/v1/raw-events` | Show stored import/runtime payloads | `raw_event` | **Verified (API)** | 11,230 global rows; event ids `kairos-import:<uuid>` |

## 3. Ingestion

| Feature | Route / page | Purpose | Status | Evidence |
| --- | --- | --- | --- | --- |
| Static import preview | `POST /api/v1/ingest/preview` | Validate + normalize without writes | **Verified** | metadata_graph: 9 assets/9 rel/41 cols; sql_file: 8/6; dbt: 8/8; csv: 1/10; inventory: 4/0 |
| Static import commit | `POST /api/v1/ingest/commit` | Atomic, idempotent persistence | **Verified** | 5 imports committed; ids recorded in the data catalog |
| Idempotent replay | same route + key | Same key + same content must not duplicate | **Verified** | `replayed: true`, same `import_id` |
| Import runs list/detail | `GET /api/v1/ingest/runs[/{id}]` | Audit trail | **Verified (API)** | 21 global rows, 5 new in the demo workspace |
| Metadata-graph envelope import | `POST /api/v1/ingestion/preview|commit` | Second, graph-specific contract | **Verified (routes + tests)** | 733 backend tests pass |
| Local folder / file picker | `/ingestion.html`, `frontend/ingestion.js` | Browser-selected files, SHA-256 inventory | **Partial** | File System Access API + manual browser action required |
| PostgreSQL source connector | `POST /api/v1/sources`, `/test`, `/discover`, `/preview`, `/sync` | Read-only JDBC-style discovery | **Blocked** | `source_connection` count = 0; needs a reachable PG source + `KAIROS_TOKEN_ENCRYPTION_KEY` |
| GitHub App import | `/api/v1/integrations/github/*` | Private repo browse + commit | **Blocked** | Requires App ID, private key, client credentials, installation |
| OpenLineage runtime ingest | `POST /api/v1/ingest/openlineage` | Runtime evidence, signed by shared secret | **Blocked** | Requires `KAIROS_OPENLINEAGE_WEBHOOK_SECRET` + `KAIROS_OPENLINEAGE_WORKSPACE_ID` |
| dbt manifest / run results | `ingest` kind `dbt_manifest` | Declared dbt dependencies | **Partial** | 8 assets/8 edges imported; warning `UNRECOGNISED_DBT_MANIFEST_*` on this fixture |

## 4. Lineage and evidence

| Feature | Route / page | Status | Evidence |
| --- | --- | --- | --- |
| Dataset-level graph | `GET /api/v1/assets/{id}/lineage` → `?view=lineage` | **Verified** | 8 nodes / 8 edges around `fct_daily_revenue` (MODEL) |
| Graph UI (SVG, zoom, modes, 3D view) | `?view=lineage`, `?view=observatory` | **Verified** | 4,066 / 3,632 chars rendered, 0 console errors |
| Edge evidence inspector | `GET /api/v1/lineage/edges/{id}/evidence` | **Verified** | Returns evidence rows for edge `5a9abd50-…` |
| Four-state reasoning (OBSERVED/POSSIBLE/REFUTED/UNKNOWN) | `evidence-semantics.js`, evidence view | **Verified** | 6,487 chars; states composed from stored evidence |
| Downstream impact | `GET /api/v1/assets/{id}/downstream-impact` | **Verified** | `customers` → `total_affected: 4` across depth levels |
| Column-level lineage | `GET /api/v1/column-lineage` | **Blocked** | `{"total":0}` — no adapter emits COLUMN-granularity evidence (BUG-03) |
| Bitemporal / as-of lineage | `?view=history`, `?as_of=`/`recorded_as_of=` | **Partial** | `evidence-at-time` returns `included: 0, undated_valid_time: 23` (BUG-04) |
| Time-travel comparison UI | `?view=history` | **Partial** | Renders, but compares an empty dated set |
| 3D observatory | `?view=observatory` | **Verified** | Loads with persisted graph, no null-node error |

## 5. Governance

| Feature | Route / page | Status | Evidence |
| --- | --- | --- | --- |
| Glossary terms + approval | `GET/POST /api/v1/governance/terms`, `/terms/{id}/approve` | **Verified** | Created `Gross Merchandise Value (GMV)` `fce04495-…`, APPROVED |
| Term ↔ asset assignment | `POST /governance/terms/{id}/assets` | **Verified** | `created: true` against `fct_daily_revenue` |
| Domains | `GET/POST /governance/domains` → `?view=domains` | **Verified** | Created `Finance & Revenue` `f480e033-…`; page shows LIVE + rows |
| Data products | `GET/POST /governance/products` → `?view=products` | **Verified (API)** | Created `Executive Revenue Intelligence` `f33bea44-…` with 2 assets |
| PII classification | `POST /governance/classifications` → `?view=pii` | **Partial** | Endpoint validated; blocked in this workspace because the imported columns sit on a duplicate asset id (BUG-01) |
| Contracts + assertion linking | `/governance/products/{id}/contracts`, `/contracts/{id}/assertions` | **Verified (API, 2 rows exist globally)** | Not yet created in the demo workspace |
| Column chooser for PII | `GET /governance/datasets/{id}/columns` | **Partial** | Returns 0 columns for the `TABLE` duplicate of `customers` |
| Stewardship requests | `/api/v1/stewardship/requests` → `?view=stewardship` | **Verified (empty state)** | 0 rows; page renders create/approve forms |
| Ownership | `/api/v1/owner/*` | **Verified (API)** | 1 `owner_assignment` globally; assign/search/approve routes tested |

## 6. Quality, freshness, incidents

| Feature | Route / page | Status | Evidence |
| --- | --- | --- | --- |
| Quality assertions | `POST /api/v1/quality/assertions` | **Verified** | `Revenue mart schema contract` `480a9715-…` |
| Metadata-only evaluation | `POST /quality/assertions/{id}/evaluate` | **Verified** | Result `54a0cd91-…` `PASS`, checked 1, failed 0 |
| Quality results readback | `GET /quality/assertions/{id}/results` | **Verified (API)** | 1 `quality_result` row |
| **Quality page / KPI** | `?view=quality`, Overview | **Fixed locally, awaiting deploy** | `catalog` now loads latest results per assertion (BUG-02); production still serves the old empty array |
| Freshness SLA | `POST /governance/slas` | **Verified** | `fct_daily_revenue` 48/60/120 min, `e0f15710-…` |
| Freshness evaluation | `GET /governance/freshness`, `/datasets/{id}/evaluate` | **Partial** | SLA stored; no runtime signal → evaluations `UNKNOWN`; scheduler `manual` |
| Incident lifecycle | `/governance/incidents` + ack/investigate/resolve/assign/comments | **Verified (empty state)** | 0 incidents; page reads live API |
| Manual freshness confirmation | `POST /governance/datasets/{id}/confirm-freshness` | **Verified (route + tests)** | Not exercised in the demo workspace |

## 7. Operations, notifications, administration

| Feature | Route / page | Status | Evidence |
| --- | --- | --- | --- |
| Pipeline runs | `catalog.runs` ← `execution_run` → `?view=runs` | **Partial** | 2 `execution_run` rows globally, 0 in demo workspace; runs page draws from catalog |
| Sync jobs | `sync_job` | **Blocked** | 0 rows; populated only by the PostgreSQL connector |
| Notifications | `/api/v1/notifications`, `/read`, `/read-all` | **Verified (API), no triggers** | 0 rows; no scheduler emits `FRESHNESS_BREACH` |
| Notification preferences | `/notifications/preferences` | **Verified (API)** | UI toggles render in Settings |
| Workspace members + roles | `/api/v1/members` | **Verified** | Admin page lists roles; owner cannot be removed |
| Invitations + email | `/members/invites`, SMTP | **Partial** | Route + DB verified; delivery requires SMTP + `KAIROS_PUBLIC_APP_URL` |
| Workspace audit feed | `GET /api/v1/audit/workspace` | **Verified (API)** | 24 `audit_event` rows globally |
| API keys | `/api/v1/api-keys` | **Verified (API)** | 1 row globally; self/rotate/revoke routes tested |
| Webhooks + deliveries | `/api/v1/webhooks` | **Verified (API, 0 rows)** | Create/test/deliveries implemented; SSRF allowlist missing (BUG-05) |
| Profile / preferences | `?view=settings`, `/api/v1/me/welcome-email` | **Verified** | Name from Supabase metadata; avatar/preferences browser-local |
| REA insight endpoints | `/api/v1/rea/*` | **Partial** | Static recommendation/pattern catalog, not workspace data |

## 8. Deliberate placeholders (honest, not bugs)

| Surface | Message | Why |
| --- | --- | --- |
| Data products health | "Product health is shown only when source evaluation rows exist." | No quality/incident evidence per product yet |
| Custom SQL assertions | Disabled with explanation | No isolated read-only runner |
| PII_INHERITED / PII_POTENTIAL | Disabled with reason | Requires lineage/SQL evidence propagation |
| Demo preview switch | Disabled | No fixture dataset is bundled |
| Notifications realtime | Copy says refresh reads persisted notifications | No websocket/realtime channel |

---

## Endpoint index (mounted under `/api/v1`)

`assets` (`GET/DELETE /assets/{id}`), `lineage` (`/assets/{id}/lineage`,
`/assets/{id}/downstream-impact`, `/lineage/edges/{id}/evidence`,
`/evidence-at-time`, `/column-lineage`), `capabilities`
(`/assets/{id}/capabilities`), `search` (`/search`, `/catalog`, `/raw-events`,
`/search/hybrid`), `ingest` (`/preview`, `/commit`, `/runs`,
`/runs/{id}`, `/openlineage`), `ingestion` (`/preview`, `/commit`),
`governance` (`/terms`, `/terms/{id}/assets`, `/terms/{id}/approve`,
`/classifications`, `/datasets/{id}/columns`, `/domains`, `/products`,
`/products/{id}/contracts`, `/contracts/{id}/assertions`, `/slas`,
`/freshness`, `/datasets/{id}/evaluate`, `/datasets/{id}/confirm-freshness`,
`/incidents` + lifecycle), `quality` (`/assertions`, `/evaluate`, `/results`),
`metadata` (`/{id}/description`, `/{id}/tags`, `/bulk-update`, `/{id}/editable`,
`/validate`), `owner` (`/team-members`, `/assign/{id}`, `/{id}/history`,
`/stats/overview`, `/request`, `/requests/pending`, `/requests/{id}/approve`),
`members`, `api-keys`, `webhooks`, `sources`, `stewardship`, `audit`
(`/workspace`, `/{id}/trail`, `/{id}/versions`, `/{id}/versions/diff`,
`/{id}/statistics`, `/{id}/compliance-report`, `/{id}/rollback`,
`/{id}/export-audit`), `notifications`, `personalization`
(`/me/recently-viewed`, `/me/starred-assets`, `/assets/{id}/star`),
`workspaces` (`/me/workspace`, `/me/workspaces`, `/me/welcome-email`,
`/workspaces/{id}`), `integrations` (GitHub App), `rea`, `health`, `dependency`.
