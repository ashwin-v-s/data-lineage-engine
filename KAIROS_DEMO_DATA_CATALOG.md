# KAIROS — Demo Data Catalog

Prepared 2026-11-21. Every record below was written through the application's
own authenticated HTTP pipeline (or a documented application route) into the
shared Supabase Postgres project, workspace
`d91f7d80-dc3e-401e-9df4-e7670e4d3ba1` (**Personal workspace**, owner
`pranavsamal43@gmail.com`).

> **Data origin — read this before presenting.** All assets, columns, lineage
> edges, governance records and quality results in this workspace are
> **synthetic demonstration data**. They model a plausible enterprise revenue
> analytics stack; they are not customer data, not externally authenticated
> metadata, and not the output of a real dbt run. Nothing here was scraped,
> purchased, or imported from an organisation. The fixtures are committed in
> `demo-authenticated-ingestion/` and are traceable to the exact file that
> produced each row.

---

## 1. The business story

A mid-size e-commerce company sells through its own storefront. Orders and
payment authorisations land in a raw zone, are conformed in a staging layer,
modelled into an analytics mart, and consumed by an executive dashboard and a
customer-success portal. Two governance concerns drive the rest of the demo:

1. **Revenue is regulated.** The daily revenue mart is SOX in scope, so its
   definition (GMV, net recognised revenue) must be governed, versioned and
   evidenced.
2. **Customer identity is PII.** The raw customer table carries emails that are
   hashed before any analytics consumer sees them.

### Logical architecture (as ingested)

```
Tier 1  Raw sources
  raw_enterprise.customers          (6 cols, PII source)
  raw_enterprise.orders_feed        (6 cols)
  raw_enterprise.payments_feed      (6 cols)

Tier 2  Staging / conformance
  staging.stg_orders_enriched       (7 cols)  <- orders_feed + payments_feed
  staging.stg_customer_360          (5 cols)  <- customers (email pseudonymised)

Tier 3  Analytics marts
  analytics.fct_daily_revenue       (6 cols)  <- stg_orders_enriched + stg_customer_360
  analytics.dim_customer_segments   (5 cols)  <- stg_orders_enriched + stg_customer_360

Tier 4  Consumption
  executive.daily_revenue_kpi       (dashboard) <- fct_daily_revenue
  reporting.customer_retention_portal (dashboard) <- dim_customer_segments
```

## 2. Fixture → resulting records

| Fixture (committed) | Adapter | Preview result | `import_id` |
| --- | --- | --- | --- |
| `enterprise_metadata_graph.json` | `metadata_graph` | 9 assets, 9 relationships, 41 columns | `cc782dcb-2209-42d3-8b78-798d50881844` |
| `enterprise_lineage_pipeline.sql` | `sql_file` (`sqlglot`) | 8 assets, 6 relationships, 0 columns | `2ac950e6-c0dc-4d74-b830-a5b512a7aca4` |
| `dbt_production_manifest.json` | `dbt_manifest` | 8 assets, 8 relationships | `b33f21f5-836d-4fb8-8bd4-42fb38730a5d` |
| `customer_transactions_schema.csv` | `csv_headers` | 1 asset, 10 columns | `e958f1a0-9811-4de0-a956-fcb9f5d8d522` |
| `enterprise_inventory.json` | `file_inventory` | 4 file assets | `477e8d47-b54f-4575-b841-14192572bef1` |

Idempotency keys follow `kairo-e2e-2026-11-21-<kind>`. Replaying the metadata
graph with the same key returned `replayed: true` and the same `import_id`, so
the demo can be re-run safely.

**Catalog readback after all five commits (before migration 0018):** 30 assets,
23 lineage edges, 23 evidence rows, 0 runs (`GET /api/v1/catalog?limit=200`,
HTTP 200). Four demo pipeline runs were added later (see §5a).

> **Resolved 2026-11-23 (BUG-01):** migration 0018 reconciles the adapters'
> variants by logical identity, and the demo workspace was merged from 30 rows
> to **17 active assets**. Tables, views, models and sources of one dataset are
> a single row; a table, its dashboard and its exposure legitimately remain
> three rows because they are different kinds. Column records, edges, temporal
> versions, PII, quality, freshness, terms and product links were moved to the
> surviving row, not dropped. Current production readback: **17 active assets,
> 42 edges (23 dataset + 19 column), 42 evidence rows, 4 pipeline runs, 9 raw events, 1 quality check**.

## 3. Assets and columns (from the metadata graph)

