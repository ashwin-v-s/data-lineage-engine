# Kairos Product Spec — Perplexity Build Checklist

**Purpose:** the per-screen, per-component, per-state build list taken from [Perplexity/perplexity.txt](Perplexity/perplexity.txt) (2,950 lines, read in full 2026-11-02). [KAIROS_ARCHITECTURE_V2.md](KAIROS_ARCHITECTURE_V2.md) says *what we are building and why*; this file says *exactly what has to be on the screen and in the response* so nothing gets lost in translation again.
**How to use:** each row is one testable unit. Tick it only with a screenshot, an API response, or a test. A component that exists but renders fixture data is **not** ticked — it is ticked in the "honesty" column as `DEMO FIXTURE`.
**Owner key:** M1 Jatin · M2 Anushka · M3 Ashwin · M4 Gauree · M5 Pranav.

---

## 1. Global shell (M4, with M1 for auth/roles)

| Component | Required content | Owner | Priority |
|---|---|---|---|
| Left sidebar | Home · Catalog · Lineage · Sources · Quality · Incidents · Glossary · Domains · Data Products · Settings (note: **Freshness and Evidence are not sidebar entries** in the spec — freshness lives in the monitoring view + asset panel, evidence in the inspector/explorer) | M4 | P0 |
| Top bar | global search, workspace selector, notification bell, avatar, help | M4 (search: M3) | P0 |
| Right inspector | contextual panel for the selected asset / node / incident / evidence / run | M3+M4 | P0 |
| Bottom status bar | sync status, connection health, last-refreshed time, **environment label** | M4 | P1 |
| Data-mode label | every view shows `LIVE / IMPORTED / DEMO FIXTURE` | M5 | P0 |

## 2. Home dashboard (M4) — "What needs my attention?"

Sections, each metric a **clickable filtered link** (the spec forbids a number-heavy dashboard with dead numbers):

1. Hero header — product name, workspace name, date, quick actions.
2. Health summary — total / healthy / at-risk / **late** / **unknown-freshness** asset counts.
3. Incidents — open, critical, assigned-to-me, resolved today.
4. Source health — connected, failed, **credentials expiring**, last sync time.
5. Freshness overview — fresh / at risk / late / stale / unknown.
6. Lineage overview — assets, edges, **observed / possible / unknown** edge counts.
7. Recent activity — new assets, metadata changes, **PII changes**, lineage updates, quality failures.
8. Recent runs — OpenLineage, dbt, PostgreSQL sync, GitHub sync.
9. My ownership — assets I own, incidents assigned to me, assets awaiting review.
10. Quick actions — add source, import artifact, search catalog, create glossary term, view incidents.

## 3. Catalog (M3)

| Component | Detail |
|---|---|
| Search bar | name, description, schema, table, column, owner, domain, tag |
| Filter sidebar | asset type, source, database, schema, domain, owner, tags, PII, freshness, quality, **certification** |
| Sort | name, updated time, freshness, incident count, popularity |
| Result row (11 fields) | name · type (table/view/file/model/dashboard/ML model) · source · `db.schema.table` · owner · domain · freshness state · quality state · PII badge · last updated · incident count |
| Preview drawer | quick detail without leaving the list |
| Bulk filters | only-PII, only-stale, with-incidents, uncertified |
| Empty states | "No assets found" / **"Connect a source to discover assets"** / "No results match filters" — three different messages |
| Pagination | required before the catalog grows past one page |
| Saved views | My assets, Critical, Stale, PII |

## 4. Asset detail (M3, tabs gated by the capability registry)

Eleven tabs: **Overview · Schema · Freshness · Quality · Lineage · Evidence · Incidents · Activity · Runs · Relationships · Actions**.

