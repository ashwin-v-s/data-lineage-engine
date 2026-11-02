# Kairos Architecture v2 — Perplexity-aligned product, research-safe

**Status:** architecture of record for the completion sprint (target = 100% of the project: working multi-user product **+** defensible research findings).
**Supersedes for product scope:** [KAIROS_ONE_PAGE_ARCHITECTURE.md](KAIROS_ONE_PAGE_ARCHITECTURE.md) (2026-10-31) and the product half of [KAIROS_FINAL_ARCHITECTURE.md](KAIROS_FINAL_ARCHITECTURE.md) (2026-10-29).
**Still binding unchanged:** [FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md](FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md) — the research contract (four-state semantics, bitemporal model, ground-truth separation, metrics, protocol) is **not** reopened by this document.
**Primary new input:** `docs/Perplexity/perplexity.txt` (2026-11-01) — UI screen inventory, freshness model, change-detection mechanisms, Supabase/Postgres positioning, evidence-by-source model, and competitor auth/connector analysis (DataHub, OpenMetadata, Atlan, Monte Carlo, Marquez, Amundsen, Atlas).
**Reality baseline:** [PROJECT_STATUS_2026-11-02.md](PROJECT_STATUS_2026-11-02.md).
**Component-level checklist (what must be on each screen, per state, per field):** [KAIROS_PRODUCT_SPEC_PERPLEXITY.md](KAIROS_PRODUCT_SPEC_PERPLEXITY.md) — this document decides *scope and rules*; that file enumerates *buildable units* taken from the same source, including the per-screen component counts, failure-state copy, connector-diagnostics fields, PII ladder, poster wording, and the list of things the source spec wrongly assumes we already have.

---

## 1. Positioning (one paragraph, quotable in report/poster)

> Kairos is an evidence-first metadata and lineage workspace. Like DataHub/OpenMetadata/Atlan it catalogs assets, schema, ownership, lineage, quality and governance; unlike them it shows **why** each relationship is trusted — `OBSERVED`, `POSSIBLE`, `REFUTED_FOR_RUN` or `UNKNOWN` — with the evidence record, coverage, and the valid/recorded time behind the conclusion. PostgreSQL on Supabase is the single authoritative store; every source a user authorizes flows through one versioned ingestion contract; every conclusion is derived from stored evidence, never from ground truth and never from a fixture silently substituted for live data.

## 2. What v2 changes relative to the previous architectures

| # | Change | Source of the change |
|---|---|---|
| 1 | Product surface grows from "import → catalog → lineage demo" to a **14-screen workspace** (Home, Catalog, Asset Detail, Lineage, Sources, Freshness, Quality, Incidents, Evidence, Glossary, Domains, Data Products, Settings, Notifications) | Perplexity §1–§18 |
| 2 | **Freshness becomes a first-class engine** (SLA × schedule × evidence × state), not a badge | Perplexity freshness analysis |
| 3 | **Three distinct update mechanisms** are named and separated: scheduled pull, push/webhook, and internal Realtime-for-refetch | Perplexity change-detection analysis |
| 4 | **Connector lifecycle is a state machine** and credential success ≠ discovery success | Perplexity §4.C, §2.2 |
| 5 | **Capability registry** gates UI tabs — no tab may look functional when its backing capability is absent | Perplexity §4.B |
| 6 | Source authorization and platform authorization are formally separated (two layers) | Perplexity auth competitor analysis |
| 7 | Evidence record is standardized across *all* source kinds (SQL, dbt, OL, PG catalog, GitHub, file, ML, RAG, manual) | Perplexity evidence-by-source table |
| 8 | `confidence` is **redefined** (see §3 C1) so the product spec and the research contract stop contradicting each other | pack §14/§19 vs ONE-PAGE §4 |
| 9 | Five streams re-divided as end-to-end vertical slices with named owners and gates (§7) | status audit |
| 10 | Source access becomes a **normative screen spec** — five wizard states, credential scopes per source, minimum-permission tables (§9); the capability registry is *derived from the granted scope* | Perplexity §4.C/§6/§10/§13 + competitor auth analysis |
| 11 | The **demo is specified step by step, with what is real at each step** (§10), and the seven-screen minimum plus the pre-conditions are binding | Perplexity §18 + §14 |

## 3. Conflict resolutions (normative — these are decisions, not discussion)