| Asset | Namespace | Type | Columns |
| --- | --- | --- | --- |
| `customers` | `raw_enterprise` | table | customer_id, email, full_name, signup_date, country_code, marketing_opt_in |
| `orders_feed` | `raw_enterprise` | table | order_id, customer_id, order_total, currency, order_status, ordered_at |
| `payments_feed` | `raw_enterprise` | table | payment_id, order_id, amount, payment_method, payment_status, captured_at |
| `stg_orders_enriched` | `staging` | view | order_id, customer_id, gross_order_value, net_order_value, currency, payment_status, order_date |
| `stg_customer_360` | `staging` | view | customer_id, masked_email, country_code, signup_date, lifetime_segment |
| `fct_daily_revenue` | `analytics` | model | revenue_date, gross_merchandise_value, net_recognized_revenue, order_count, refund_amount, currency |
| `dim_customer_segments` | `analytics` | model | customer_id, value_tier, lifetime_value, churn_risk_band, last_order_date |
| `daily_revenue_kpi` | `executive` | dashboard | — |
| `customer_retention_portal` | `reporting` | dashboard | — |

All **17 active assets** now carry a description, named owner, steward and
tags. Owners are the real project users **Pranav Samal**, **Jatin Shende** and
**Gauree Hatkar**; only the active workspace member (Pranav) is stored as
`owner_id`, so the other names are descriptive assignments rather than silent
access grants. See §3a for the complete mapping.

### 3a. Ownership and PII coverage

`scripts/db/seed_demo_ownership_pii.py` updates all 17 assets and replaces the
demo PII rows with 16 curated classifications:

| Owner | Assets |
| --- | --- |
| Pranav Samal (Customer Data Steward) | `customers`, `customer_retention_portal`, `stg_customer_360`, `enterprise_metadata_graph.json` |
| Jatin Shende (Revenue Data Steward) | `customer_transactions_schema`, its CSV, `orders_feed`, `payments_feed`, `stg_orders_enriched`, `dbt_production_manifest.json`, `enterprise_lineage_pipeline.sql` |
| Gauree Hatkar (Finance Analytics Steward) | `fct_daily_revenue`, `dim_customer_segments`, and the three `daily_revenue_kpi` kinds |

PII rows:

| Asset | Column | Classification | Evidence |
| --- | --- | --- | --- |
| `customers` | `email`, `phone_number`, `full_name`, `customer_id` | PII_SOURCE | OBSERVED |
| `payments_feed` | `payment_id`, `payment_method` | PII_SOURCE | OBSERVED |
| `stg_customer_360` | `email` / `masked_email` / `customer_id` | PII_SOURCE / PII_MASKED / PII_INHERITED | OBSERVED / OBSERVED / POSSIBLE |
| `customer_transactions_schema` | `customer_id` / `risk_score` | PII_INHERITED / PII_POTENTIAL | POSSIBLE / POSSIBLE |
| `orders_feed`, `stg_orders_enriched`, `dim_customer_segments` | `customer_id` | PII_INHERITED | POSSIBLE |
| `fct_daily_revenue`, `daily_revenue_kpi` (TABLE) | whole dataset | PII_CLEARED | OBSERVED |

Readback: `/api/v1/catalog` exposes `owner_name`, `steward_name`, `tags` and
`is_pii`/`sensitivity_classification`; `/governance/classifications` joins the
asset and column names and returns all 16 rows. Seven assets carry a PII badge;
`fct_daily_revenue` and the KPI table are explicitly reviewed as not PII.

## 4. Lineage edges (declared, `dbt_model_ref` / `dashboard_upstream_dataset`)

```
orders_feed    ─┐
payments_feed  ─┴─► stg_orders_enriched ─┬─► fct_daily_revenue      ─► daily_revenue_kpi
customers      ────► stg_customer_360   ──┴─► dim_customer_segments  ─► customer_retention_portal
```

Nine edges in the metadata graph; six equivalent edges are re-derived by the
SQLGlot adapter from `CREATE TABLE … AS SELECT` / `INSERT … SELECT` in
`enterprise_lineage_pipeline.sql`; eight more come from the dbt manifest's
`depends_on.nodes`. Each persisted edge carries:

- `granularity = DATASET`
- `operator_fingerprint` (`declared_dependency` for static imports)
- an `evidence` row of type `STATIC_DEPENDENCY`, `parser_status = SUPPORTED`,
  with `diagnostics.edge_type`, `diagnostics.provenance` (the source file) and
  `classification = DECLARED_METADATA`.

Evidence ids follow `kairos-import:<import_id>` so every claim is traceable to a
committed file.

### Verified query results