- Overview: name, URN, description, type, source, owner, domain, tags, certification, created/updated.
- Schema: columns, types, nullability, PK/FK, constraints, descriptions, PII tags.
- Freshness panel must print exactly: status, SLA, last successful update, next expected update, **signal type**, last checked, trend (7d), evidence (`run_882, source: OpenLineage`).
- Quality: results, pass/fail trend, failed tests, score, latest run.
- Lineage: upstream/downstream, column-level, evidence state, impact.
- Evidence: raw records, source event, parser output, valid time, transaction time.
- Activity: metadata edits, ownership changes, tag changes, lineage changes, comments (**M1's `asset_version` table is the backing store**).
- Runs: OpenLineage, dbt, ingestion, source sync.
- Relationships: glossary terms, data products, dashboards, ML models, contracts.
- Actions: edit description, assign owner, add tag, mark PII, create incident, refresh metadata, view lineage (each needs a permission check, §12).

## 5. Lineage (M3)

Fifteen components: graph · direction toggle (up/down/both) · **depth control (1/2/3/5/custom)** · column-level toggle · **evidence-state legend** · edge inspector · node inspector · impact analysis · root-cause view · time-travel control · filters · **search-within-graph** · **mini-map** · export **PNG/SVG/JSON** · 2D/3D toggle.

Edge click must show all eight: relationship type (table-to-table / column-to-column), state, evidence source (OpenLineage / dbt manifest / SQL parser / user declaration), evidence ID, **evidence strength**, coverage, valid time, transaction time, plus the explanation sentence.

## 6. Sources (M2 API + M4 UI)

Twelve components: source cards (name/type/status/last sync/asset count) · Add source (wizard) · connection status · **sync history per run** (started, finished, status, discovered, updated, deleted, errors) · **sync schedule** (manual / hourly / every 6h / daily / custom) · Sync now · credential health (masked, expiry warning, rotate) · **scope selector** (databases, schemas, repositories, folders, branches) · error panel (auth / permission / timeout / parser) · delete or disable.

**Connection screen fields** (spec §10 mockup): source-type buttons `[PostgreSQL][GitHub][dbt artifact][OpenLineage][JSON file]`; PostgreSQL host/port/database/username/password + `SSL: Require|Prefer|Disable`; access-scope checkboxes `Discover schemas` `Discover tables and columns` `Read table comments` `Enable data preview` `Read query logs`; workspace selector; **data-visibility selector `Only me | Workspace members | Specific roles`**; `[Test connection] [Cancel]`.

> ⚠️ The visibility selector is a real requirement, not decoration: it decides whether an asset row is readable by the whole workspace or only its importer. That is an **RLS design question for M1** (a `visibility` column + policy), and it is currently undecided — see §15 D7.

**Post-connection status block** (8 lines): Connection · Status · Credential · Scope · Last successful sync · Assets discovered · **Data preview: Disabled** · **Query-log lineage: Not authorized**.

**Failure states — all seven must render distinctly** (spec §10):

| Failure | UI status | User action offered |
|---|---|---|
| Wrong password | Authentication failed | Re-enter credential |
| Network unreachable | Source unreachable | Check host/network |
| Insufficient schema permission | **Connected but partial authorization** | Grant metadata read **or reduce selected scope** |
| Expired GitHub token | Credentials expired | Reconnect GitHub |
| Revoked GitHub App | Connection revoked | Reinstall / reauthorize |
| Empty schema | Connected — no discoverable assets | Honest empty state |
| Partial discovery failure | Partially discovered | Show succeeded / failed resource counts |

**Connector diagnostics** (spec §3.1, 12 fields — this is the `GET /sources/{id}/health` payload): connection status · credential status · last successful **discovery** · last successful **sync** · assets discovered · assets created/updated/unchanged · relationships discovered · errors and warnings · **next scheduled sync** · sync duration · **permission gaps** · source version / commit / artifact version.

## 7. Freshness (M4)

Eleven components: dashboard counts · freshness table (asset, SLA, last update, age, status, owner, source) · filters · trend chart · SLA configuration · evaluation schedule (15 min / hourly / daily / CRON) · freshness evidence · incident trigger · notification settings (owner, steward, Slack/email/webhook) · **manual refresh** (records `MANUAL` provenance) · **unknown-state explanation**.

States and thresholds (`HEALTHY ≤80%` · `AT_RISK >80%` · `LATE >SLA` · `STALE ≫SLA` · `UNKNOWN no evidence` · `PAUSED` explicit) are in v2 §5.6; the correctness rule is v2 §3 C3 — **never `LATE` because an event simply did not arrive**.

Check-frequency defaults from the spec (start here, do not invent):

| Asset class | Freshness check | Source sync |
|---|---|---|
| Critical / certified / production | every 5–15 min | 1–6 h |
| Standard production | 30–60 min | 6–24 h |
| Internal / non-critical | 6–24 h | daily |
| Experimental / demo | manual or daily | manual |
| Real-time pipeline source | event-driven (OpenLineage) | event-driven |

## 8. Quality (M4)

Nine components: dashboard (pass rate, failing, critical, trend) · test list (name, asset, type, status, last run, owner) · test detail (definition, threshold, latest result, history, evidence) · **test creation form** (asset, type, threshold, schedule, severity) · test types (freshness, completeness, uniqueness, validity, schema, custom SQL) · **failure investigation** (failed rows, sample values, affected downstream assets) · trend chart · schedule · **test-to-contract link**.

> "Sample values" implies row access. Under the metadata-vs-data rule (§11) it is **opt-in** (`data:preview`) and off by default; with no preview grant the failure view shows counts and the assertion SQL, never values.

## 9. Incidents (M4)

Ten components: list (ID, title, severity, status, asset, owner, opened, age) · filters (open / acknowledged / investigating / resolved / assigned-to-me / severity) · detail (description, affected assets, root cause, evidence, timeline, comments) · timeline · **impact panel from downstream lineage** (needs M3) · **evidence panel** (OpenLineage event, failed test, freshness breach, sync error) · assignment (owner + steward) · resolution form (reason, action, by, time) · notifications · **related incidents**.

Routing pipeline the spec requires (not just "create an incident"): classify severity → **find the owner through lineage** → create/deduplicate → notify owner → **escalate if unresolved** → resolve with evidence. Targets: asset owner, downstream owners, steward (PII/policy), connection owner (credential/sync), data-product owner (contract violation), AI-agent owner (retrieval failure).

## 10. Evidence explorer (M3) — the differentiator

Eleven components: evidence list (ID, source, type, ingested time, valid time, strength) · filters (source, type, asset, run, time range) · **raw viewer** (original event/artifact, read-only, sanitized) · **normalized viewer** (entities, relationships, columns, runs, facets) · evidence→asset link · evidence→lineage link · **strength indicator: High / Medium / Low** · coverage indicator: Complete / Partial / Unknown · **conflict view** (two records disagree) · temporal view · **provenance chain raw → parser → normalized → canonical**.

**Evidence inspector layout the spec draws** (M3 renders this verbatim):

```text
Evidence ID · Evidence State · Evidence Kind · Source · Producer · Run ID · Event Time · Recorded Time
Subject / Related Subject
Explanation: "OpenLineage lineage facet recorded this field-level dependency during run run_4821."
Coverage: Run scope: full · Field coverage: complete
Raw Event: View sanitized payload
```

The UI must always be able to answer the spec's five questions: **What do we know? How do we know it? When did we learn it? For which run or time period? What remains unknown?**

## 11. Access model (M1 + M2) — what the user actually grants

**The separation, in one line:** *a source credential authorizes Kairos' backend to read a narrow source; Kairos membership + RLS authorize a user to see the metadata that import produced.* "Kairos may read my repository" ≠ "every Kairos user may see my repository metadata."

Six concepts, each enforced somewhere specific:

| Concept | Question | Where enforced |
|---|---|---|
| Authentication | who is calling? | Supabase JWT, verified server-side |
| Source authorization | what may Kairos read? | read-only role / App installation + scope checkboxes |
| Platform authorization | what may this user see? | `workspace_member` role + permission claims derived server-side |
| Tenant isolation | whose records? | RLS on every business table |
| Source scope | which repos/schemas? | scope stored on the connection, applied at discovery |
| Evidence visibility | who may view raw events / PII / previews? | separate permission, steward/admin only |

**Supabase roles:** `anon` → public data only; `authenticated` → RLS applies; `service_role` → bypasses RLS, **never leaves the server**. Do not use `user_metadata` claims for authorization.

**Permission model (MVP roles):** Viewer, Steward, Editor, Connection owner, Admin × the eight capabilities (`catalog:read, lineage:read, metadata:write, pii:classify, data:preview, incident:manage, connection:admin`, plus `governance:read`, `governance:policy:apply`, `data:pii:unmasked`).

**Metadata access ≠ data access** (Atlan's posture, and our default): catalog discovery ≠ query execution ≠ query-log capture ≠ complete runtime lineage. Request metadata read; make `Enable data preview` and `Read query logs` explicit opt-ins, off by default.

**PostgreSQL:** dedicated `kairos_reader` (CONNECT + USAGE on schema + SELECT on the metadata views needed); never a user's admin credential; capability→permission table in v2 §9.4.

**GitHub:** App installation for the product path (Metadata read, Contents read, Webhooks only if incremental sync, **never** Administration/Actions/Secrets, never write "just to catalog"), fine-grained PAT restricted to "Only select repositories" + Contents read-only as the demo fallback; **classic PATs are rejected** because they expose every repo the owner can see.

**Revocation + retention** (v2 §9.8): next health check fails → `REVOKED`/`CREDENTIALS_EXPIRED` → sync stops → **imported evidence remains as history** → the user may delete it or keep it per retention policy. Never silently wipe, never keep syncing.

**PII: classification propagates, access does not.** Ladder: `PII_SOURCE → PII_INHERITED (via column lineage) → PII_MASKED (mask/hash detected) → PII_POTENTIAL (static inference) → PII_CLEARED (aggregation, no identifiers — requires review)`, with `UNKNOWN` when the lineage is missing. Evidence per rung: manual steward tag = `OBSERVED` manual; direct copy through lineage = `OBSERVED` inherited; SQLGlot guess = `POSSIBLE` inherited. Every downstream asset shows *why* it is tagged, and seeing the tag is `metadata:read` while seeing the value is `data:pii:unmasked`.

## 12. Settings, notifications, admin (M1 + M4)

Settings sections: profile · workspace (members, roles) · notifications (email, in-app, Slack, webhook) · freshness defaults · sync defaults **and retry policy** · **API keys (create/revoke)** · **webhook endpoints** (OpenLineage, GitHub, dbt artifact) · security (RBAC, audit log, credential policy) · integrations · audit log.

Notifications UI: bell with unread count · dropdown · full centre · types (freshness breach, quality failure, new incident, sync failure, credential expiry, lineage change, PII change) · mark read (single/bulk) · filters · action link into the affected asset/incident/source.

Admin surface (spec §3.7, minimal but real): user/workspace management · connection inventory · ingestion-run history · **failed-record quarantine** · **fixture registry** (the mechanism that keeps demo data separate from live data — M5 owns the registry, M1 the screen) · classification approval queue · contract approval queue · audit log · **data-retention controls** · API-token management.

## 13. Realtime behaviour (M4, after M1)

Eight event → reaction rows: asset imported (catalog count + row after authorized refetch) · freshness changed (badge) · incident created (count + notification) · lineage edge changed (refetch the affected subgraph) · quality failed (badge + incident) · PII tag changed (badge + governance panel) · sync completed (source status + counts) · another user edited a description (asset detail refetches).

Rule: Realtime carries an **invalidation signal**, the client then refetches through the authorized API. Never trust the payload for state or authorization, and never broadcast to users without membership (v2 §3 C6).

## 14. What the spec assumes we already have — and we do not

The Perplexity analysis was written against an older snapshot. Correct these in every status/report file so nobody chases a feature that does not exist:

| Spec claim | Repo reality (measured 2026-11-02) |
|---|---|
| "quality tables exist" | No `quality_assertion` / `quality_result` table anywhere in `backend/migrations/`; the only occurrence of those names is as **capability keys** in [capabilities.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/capabilities.py) |
| "RAG: embedding/trace schema exists" | No `pgvector`, no embedding column, no trace table in migrations; search is keyword `LIKE` |
| "JSON lineage export exists" | No lineage export route; `frontend/app.js` renders, it does not export |
| "Confirm the deployed Hatchable app uses the intended Supabase project" | There is **no deployment at all** — no base URL, `live-smoke` never run |
| "3D Observatory existing BETA module" | `frontend/observatory.js` exists — true, preserve it |
| "File / folder upload, image, document assets" | Only metadata-graph JSON, dbt, file **inventory** and CSV-header adapters; no document/image metadata extraction, and no Supabase Storage usage |
| "Profiler" | Not implemented — quality/profiling is why `preview`/`profile` capabilities must report `supported: false` |

## 15. Decisions this checklist exposed (now recorded in v2 §11 as D7–D12)

D7–D10 below were promoted into [KAIROS_ARCHITECTURE_V2.md](KAIROS_ARCHITECTURE_V2.md) §11, which also adds **D11** (every source in §9.2 is in demo scope, incl. MLflow and RAG-trace lineage) and **D12** (where we get a database we can actually test against). Kept here for the screen-level context that motivated each.

| # | Question | Owner | Needed by |
|---|---|---|---|
| D7 | Does the **data-visibility selector** (`Only me` / `Workspace members` / `Specific roles`) get implemented, or do we ship workspace-wide visibility and say so? It changes the RLS policy shape, so it cannot be decided after Wave 1 | M1 | Wave 1 |
| D8 | Do we ship **`Read query logs`** as a real capability, or hide the checkbox? A checkbox that grants nothing is a dishonest UI | M2 | Wave 2 |
| D9 | Failed-record quarantine + fixture registry: new tables, or file-based registry? | M1 (quarantine) + M5 (registry) | Wave 3 |
| D10 | Export formats: PNG/SVG/JSON for lineage — client-side or server-side? | M3 | Wave 3 |

## 16. Poster / report wording the spec dictates (M5 keeps these in sync with reality)

- **Architecture:** "Kairos uses PostgreSQL as its authoritative metadata, lineage, evidence, and governance store, deployed on Supabase. Supabase provides authentication, row-level security, file storage, realtime updates, Edge Functions, and vector-search infrastructure around PostgreSQL. The platform does not replace PostgreSQL with Supabase; it uses Supabase to operate and secure its PostgreSQL database."
- **Multi-user:** "Metadata ingested by one authorized user is persisted centrally and becomes visible to other authorized users according to workspace membership and Row Level Security. Supabase Realtime may optionally notify open clients of changes, but authorization is always enforced server-side." **Never** say "Supabase automatically shares all data with all users."
- **Freshness:** "Kairos runs scheduled freshness evaluations against each asset's defined SLA… If an asset exceeds its SLA, Kairos changes its freshness state, creates or updates an incident, notifies the owner, and records the result as evidence." Claim **"scheduled freshness monitoring with event-driven updates where available"**, not "real-time monitoring", unless an OpenLineage producer is actually connected and tested.
- **Positioning:** "Kairos is an evidence-first metadata and lineage workspace that shows not only what depends on what, but what was observed, what was inferred, what was refuted for a specific run, what remains unknown, and which evidence proves each conclusion."
- **Honesty frame (seven claims to make about the product's own honesty):** connection lifecycle tells the truth about what Kairos can access; the capability registry about what an asset supports; the evidence inspector about why a conclusion exists; quality about which assertion produced a result; incidents about who owns and resolved a failure; search about whether it is keyword, semantic or grounded RAG; demo mode about the fact that its data is synthetic.

## 17. Priority order the spec sets (do not reorder silently)

**P0:** shell + global search · Home · Catalog · Asset detail · Lineage with node/edge inspector and evidence states · Sources with status + sync history · Freshness dashboard + per-asset panel · Incidents list/detail.
**P1:** Quality · **Evidence explorer** · Glossary + PII tagging · Domains · Data products + contracts.
**P2:** 3D modes · advanced impact/root-cause · **time travel** · audit log + admin settings.

Note for our wave plan: the spec puts the **evidence explorer at P1** and **time travel at P2**. v2's Wave 3 puts both together; if we run short, ship the explorer and disclose that time travel is limited (v2 §11 D5) rather than dropping the explorer.

**The spec's own stop rule:** *do not add more connectors, AI features, or dashboard visuals until the first five demo workflows can be reproduced end to end from real imported or live data, with visible provenance and no silent mock fallback.*

## 18. Deferred by the spec itself (safe to not build, cite this file)

Kafka / Elasticsearch / Neo4j-as-primary · external CDC · connector marketplace · enterprise SSO/SCIM · personas & purposes (start with simple roles) · ratings/endorsements · announcements · Slack/Teams delivery (schema only) · usage analytics · MCP context API (only after RLS, permissions and provenance are reliable) · grounded-RAG evaluation · MLflow · Iceberg REST / RDF / DCAT / DPROD (prioritize **OpenLineage + ODCS** only) · graph neural nets · causal claims · auto-lineage from name similarity · any numeric confidence.