**C1 — "confidence" (real contradiction, now closed).**
The research pack LOCKS "no numeric confidence in v1" and the M5 audit forbids rendering a percentage; the Perplexity spec displays "Confidence" in the edge inspector (§5) and asks for a **"Confidence indicator: High / medium / low"** in the evidence explorer (§10), while its own evidence JSON example stores `"confidence": null`.
→ **Rule:** the stored field stays **`null`** (exactly as the spec's own example). The UI may render an **ordinal** "Evidence strength: High / Medium / Low" derived by published rule from `evidence_state` + `coverage` + `evidence_kind` — e.g. `OBSERVED`+full coverage+lineage facet ⇒ High, `DECLARED`/`PARSED` ⇒ Medium, `UNKNOWN`/partial coverage ⇒ Low, with the mapping documented and returned by the API so the client never re-derives it. A **percentage is forbidden** unless it is a *measured* statistic from the research track with a protocol version attached. Never label the ordinal "Confidence 87%", never label the enum as a score. M5 freezes the mapping string set; M3 renders it.

**C2 — `REFUTED_FOR_RUN` preconditions (ONE-PAGE loosened the rule).**
→ **Rule:** the pack's complete-negative-evaluation contract stands — a run ID, a non-empty coverage manifest declaring that run fully observed, and an explicit negative evaluation record. Absence of an event yields `UNKNOWN`/`POSSIBLE` **only**. `tests/test_engine_rules.py` + `M4_TODAY_TEST_REPORT.md` are the enforcement evidence; any UI that renders a negative edge without those fields fails Gate 3.

**C3 — freshness "late" vs "missing evidence is not absence" (the trap in Perplexity's own model).**
→ **Rule:** `LATE`/`STALE` require a *known* last-successful-update time from evidence. No evidence at all ⇒ `UNKNOWN` with an explicit "why we cannot tell" string. A sync failure is a connector-state event, not a freshness verdict.

**C4 — storage topology.**
→ **Rule:** PostgreSQL (Supabase) is authoritative; `pgvector` is an *index inside the same database*; Neo4j stays a rebuildable projection behind decision gate D-06; **no Kafka, no Elasticsearch, no separate graph DB**. This is the OpenMetadata pattern, which the competitor analysis validates, and it keeps DataHub's multi-store operational cost out of a student MVP.

**C5 — AI features (RAG, MLflow, MCP).**
→ **Rule:** deferred to Wave 4+ and explicitly labelled product features, never research contributions. A RAG answer may only cite metadata the caller is authorized to read, and its factual correctness is `UNKNOWN` until evaluated.

**C6 — Realtime.**
→ **Rule:** Supabase Realtime payloads are invalidation signals that trigger an authorized refetch; they never carry authoritative or cross-workspace data, and Realtime is never an ingestion queue.

**C7 — the two competing M1–M5 definitions.**
`docs/workstreams/*.md` (research-milestone view) and `PROJECT_COMPLETION_AND_TEAM_PLAN.md` Part B (product-stream view) describe different scopes under the same labels.
→ **Rule:** this document's §7 stream table is the operating definition for the completion sprint; `docs/workstreams/*` stays as the historical research-milestone record.

## 4. Layered architecture

```
L0 SOURCES     user PostgreSQL (read-only role) · GitHub App (repo-scoped) · dbt manifest/run_results
               OpenLineage emitter · file/folder upload · CLI
L1 INGESTION   one orchestrator, many typed adapters → validate → PREVIEW (read-only) → COMMIT (1 txn, idempotent)
               durable job queue + scheduled pull workers + webhook receivers  [NEW in v2]
L2 STORE       Supabase PostgreSQL: identity · catalog · raw_event · evidence · lineage_edge + edge_temporal_version
               execution_state · import_run · source_connection · freshness_sla/evaluation · incident(+event)
               quality_assertion/result · glossary_term · domain · data_product · data_contract · notification
               workspace_member/invite · audit_log · pgvector embeddings
L3 API         FastAPI /api/v1, fail-closed bearer auth, capability registry, stable error shape, size caps
L4 RESEARCH    isolated runner: SQLGlot/dbt/OpenLineage → four-state engine → metrics vs B1–B5,
               loss simulation (6 mechanisms), independent ground truth — never imported by L1–L3
L5 PRODUCT     React shell + retained CSS/legacy renderer: 14 screens, edge/evidence inspector, time travel,
               data-mode labels (LIVE / IMPORTED / DEMO FIXTURE)
L6 OPS         Vercel (frontend dist + backend function) · Supabase Auth/RLS · CI ci/contract/e2e/live-smoke
```

**Hard invariants (all five streams bound by them):**
1. PostgreSQL is the only authority. Projections are derived and rebuildable.
2. Missing evidence ⇒ `UNKNOWN`/`POSSIBLE`, never a negative edge (C2).
3. Ground truth (`PROPAGATED`/`NOT_PROPAGATED`) never enters a predictor, the product API, or user-facing conclusions.
4. A source credential authorizes **Kairos' backend** to read a source; Kairos membership + RLS authorize **a user** to see metadata. Separate, never conflated (C6 of the auth analysis).
5. No fixture is silently substituted for a failed live call; every record carries `source_mode ∈ {LIVE, IMPORTED, DEMO_FIXTURE}`.
6. Authorization is enforced in the API and in RLS — never by hiding UI, never from JWT `user_metadata`.
7. A tab is only rendered as available when the capability registry says so (C5 of the competitor analysis).
8. No claim in a report, poster or viva answer without a test, a query, or a screenshot behind it.
9. **Never derive an edge per input × output.** An OpenLineage job that reads `customers` + `orders` and writes `customer_summary` + `order_summary` is **not** four edges. Run-boundary evidence proves datasets participated in the run; exact edges come only from the lineage facet. (`tests/test_engine_rules.py` + `tests/test_ingest_pipeline.py` must both hold this.)
10. **Metadata access ≠ data access.** Catalog discovery, query execution, query-log capture and complete runtime lineage are four different permissions. Preview and query-log scopes are opt-in and off by default, so a profiler or preview panel reports `supported: false` rather than inventing values.
11. **Revocation does not rewrite history.** When a credential expires or an installation is revoked, the connection moves to `CREDENTIALS_EXPIRED`/`REVOKED`, sync stops, and already-imported evidence stays as historical evidence under a stated retention policy — it is neither silently wiped nor silently refreshed.

## 5. Contracts (frozen; changing one needs all consumers in review)

**5.1 Ingestion envelope `kairos.ingest.v1`** — unchanged from KAIROS_FINAL §3: `{contract_version, source{kind,ref}, workspace_id (server-derived), idempotency_key, assets[], relationships[], runs[], evidence[], diagnostics[], provenance{adapter, adapter_version, content_sha256}}`. Preview writes nothing; commit is one transaction; a repeat with the same key returns `replayed: true`; invalid input returns diagnostics, never an empty success.

**5.2 Evidence record** — the union of the pack's semantics and Perplexity's source-neutral shape:

```json
{ "evidence_id": "uuid", "raw_event_id": "uuid|null",
  "source_type": "sqlglot|dbt_manifest|dbt_run_results|openlineage|postgres_catalog|postgres_query_log|github|file_upload|mlflow|rag_trace|manual|profiler",
  "source_system": "warehouse|github|dbt|airflow|user-upload|null",
  "evidence_kind": "structural|declared|runtime|profile|classification|content|manual",
  "evidence_state": "OBSERVED|POSSIBLE|REFUTED_FOR_RUN|UNKNOWN",
  "connection_id": null, "run_id": null, "artifact_version": null,
  "subject": {"asset_urn": "…", "column": "…"}, "related_subject": {…},
  "observation": {"statement": "…", "confidence": null,
                  "coverage": {"run_scope":"full|partial|unknown","field_coverage":"…"},
                  "complete_negative_evaluation": false},
  "temporal": {"event_time":null,"valid_from":null,"valid_to":null,"recorded_from":null,"recorded_to":null},
  "provenance": {"producer":null,"artifact_uri":null,"parser_version":null,"extraction_span":null,"redacted_fields":[]},
  "source_mode": "LIVE|IMPORTED|DEMO_FIXTURE" }
```

Every source follows the same five-step pipeline: capture raw → immutable raw record + provenance → normalize to source-neutral evidence → resolve canonical identity → derive the four-state conclusion without ground truth. Then the UI must answer five questions for whatever it shows: **what do we know · how do we know it · when did we learn it · for which run or time period · what remains unknown**.

**PII classifications are evidence records too**, with their own propagation ladder — `PII_SOURCE → PII_INHERITED (column lineage proves a copy) → PII_MASKED (mask/hash detected) → PII_POTENTIAL (static inference) → PII_CLEARED (aggregation, no identifiers — requires review)`, plus `UNKNOWN` where lineage is missing. A manual steward tag is `OBSERVED` manual classification; an inherited one through parsed SQL is `POSSIBLE` with provenance. **Classification propagates; data access never does** — inheriting a PII tag must not hide or reveal values (§9.8).

**5.3 Capability registry** — `GET /api/v1/assets/{id}/capabilities` → `{schema, preview, lineage, quality, runs, profile, usage, freshness}` each `{supported, available, reason?}`. The UI renders tabs **from** this response; a `false` value must render an honest empty/unsupported state. Reason strings are user-facing copy and follow the spec example:

```json
{ "schema":   { "supported": true,  "available": true },
  "preview":  { "supported": true,  "available": false, "reason": "No preview data retrieved" },
  "lineage":  { "supported": true,  "available": false, "reason": "No lineage evidence ingested" },
  "quality":  { "supported": false, "available": false, "reason": "Unsupported resource type" } }
```

Two levels are required, not one: a **resource-type** registry (what a table vs a pipeline vs an ML model could ever support) and an **instance** registry (what *this* asset supports, given the scope granted on its connection and the evidence actually ingested). `reason` is never a raw error string or stack trace. (Implemented as one route in [capabilities.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/capabilities.py) — uncommitted, instance-level only, and not yet consumed by any tab.)

**5.4 Connector lifecycle** — `CONFIGURED → AUTHENTICATED → REACHABLE → AUTHORIZED → DISCOVERY_IN_PROGRESS → DISCOVERY_COMPLETED → NORMALIZED → PERSISTED → REFRESH_IN_PROGRESS → STALE | SYNC_FAILED | CREDENTIALS_EXPIRED | REVOKED`. Each transition is a row in the sync history, never implied by the previous one. The Sources screen renders exactly these states — see §9.1 for the "test ≠ discover" rule.

**5.5 Sync/incremental record** — `last_full_sync_at, last_incremental_sync_at, last_successful_discovery_at, last_successful_sync_at, next_scheduled_sync_at, sync_cursor, source_snapshot_hash, sync_status, sync_duration_ms, records_created, records_updated, records_unchanged, records_deleted, records_failed, errors[], warnings[], permission_gaps, source_version`. This is the connector-diagnostics payload (`GET /sources/{id}/health`): five *sync modes* have to be distinguishable in it — full snapshot, incremental (cursor: `updated_at` / commit SHA / event id / watermark), event-driven, scheduled, and manual refresh. A full scan on every refresh is not acceptable: it is slow in front of an audience and it hides what actually changed.

**5.6 Freshness record** — `freshness_sla(asset_urn, sla, signal_type, signal_column, evaluation_schedule, lookback, incident_policy)` + `freshness_evaluation(asset_urn, observed_at, age, state, evidence_id)`, states `HEALTHY (≤80%) | AT_RISK (>80%) | LATE (>SLA) | STALE (>n×SLA) | UNKNOWN (no evidence) | PAUSED (explicitly disabled)`, each carrying the evidence row that justifies it.

**5.7 Identity/URN** — `kairos:<type>:<namespace>:<source_native_id>`; display name is never identity; UUID v5 deterministic. **Note:** `backend/app/identity/canonical_ids.py:254` is a live `NotImplementedError` — one identity path is unfinished while this contract claims LOCKED.

**5.8 Auth/role** — JWT `{sub}` only; role/permissions come from `workspace_member` server-side. Roles: `viewer, steward, editor, connection_owner, admin`, with the Perplexity MVP permission matrix (`catalog:read, lineage:read, metadata:write, pii:classify, data:preview, incident:manage, connection:admin`).

## 6. Update mechanisms (named, because the MVP must not blur them)

| Mechanism | Used for | v2 decision for Kairos |
|---|---|---|
| Scheduled **pull** | user PostgreSQL catalog, GitHub repo tree | a runner (Supabase Cron / small worker / GitHub Action calling an authenticated endpoint) — **not** a Vercel request, which caps at `maxDuration: 30`. MVP: hourly for demo assets, daily otherwise. |
| **Push / webhook** | OpenLineage events, dbt CI artifacts, GitHub push | receiver validates signature + schema, stores the immutable raw event, enqueues, then normalizes. Idempotent by event ID. |
| Internal **Realtime** | UI refresh after a Kairos write | invalidation → authorized refetch only (C6). |

Explicitly **not** built: external CDC/logical replication from user databases, connector marketplaces, enterprise SSO/SCIM, purpose-based access, graph neural nets, causal claims.

## 7. Five streams → five people (end-to-end vertical slices)

Every stream owns **its own migration + API routes + UI screens + tests + docs**; nobody is "backend only" or "CSS only". Current owners follow demonstrated history; swap only as a pair so the slice stays intact.

| Stream | Owner (GitHub) | Mission | Owns | Gate |
|---|---|---|---|---|
| **M1 Platform: identity, workspace, deployment, contract** | Jatin (`Jat-in32006`) | a stranger can sign up, be isolated, and reach a deployed URL | `workspace_member/invite` + RBAC, `auth.py`, `main.py`, `contracts/openapi.json`, migrations registry, Vercel + secrets, CI/`live-smoke`, CODEOWNERS | a real signup → verify → sign in; unauthorized → 401; two-workspace test proves isolation; `live-smoke` green |
| **M2 Connectors & ingestion engine** | Anushka (`AnaaMorr`) | every authorized source materializes honestly through one pipeline | `ingest.py`, `sources.py`, `ingestion/*` adapters, OpenLineage webhook, PG read-only connector, GitHub App, dbt `run_results`, scheduler + sync history | connect → preview (no writes) → commit once → refresh → read back; duplicate commit idempotent; unsupported input → diagnostics |
| **M3 Catalog, lineage & evidence** | Ashwin (`ashwin-v-s`) | the differentiator: every conclusion shows *why* | `assets.py`, `lineage.py`, `search.py`, `evidence` + `edge_temporal_version` queries, capability-driven tabs, edge inspector, evidence explorer, time travel, `pgvector`, export | every visible edge shows real evidence state; declared/parsed never renders as observed; time travel discloses gaps |
| **M4 Governance & product shell** | Gauree (`gaureehatkar`) | the workspace a user actually lives in | shell + Home, `governance.py`, `freshness.py`, incident lifecycle UI, quality assertion/result tables+API+UI, glossary/domains/data products/contracts, notifications + Realtime, Settings | a breach creates exactly one incident + owner notification from stored evidence; 7 demo screens on live data |
| **M5 Research integrity & demo honesty** | Pranav (`pranav-samal`) | the claims: real findings, no fabrication, no fake demo | `research/*` (protocol, benchmarks, missingness, experiments, metrics, baselines, ground truth), leakage/boundary tests, data-mode enforcement, E2E acceptance gates, `docs/DEMO_SCRIPT.md`, results report | a non-plumbing experiment run completes with protocol hash + GT hash + git SHA; every screen labels `LIVE/IMPORTED/DEMO FIXTURE`; forced API failure shows an error, not a fixture |

### Waves

| Wave | Goal | Gate to leave the wave |
|---|---|---|
| **0 — Stop the bleeding (≤1 day, M1+all)** | restore shared-DB access, commit+push the tree as reviewable PRs per stream, delete the unverified "APPLIED" claims until re-proved, fix CODEOWNERS, make `main` buildable | `list_tables.py` output pasted in the PR; `pytest` with `KAIROS_LIVE_API_TESTS=1` running, not skipping |
| **1 — Unblock** | M1 membership/RBAC live; M2 commit path proven on the shared DB; M4 shell + data-mode label everywhere | signup works; idempotent replay returns `replayed:true`; no view hides its `source_mode` |
| **2 — User-visible value** | M2 add-source wizard + scheduled PG sync + OL webhook; M3 catalog/lineage on committed data + edge inspector; M4 freshness schedule + incidents + Home | connect→sync→history visible; edge click shows evidence rows; breach→incident→acknowledge→resolve loop closed on live rows |
| **3 — Differentiation & completeness** | M3 evidence explorer + time travel + hybrid search; M4 quality assertions, glossary/domains/products/contracts, notifications; M1 capability registry consumed everywhere | 7 minimum demo screens real; tabs gated by registry |
| **4 — Product + findings** | M1 deployed URL + green `live-smoke`; M4 Realtime; **M5 real experiment** (benchmark cases frozen, protocol TBD=0, `run_real()`, K1–K8 filled, findings written); demo runbook + viva gates | all five gates pass on the deployed URL; results section has measured numbers with protocol/GT hashes |

## 8. What v2 deliberately does **not** build

Kafka/Elasticsearch/Neo4j **as a primary store** (Kafka as an event *transport* into the §5.5 receiver is in scope — see §9.2), external CDC/logical replication from user databases, connector marketplace, enterprise SSO/SCIM, purpose-based access, auto-generated lineage from name similarity, causal-inference or graph-neural claims, unlabelled demo data, any numeric confidence (C1).

**Boundary that used to be blurred:** *LLM/RAG as the reasoning engine* is out; **a RAG trace as an evidence source** is in (§9.2) — we record and display what an AI system retrieved, we do not let a model decide lineage. Likewise **MLflow is in scope for the demo** (D11) as a training-lineage source; it is not a model-serving or feature-store product. Nothing in this section is a licence to hide an unwired source: unwired means `NOT AVAILABLE — <reason>` on the Sources screen.

## 9. Source access & credential specification (normative)

This is the section the previous architectures only implied. It comes from Perplexity §4.C, §6, §10, §13 and the competitor auth/connector analysis, and it is what the **Sources** screen and the M2 connector API must actually implement.

**9.1 The wizard has five states, not three buttons.**
`type → credential → test → scope → discover` (+ a **review discovered assets → save connection and schedule** step, as DataHub/OpenMetadata both do), mapping onto §5.4: **test** means `AUTHENTICATED`+`REACHABLE` and ingests nothing; **scope** records the granted permissions; **discover** is `DISCOVERY_IN_PROGRESS → DISCOVERY_COMPLETED` and is the only step that produces assets. The UI must label which action just happened. Five rules:
- A failed test never leaves a connection showing "connected", and a credential test is never presented as discovery (the spec's own anti-pattern: *"Fake 'connected' status after credential test"*).
- "Discovered 0 assets" and "discovery failed" are different outcomes with different copy; the second is never rendered as an empty catalog.
- **Partial authorization is its own state.** If the role reaches some schemas but not others, the UI says "Connected but partial authorization", lists the `permission_gaps`, and offers "grant metadata read on X" or "reduce selected scope" — it does not show a green tick and it does not show a red failure.
- A secret is never re-displayed in plaintext in any screen, log, or sync-history row. The licensed display form is a **masked** value — `postgres://demo_user:••••••@host:5432/sales` or `kairos_reader @ db.example.com:5432 / sales` — with the password always collapsed to `••••••`; the plaintext is resolved server-side by the worker at job time only, encrypted at rest with `KAIROS_TOKEN_ENCRYPTION_KEY`.
- The connection row records **what was granted**, so a capability can later be explained ("query-log lineage: not authorized") without re-reading the credential.

**9.2 What each source can and cannot yield — and all of them are in the demo.**
This is the **complete source set**, not a shortlist. Decision **D11**: every row ships in the demo, because each one demonstrates a *different evidence state* — that is the whole research claim made visible. A source that yields only `POSSIBLE` is as valuable on stage as one that yields `OBSERVED`; what is not allowed is a source that is *claimed* but never connected. The competitor column is not background reading: those products run these pipelines today, so their flow **is** our implementation spec — copy the shape, then shrink the scope.

| Source | Kairos reads / ingests | Best attainable state | Never proves | Working model to copy |
|---|---|---|---|---|
| SQL + schema (SQLGlot) | parsed tables, columns, joins, CTEs, aliases; extraction span | `POSSIBLE` | that a run executed it; unsupported constructs must surface as diagnostics, never silence | SQLGlot's own column-lineage API + the spec's `extraction_span {start,end}` provenance record |
| dbt `manifest.json` | nodes, sources, exposures, tests, `depends_on.nodes`, descriptions | `DECLARED` → `POSSIBLE` | that a model ran or rows propagated | dbt's artifact contract; OpenMetadata's dbt ingestion (manifest → entities + `lineage` facet) |
| dbt `run_results.json` | per-model success/failure/skipped/timing/`unique_id` | `OBSERVED` **for the test outcome only** | column-level propagation | DataHub's dbt-source emit: results become *status* aspects, not lineage edges |
| OpenLineage run event | job, run id, inputs, outputs, timestamps, facets | `OBSERVED` at the **run boundary** | an edge from every input to every output — **never build the Cartesian product** (invariant 9); exact edges only from the lineage facet | OpenLineage spec 1.48 + the Airflow/Airflow-like emitter pattern: `START`/`RUNNING`/`COMPLETE` with the same run id |
| OpenLineage **lineage facet** | explicit `dataset`/`field` `parentLink`/`transformation` mappings | `OBSERVED` for the supplied edge | completeness of instrumentation | OpenLineage `ColumnLineageFacet`; render field-level only when the facet actually carries it |
| PostgreSQL catalog (`kairos_reader`) | `information_schema`/`pg_catalog`: schemas, tables, columns, types, constraints, comments | `OBSERVED` that *structure existed at discovery time* | row content, usage, query execution, lineage | OpenMetadata's metadata-only ingestion user (`USAGE` + `SELECT` on `information_schema`, never write) — see §9.4 |
| PostgreSQL **query log** | captured statements → parsed table/column references | `OBSERVED` that a query referenced them; `POSSIBLE` lineage | complete runtime propagation unless the parser proves it | DataHub's query-log ingestion (`datahub-upgrade`/`pydatahub` usage source) and Atlan's usage-based lineage: **separate elevated grant, opt-in, off by default** |
| GitHub App / PAT | repo tree at a pinned commit, file contents, commit SHA, path, hash | `OBSERVED` that `repo://org/repo/path@abc123` existed; `POSSIBLE` for parsed edges | that the SQL ran anywhere | OpenMetadata's GitHub/`source_code` ingestion; then run the SQL/dbt/OpenLineage parsers **on the discovered files only** |
| File upload — JSON metadata | declared assets + explicit relationships | `OBSERVED` that the user supplied it; content state per source | source authenticity or live connectivity | DataHub `file`/`json` publisher (`datahub publish`) — an **import event**, never a connector |
| File upload — CSV | file metadata + header names | columns `OBSERVED` (names only); types/profile `UNKNOWN` unless a profile ran | row values, quality, lineage | Great Expectations / Monte Carlo profiler shape: header read ≠ profile; a profile is its own run with its own timestamp |
| File upload — document | path, MIME type, size, extracted text **if implemented** | metadata `OBSERVED`; semantics `UNKNOWN` | content meaning | OpenMetadata `document`/file ingestion; state "extraction not implemented" rather than inventing meaning |
| File upload — image | MIME type, dimensions, hash, thumbnail if available | metadata `OBSERVED`; content meaning `UNKNOWN` | anything about what the image shows | same as document; a hash + dimensions is the whole honest claim |
| **MLflow** | model version, run id, parameters, metrics, artifacts, `tags`, training dataset / feature references, code version | `OBSERVED` **training** lineage (`model.churn@v7 was trained with these inputs`) | that any feature contributed at inference; every downstream prediction | MLflow's own Model Registry + `run.inputs.dataset_inputs` — read it, do not reinterpret it. The spec files this as P3; **D11 overrides that for the demo** and M5 must keep the wording to "training lineage" |
| **RAG trace** | query, retrieved chunks, prompt, model, answer, token counts | `OBSERVED` that retrieval/generation happened; factual correctness `UNKNOWN` until evaluated | that the answer is grounded or correct | the spec's trace contract; grounded-RAG evaluation is a *separate* measured artifact — until it exists, the UI says `UNKNOWN` |
| **Profiler** | row count, null rate, distinct count, distribution, min/max at a moment | `OBSERVED` profile **at that timestamp** | complete data quality, lineage, or that the profile still holds | Great Expectations/Monte Carlo: a profile is an evidence row with `observed_at`, never a standing attribute |
| **Manual steward action** | human classification, approval, relationship assertion, owner assignment | `OBSERVED` that a human decided (with `MANUAL` provenance, who, when) | that the decision is technically correct; a manual edge is **not** runtime-observed | Collibra/Alation stewardship queues: assignment + reviewer + timestamp, and Atlan's "manual confirmation counts as evidence, labelled as manual" |
| Kafka / event bus (transport, not a catalog source) | OpenLineage or CDC-style events delivered as a stream | same states as the underlying event | anything beyond what the event carries | DataHub's `policies`/`executor` + Kafka relay: **the queue is a transport for the receiver in §5.5, never a second source of truth** |

**Demo consequence (D11).** The Sources screen must offer every row above, and the demo must be able to say, for each one that is wired: *"this is connected, this is what it proved, this is what it cannot prove."* Rows that are not wired by demo day are shown as **`NOT AVAILABLE — <reason>`** (the registry, §5.3/§9.6), never hidden and never faked. Priority inside the set is fixed by what the claim needs: SQL + dbt + OpenLineage + PostgreSQL + GitHub + file upload carry the four-state story; MLflow, RAG trace, profiler and query-log lineage extend it and must each be *honestly labelled* if they are present at all.

**9.2.1 The one pipeline shape for all of them.** Every source follows the same five steps, so a new connector is a parser plus a scope, not a new subsystem:

```text
acquire artifact (pull on schedule | push/webhook | user upload | human action)
  → store immutable raw artifact + content hash           [raw_event / import_run]
  → normalize to evidence records (§5.2 contract, source_type per row above)
  → resolve canonical identity (§5.7) then edges/relations  [never input×output]
  → project to catalog + lineage + governance views, each tab gated by §5.3
```

At every step the state is decided by *what the artifact actually contained* — the four-state table in the Perplexity evidence section is the acceptance checklist for this pipeline, and `UNKNOWN` is a valid, shippable outcome.


**9.3 GitHub — App is the product path, fine-grained PAT is the demo fallback (decision D2).**
Minimum permissions, and nothing more: **Metadata: read** (required — how the app enumerates what it was granted), **Contents: read** (required — the files), **Webhooks: read/write only if incremental sync is implemented**, **Administration / Actions / Secrets / Pull requests: none** — and *no write permission ever, merely to catalog a repository*. Flow: register app → user installs on selected repos → callback validates `state` and the webhook signature → installation id bound to the workspace → read at a pinned commit. PAT fallback: user creates a repo-limited read-only PAT, pastes once, Kairos encrypts server-side; the UI must say plainly that a PAT gives no webhook and no revocation event, so incremental sync degrades to polling.
**Sign-in ≠ source access.** GitHub/Google OAuth into Supabase proves identity only; it is a separate, explicitly-granted step before Kairos can read a repository, and the demo must say so out loud.

**9.4 PostgreSQL — a dedicated read-only role, never a user's admin credential.**
```sql
CREATE ROLE kairos_reader LOGIN PASSWORD '<secret, server-side only>';
GRANT CONNECT ON DATABASE app_db TO kairos_reader;

GRANT USAGE ON SCHEMA analytics TO kairos_reader;          -- structure only, by default
GRANT SELECT ON information_schema.tables TO kairos_reader;
GRANT SELECT ON information_schema.columns TO kairos_reader;
-- Data preview requires an additional, explicitly-granted SELECT ON tables:
-- GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO kairos_reader;
```
Connection test = `SELECT 1` plus an assertion that the role is not superuser and has no write grants; credentials are schema-scoped, secret-managed, testable, revocable. The capability→permission map the discovery code must honour:

| Capability | Source permission | Kairos feature |
|---|---|---|
| List schemas/tables/views | catalog metadata read | Catalog discovery |
| Columns, types, nullability | catalog metadata read | Schema tab |
| Primary/foreign keys | catalog metadata read | Relationship **candidates**, never runtime lineage |
| Table/column comments | comment read | Descriptions |
| Table statistics | optional elevated | Profiling hints |
| **Query logs** | **separate elevated grant** | Runtime lineage candidates (default: not authorized) |
| **Execute data queries** | **separate explicit grant** | Preview / profiling only |

**9.5 File upload is an *event*, not a connection.**
The same `kairos.ingest.v1` preview→commit path applies, with `provenance.content_sha256` as the identity of what was imported. It must **not** appear in the Sources list as a live connector with a sync schedule or a "last synced" clock — it appears in import history. `source_mode = IMPORTED` for a user's own file, `DEMO_FIXTURE` for anything shipped in the repo.

| Uploaded artifact | Evidence produced | Honest state |
|---|---|---|
| JSON metadata graph / dbt manifest / OpenLineage event | structural or declared records, explicit relationships | `OBSERVED` that the user supplied it; content state per source table above |
| CSV | file metadata + header names | columns `OBSERVED` (names only); **types and profile `UNKNOWN` unless a profile actually ran** |
| Document | path, MIME type, size, extracted text if implemented | metadata `OBSERVED`; **semantics `UNKNOWN`** |
| Image | MIME type, dimensions, hash, thumbnail if available | metadata `OBSERVED`; **content meaning `UNKNOWN`** |

File membership is inventory, not lineage; a header read never inspects rows; and nothing in this path may be described as a live connector.

**9.6 Scope drives the capability registry — this is how "never show a tab as functional" is implemented.**
`GET /assets/{id}/capabilities` (§5.3) must be computed from the *granted scope + connector type*, not hardcoded: e.g. "Read query logs" unchecked ⇒ `usage: {supported: false, reason: "query-log scope not granted"}`; metadata-only catalog ⇒ `preview: {supported: false, reason: "Kairos reads structure, not row data"}`. The UI renders tabs from that response and shows the reason.

**9.7 Limits on untrusted input.**
Cap request bytes, file count, nesting depth, row/asset count and parse time; reject over-limit with actionable diagnostics; never execute SQL that arrives in an upload; treat repo contents and uploaded files as untrusted. Invalid records go to a **failed-record quarantine** rather than being dropped silently or written as junk assets.

**9.8 Metadata access ≠ data access (the boundary the demo must state).**
Atlan's posture is the model: the platform *"reads metadata, not production data"*, and data preview is centrally disableable. For Kairos that means four distinct permissions — catalog discovery, query execution, query-log capture, and complete runtime lineage — and the UI must never collapse them. Default scope is **metadata read**; `Enable data preview` and `Read query logs` are separate opt-ins that a viewer role cannot grant to itself. A "sample values" pane in Quality (§8 of the product spec) therefore shows counts + the assertion SQL unless `data:preview` was granted.

**9.9 Revocation and retention.**
Credential expires or the GitHub installation is revoked → next health check fails → `CREDENTIALS_EXPIRED` / `REVOKED` → discovery and sync stop → **already-imported evidence remains as historical evidence**, visible to whoever is still authorized, until the retention policy removes it or the user asks for deletion. Never keep a connection showing "Connected", never let stale evidence keep being presented as current (`STALE` + a last-successful-sync timestamp), and never delete imported evidence as a side effect of disconnecting.

## 10. Demo specification — exactly how the demo runs

**One sentence:** *a stranger signs up, authorizes a real source, and every visible conclusion shows the evidence behind it.*

**Pre-conditions (the demo does not start until all are true, §11 gate 0):** shared-DB auth restored and `scripts/test_connection.py` green; migration status for `0004–0009` measured against the live DB rather than asserted in file headers; per-stream PRs merged to `main`; a deployed Vercel URL with green `live-smoke`; one seed source the team can re-authorize in front of an audience; `docs/DEMO_SCRIPT.md` (M5) holding this section's steps as the runbook.

**Cast:** Account **A** (presenter) and Account **B** (isolation check). No third party, no service role in the browser.

| # | Screen | What happens | What is demonstrably real | Fails if |
|---|---|---|---|---|
| 1 | *(signed out)* | `curl /api/v1/assets` | 401 fail-closed; identity comes from Supabase, not a JSON body | any anonymous read returns rows |
| 2 | Sign up / verify / sign in | Supabase email confirmation → first authenticated call provisions A's personal workspace | Settings shows workspace + role from `workspace_member`, not JWT `user_metadata` | verification or provisioning unproven |
| 3 | **Home** | "What needs my attention": source health, freshness breaches, open incidents, my ownership | every card is an API count; **every number is a clickable filtered link** | any number comes from a fixture |
| 4 | **Sources → Add source** | PostgreSQL: host/port/db/read-only user/SSL → scope checkboxes (`Enable data preview` and `Read query logs` left **off**) → workspace + visibility → **Test connection** | badge moves to `AUTHENTICATED`/`REACHABLE`, secret renders `••••••`, **0 assets imported**, preview/query-log capability reasons already say "not authorized" | test and discover are the same button |
| 5 | Sources → **Discover metadata** | catalog read via `kairos_reader` → **review discovered assets** → save + schedule; then upload a dbt `manifest.json` → **Preview** | counts, warnings, unsupported constructs, `permission_gaps` if a schema was unreachable, provenance (adapter + version + `content_sha256`), `IMPORTED` chip; preview has written nothing | a partial grant renders as full success, or preview mutates the DB |
| 6 | **Commit** | one transaction → import-run id + audit row | refresh browser → rows still there; press Commit again → `replayed: true`, counts unchanged | duplicate rows, or data vanishes on refresh |
| 7 | **GitHub** | App install on 2 repos (or PAT fallback) → import the dbt project | evidence row = `repo://org/repo/path@<commit>`; file existence `OBSERVED`, parsed dependency `POSSIBLE` | a declared edge renders as observed |
| 8 | **Catalog → Asset detail** | search, filters, saved views; tabs from the capability registry | a tab whose capability is `false` shows the reason; owners + glossary from stored rows | tabs hardcoded |
| 9 | **Lineage → edge inspector + evidence explorer** | direction / depth (1·2·3·5·custom) / column toggles, legend, mini-map, search-in-graph; click an edge, then open its evidence record | relationship type, state chip, evidence source + `evidence_id`, coverage (complete/partial/unknown), **evidence strength as `High/Medium/Low` derived by rule (C1 — never "87%", never a stored number)**, valid vs recorded time, the explanation sentence, and the raw → parser → normalized → canonical chain | panel shows anything not in the DB, or a table-level run event is shown as column lineage |
| 10 | **OpenLineage → the upgrade moment** | push one run event (curl/emitter) | the same edge moves `POSSIBLE → OBSERVED` with the run id; absence of an event still shows `UNKNOWN`, never a red edge | negative edge from absence |
| 11 | **Freshness → Incident** | SLA on one asset; scheduled evaluator runs | `HEALTHY/AT_RISK/LATE` derived from a stored signal; the asset with no signal shows `UNKNOWN` + "why we cannot tell"; **exactly one incident**, owner notified, timeline detected→ack→investigating→resolved | `LATE` without evidence (C3) |
| 12 | **Time travel + honesty + isolation** | `as_of` / `recorded_as_of` query; log in as **B**; then revoke A's connection | graph as it was at an earlier date with undated rows disclosed; B's catalog is empty and a direct cross-workspace query returns 0 rows; after revocation the UI shows `REVOKED` + the error, **keeps the imported evidence as history (§9.9), and substitutes no fixture** | time travel implies complete history, a disconnect wipes evidence, or a fallback fixture appears |

**The seven screens that must be live** (Perplexity §18 minimum for a strong university demo): Home, Catalog, Asset detail, Lineage, Sources, Freshness, Incidents. The spec's own next tier is **Quality, Evidence explorer, Glossary, Settings** (P1/P2), so if the run shortens, drop Domains/Data Products first and the evidence explorer last — the explorer is the differentiator, not a garnish. Anything fixture-backed must be visibly `DEMO FIXTURE` or hidden behind the capability registry.

**Three sentences the presenter says out loud:** *"This edge is `POSSIBLE` because dbt declared it — nothing here proves it ran." · "This one became `OBSERVED` because an OpenLineage event with a run id arrived two minutes ago." · "This asset is `UNKNOWN`, not `LATE`, because we have no evidence — missing evidence is never absence."*

**Honest limits to state before questions:** search is keyword until `pgvector` lands; Postgres catalogs structure, not usage; the GitHub grant proves file existence at a commit; the research track is a separate evaluation, not a product feature; demo data is labelled wherever it appears.

**Two phrasings are mandatory, two are forbidden** (from the spec's own honesty rules, kept in sync by M5): say **"scheduled freshness monitoring with event-driven updates where available"** — never "real-time monitoring" unless an OpenLineage producer is genuinely connected and tested; say "Supabase-hosted PostgreSQL is our single authoritative store" — never "Supabase automatically shares all data with all users". And per the spec's last demo point: **the UI may not claim semantic search, grounded RAG, live lineage, or tenant isolation in any screen or slide until that exact path has been tested end to end** — a demo whose slide says "AI semantic search" while `search.py` runs `LIKE` is a claim without evidence, which invariant 8 forbids.

## 11. Open decisions (owner + default + when it must be answered)

| # | Decision | Owner | Default in v2 | Needed by |
|---|---|---|---|---|
| D1 | Apply/verify `0004–0009` against the shared Supabase DB and correct the file headers to measured truth | M1 | measure, then document — no "Applied" without `list_tables.py` output | Wave 0 |
| D2 | GitHub: App vs fine-grained PAT | M2 | **App** for the product path, **PAT** allowed as demo fallback (§9.3) | Wave 2 |
| D3 | First live demo source: real PostgreSQL, or labelled fixture? | M2+M5 | real read-only PG + one labelled `DEMO_FIXTURE` fallback only if the live call fails *and the failure is shown* | Wave 2 |
| D4 | dbt `manifest.json` versions supported + `kairos_` OpenLineage facet schema | M2 | manifest v7+; facet schema drafted with fixtures before the receiver ships | Wave 2 |
| D5 | Back-fill `edge_temporal_version` into `lineage_edge`, or limit table-edge time travel? | M3 | limit and disclose undated rows (D-14) rather than imply complete history | Wave 3 |
| D6 | Rollback owner + approval process for schema/RLS changes on the shared project | M1 | named human owner; migrations applied once, checked, with a stated rollback path | Wave 0 |
| D7 | Ship the **data-visibility selector** (`Only me` / `Workspace members` / `Specific roles`) or workspace-wide visibility only? It changes the RLS policy shape, so it must be settled before `0007` | M1 | workspace-wide for MVP, stated plainly in the UI copy | Wave 1 |
| D8 | `Read query logs` as a real capability, or hide the checkbox? | M2 | hide it until a parser exists — a checkbox that grants nothing is a dishonest UI | Wave 2 |
| D9 | Failed-record quarantine + **fixture registry** (the mechanism that keeps demo data provably separate from live data) — new tables or file-based? | M1 + M5 | quarantine table for records; fixture registry as a migration-seeded allowlist of `source_mode=DEMO_FIXTURE` provenance hashes | Wave 3 |
| D10 | Lineage export PNG/SVG/JSON — client-side or server-side? | M3 | client-side PNG/SVG, server-side JSON of the visible subgraph with evidence states included | Wave 3 |
| **D11** | **Source breadth for the demo.** The Perplexity spec files MLflow and RAG-trace lineage as P3; the team decision is that **every source in §9.2 is in scope for the demo**, because each one demonstrates a distinct evidence state | M2 (pipelines) + M4 (Sources screen) + M5 (wording) | **all in scope**, with the rule: wired ⇒ shown with its real state; not wired ⇒ `NOT AVAILABLE — <reason>`, never hidden and never faked. MLflow wording is capped at "training lineage"; RAG at "retrieval observed, correctness `UNKNOWN`" | Wave 2–4 |
| **D12** | **Where do we get a database we can actually test against?** Shared Supabase credentials fail today, and this machine has no Docker and no `psql`, so no local substitute exists either | M1 | fix the shared project first (it is the product's store); if it cannot be restored by the end of Wave 0, install a local PostgreSQL and run `0001–0009` against it as an explicitly-labelled dev DB — never as "verified against the shared project" | Wave 0 |

[docs/VERIFICATION_2026-11-02.md](VERIFICATION_2026-11-02.md) is the executed evidence behind D12 and behind every "not working" item in the handouts. Screen-level detail the checklist exposes beyond D1–D12 is listed in [KAIROS_PRODUCT_SPEC_PERPLEXITY.md](KAIROS_PRODUCT_SPEC_PERPLEXITY.md) §15.

## 12. Consequences for the documentation set

- `docs/workstreams/*.md` = historical research-milestone scope (keep, do not edit).
- `docs/TEAM_GUIDE.md` §ownership tables and `.github/CODEOWNERS` = stale; must be updated to §7 of this document (M1 action).
- `KAIROS_FINAL_ARCHITECTURE.md` / `KAIROS_ONE_PAGE_ARCHITECTURE.md` remain as inputs; where they conflict with §3, this document wins.
- [KAIROS_HANDOFF_5_MEMBERS.md](KAIROS_HANDOFF_5_MEMBERS.md) §4 remains the task detail per stream; where it conflicts with §9–§11 here, this document wins (its §8 decision list is superseded by §11 above).
- [docs/DEMO_SCRIPT.md](DEMO_SCRIPT.md) is M5's runbook and must be generated from §10; §10 is the specification, the script is the rehearsal.
- All planning documents + `docs/Perplexity/` are currently **untracked** — committing them is Wave 0 work, not optional.
- [KAIROS_PRODUCT_SPEC_PERPLEXITY.md](KAIROS_PRODUCT_SPEC_PERPLEXITY.md) §14 records the places where the source spec describes **our repo inaccurately** (it assumes quality tables, an embedding/trace schema, JSON lineage export, a deployed Hatchable app, and file/document/image ingestion all exist). Anyone planning from the spec alone will chase those five ghosts — read §14 before writing a task from the spec.