| Query | Result |
| --- | --- |
| `GET /api/v1/assets/{fct_daily_revenue MODEL}/lineage?depth=4` | 8 nodes, 8 edges |
| `GET /api/v1/assets/{customers SOURCE}/downstream-impact?depth=4` | `total_affected: 4` across depth levels |
| `GET /api/v1/lineage/edges/5a9abd50-…/evidence` | evidence rows returned |
| `GET /api/v1/evidence-at-time?valid_as_of=now&recorded_as_of=now` | `included: 8, undated_valid_time: 34` — the dbt dependencies carry the manifest's `generated_at`; SQL/CSV/file evidence stays undated |
| `GET /api/v1/column-lineage?valid_as_of=now` | `total: 19` after the SQL projection backfill (was 0) |

## 5. Governance records created in this workspace

| Kind | Record | Id |
| --- | --- | --- |
| Domain | Finance & Revenue — "Certified revenue, margin and customer-value reporting domain." | `f480e033-8b02-40ac-bd91-94ff545632fd` |
| Glossary term | Gross Merchandise Value (GMV) — "Total value of settled orders before cancellations, refunds and taxes." | `fce04495-a252-4ec0-ae49-85c0702dbf3b` (status APPROVED) |
| Term ↔ asset | GMV linked to `fct_daily_revenue` | `created: true` |
| Data product | Executive Revenue Intelligence (ACTIVE) — assets: `daily_revenue_kpi` (DASHBOARD), `fct_daily_revenue` (TABLE) | `f33bea44-db2f-459c-8db2-8f42eac7e714` |
| Quality assertion | "Revenue mart schema contract", type `schema`, severity HIGH, schedule manual | `480a9715-3dbc-4b4d-be47-703dde52a6bd` |
| Quality result | PASS, checked 1, failed 0, evaluated 2026-11-21T11:36Z | `54a0cd91-49b3-4ec6-a532-6169b28e3e8b` |
| Freshness SLA | `fct_daily_revenue`: warn 48 min, error 60 min, stale 120 min, signal `manual`, schedule `manual` | `e0f15710-ed4a-4947-8c2f-9e486d3854ea` |

Readbacks: `/governance/terms` 4 rows, `/governance/domains` 3 rows,
`/governance/products` 3 rows, `/quality/assertions` 1 row,
`/governance/slas` 1 row — all HTTP 200.

### Not created (and why)

| Item | Reason |
| --- | --- |
| PII classification on `customers.email` | **Created** — after the BUG-01 merge, `customers` is one asset with 6 columns and the classification resolves to it. |
| Data contract version | Available, but a contract needs an assertion id and clause JSON; prepared steps are in the demo guide. |
| Incidents / notifications | No scheduler or runtime freshness signal exists in this deployment, so nothing legitimately triggers them. |
| Sync jobs, source connections | Requires a reachable PostgreSQL source and `KAIROS_TOKEN_ENCRYPTION_KEY`. |
| Column-level lineage | **Available** — 19 SQL projection mappings backfilled; no longer a gap. |

### 5a. Demo pipeline runs

`scripts/db/seed_demo_runs.py` adds four `job`/`execution_run` records and one
immutable source event per run, all idempotent by workspace + run id:

| Run | Pipeline | Stored status | Started → completed | Environment | Assets | Events |
| --- | --- | --- | --- | --- | ---: | ---: |
| `demo-run-legacy-export-20261123-0315` | Legacy warehouse export | failed → FAILED | 2026-11-23T03:15Z → 03:16:05Z | production | 0 | 1 |
| `demo-run-revenue-quality-20261123-0300` | Revenue quality gate | warning → WARNING | 2026-11-23T03:00Z → 03:02:15Z | staging | 0 | 1 |
| `demo-run-customer360-20261123-0230` | Customer 360 refresh | completed → SUCCESS | 2026-11-23T02:30Z → 02:41:10Z | production | 0 | 1 |
| `demo-run-revenue-20261123-0200` | Revenue daily pipeline | completed → SUCCESS | 2026-11-23T02:00Z → 02:08:42Z | production | 0 | 1 |

Asset counts are deliberately zero: there is no normalized per-run evidence
linking these jobs to datasets, and the run page must not claim an observed
asset. The stored `raw_event` rows are counted as source events. Job
`namespace` is the environment shown in the UI. Reproduction:

```bash
python scripts/db/seed_demo_runs.py \
  --workspace d91f7d80-dc3e-401e-9df4-e7670e4d3ba1
```

### 5b. Integration credentials

Created from the signed-in **Workspace administration** page on 2026-11-23:

| Record | Value |
| --- | --- |
| API key | `ci-readonly-catalog`, prefix `kairos_sk_2bI-S26ksl`, scope `read`, last used 2026-11-23T22:09Z |
| API key secret | `.demo-sources/ci-readonly-catalog.key` (git-ignored local file; never documented) |
| Webhook | `https://httpbin.org/post`, description "Demo echo receiver - replace with your HTTPS endpoint", all 7 events, active |
| Webhook signing secret | `.demo-sources/webhook-signing-secret.txt` (git-ignored local file) |
| Delivery | `test.ping`, HTTP 200, 26 ms, `X-Kairos-Signature` echoed by the receiver |

The API key was verified against production: catalog read **200** with 17
assets, `/api-keys/self` **200**, `/members` **403**, ingest preview **403**.
The webhook delivery is stored in `workspace_webhook_delivery` and surfaced in
the page's History panel.

## 6. Historical / temporal data

The dbt manifest declares `metadata.generated_at = 2026-11-17T21:00:00Z`.
The adapter forwards that source timestamp, and
`scripts/db/backfill_demo_temporal.py` applied it to the eight already-imported
dbt dependencies, so they now have `effective_time_status='KNOWN'` and a valid
interval starting at the manifest generation time. They were recorded at import
time (`2026-11-21T11:32:59Z`).

The bitemporal query therefore returns **8 dated rows** at "now" and reports
the other **34** SQL/CSV/file evidence rows as undated rather than inventing a
time for them. Demo states:

- today → 8 rows;
- valid time `2026-11-16` → 0 rows (manifest did not exist);
- valid time `2026-11-18` → 8 rows;
- recorded time before `2026-11-21T11:32Z` → 0 rows (not learned yet).

The backfill is idempotent; a second run updates 0 rows. Future dbt imports get
the same timestamp directly from the adapter.

## 7. Reproducing this dataset

```bash
# 0. Demo pipeline-run records (idempotent)
python scripts/db/seed_demo_runs.py \
  --workspace d91f7d80-dc3e-401e-9df4-e7670e4d3ba1

# 1. Real session (test account; credentials live in scripts/get_test_token.py)
python scripts/get_test_token.py

# 2. Preview + commit each fixture through the deployed API
#    POST /api/v1/ingest/preview   {kind, filename, content}
#    POST /api/v1/ingest/commit    {kind, filename, content, idempotency_key}
#    Header: Authorization: Bearer <token>
#            X-Kairos-Workspace-ID: d91f7d80-dc3e-401e-9df4-e7670e4d3ba1

# 3. Governance objects
#    POST /api/v1/governance/domains|terms|products|classifications|slas
#    POST /api/v1/quality/assertions  then  /{id}/evaluate
```

The exact scripts used are in the (git-ignored) `.demo-sources/` folder:
`e2e.py` (ingestion), `e2e2.py` (lineage/evidence/search),
`e2e3.py` (governance/quality/SLA), `inspect.py` / `inspect2.py` / `qa.py`
(database verification), `browser.mjs` / `.demo-check2.mjs` /
`.demo-sweep.mjs` (browser verification).

## 8. Cleanup

To remove only what this preparation created, delete by identifier — never by
name pattern:

```sql
-- workspace d91f7d80…, created 2026-11-21
DELETE FROM quality_result      WHERE assertion_id = '480a9715-3dbc-4b4d-be47-703dde52a6bd';
DELETE FROM quality_assertion   WHERE id           = '480a9715-3dbc-4b4d-be47-703dde52a6bd';
DELETE FROM freshness_sla       WHERE id           = 'e0f15710-ed4a-4947-8c2f-9e486d3854ea';
DELETE FROM product_asset       WHERE product_id   = 'f33bea44-db2f-459c-8db2-8f42eac7e714';
DELETE FROM data_product        WHERE id           = 'f33bea44-db2f-459c-8db2-8f42eac7e714';
DELETE FROM term_assignment     WHERE term_id      = 'fce04495-a252-4ec0-ae49-85c0702dbf3b';
DELETE FROM glossary_term       WHERE id           = 'fce04495-a252-4ec0-ae49-85c0702dbf3b';
DELETE FROM domain              WHERE id           = 'f480e033-8b02-40ac-bd91-94ff545632fd';
DELETE FROM import_run          WHERE id IN ('cc782dcb-…','2ac950e6-…','b33f21f5-…','e958f1a0-…','477e8d47-…');
-- then remove the workspace's datasets/edges/evidence by workspace_id if desired
```

Deleting is **not** part of the demo flow and must be authorised separately.
