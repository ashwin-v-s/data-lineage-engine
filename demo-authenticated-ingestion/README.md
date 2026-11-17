# Enterprise Authenticated Demo Ingestion Folder (Demo 3)

**Location:** `demo-authenticated-ingestion/`  
**Purpose:** Authenticated, multi-tier enterprise lineage ingestion for Kairos Demo 3 (`/ingestion.html`).  
**Contract Version:** `kairos.ingest.v1`  
**Security Scope:** RLS-isolated to authenticated workspace (`current_setting('kairos.workspace_id')`). Zero synthetic fallback. Zero bypassRLS.

---

## 1. Enterprise Architecture & Dependency Lineage

This demo folder models a real-world enterprise **Financial & Customer Revenue Intelligence Pipeline**, structured across 4 distinct architectural layers:

```
[ Tier 1: Ingestion / Raw Source Layer ]
  raw_enterprise.customers (PII source) ──────┐
  raw_enterprise.orders_feed (Checkout log) ──┼──┐
  raw_enterprise.payments_feed (Gateway log) ─┘  │
                                                 │
[ Tier 2: Staging & Conformation Layer ]         │
  staging.stg_customer_360 (Masked PII) ◀───────┘
  staging.stg_orders_enriched (Settled Orders) ◀─┘
       │                                │
       ▼                                ▼
[ Tier 3: Certified Analytics Marts Layer ]
  analytics.fct_daily_revenue (SOX In-Scope Mart)
  analytics.dim_customer_segments (Customer Lifetime Value)
       │                                │
       ▼                                ▼
[ Tier 4: Enterprise Consumption Layer ]
  executive.daily_revenue_kpi (CFO Board Dashboard)
  reporting.customer_retention_portal (Customer Success Portal)
```

### Dependency Graph Highlights
1. **Fan-In / Transformation:** `orders_feed` and `payments_feed` join into `stg_orders_enriched`.
2. **PII Masking:** `customers.email` is pseudonymized into `stg_customer_360.masked_email` (HMAC-SHA256).
3. **Conformed Aggregation:** `stg_orders_enriched` and `stg_customer_360` feed the certified financial mart `analytics.fct_daily_revenue`.
4. **Data Product & Board Consumption:** `analytics.fct_daily_revenue` feeds `executive.daily_revenue_kpi` under the **Executive Revenue Intelligence Product**.

---

## 2. Included Demo Artifacts

| File Name | Format Type | Extraction Target | Examiner Checkpoint |
|---|---|---|---|
| `enterprise_metadata_graph.json` | `metadata_graph` | 9 assets, 9 explicit edges, 26 columns | Rich column lineage, PII classifications, owners, and governance metadata |
| `enterprise_lineage_pipeline.sql` | `sql_file` | 8 assets, 6 SQL candidate edges | Pure SQLGlot AST parsing (`CREATE TABLE ... AS SELECT` + `INSERT INTO ... SELECT`) |
| `dbt_production_manifest.json` | `dbt_manifest` | 8 assets (4 models, 3 sources, 1 exposure), 7 edges | dbt Core v1.8 manifest v10 schema with `depends_on.nodes` |
| `customer_transactions_schema.csv` | `csv_headers` | 1 asset, 10 column schemas | Header-only schema extractor (zero data rows ingested) |
| `enterprise_inventory.json` | `file_inventory` | 5 file assets, directory containment | File sizes and SHA-256 digests without synthetic lineage claims |

---

## 3. Governance & Enterprise Metadata Bindings

When ingested, these assets immediately connect to Kairos's governance registries:

### A. Business Glossary Terms
- **Gross Merchandise Value (GMV):** Bound to `analytics.fct_daily_revenue.gross_merchandise_value` and `staging.stg_orders_enriched.gross_order_value`.
- **Net Recognized Revenue:** Bound to `analytics.fct_daily_revenue.net_recognized_revenue` (ASC 606 / IFRS 15 GAAP).
- **Customer Lifetime Value (LTV):** Bound to `analytics.dim_customer_segments.lifetime_value_usd`.
- **Personally Identifiable Information (PII):** Bound to `raw_enterprise.customers.email`, `full_name`, and `phone_number`.

### B. Business Domains
- **Finance & Revenue:** Owns `orders_feed`, `payments_feed`, `stg_orders_enriched`, `fct_daily_revenue`, and `daily_revenue_kpi`.
- **Customer Management:** Owns `customers`, `stg_customer_360`, `dim_customer_segments`, and `customer_retention_portal`.

### C. Data Products & Contracts
- **Executive Revenue Intelligence Product (Domain: Finance & Revenue):**
  - Primary Output: `analytics.fct_daily_revenue` and `executive.daily_revenue_kpi`
  - SLA: 24-hour daily freshness guarantee with SOX Section 404 audit logging.
- **Customer 360 Intelligence Mart (Domain: Customer Management):**
  - Primary Output: `staging.stg_customer_360` and `analytics.dim_customer_segments`
  - SLA: 7-day rolling refresh guarantee with automated PII masking validation.

---

## 4. Live Walkthrough Instructions for Presenter

1. Open Kairos in the browser and sign in with your Supabase account.
2. Navigate to **"Connect / import metadata"** (`/ingestion.html`).
3. Under **"Scan a local folder"**, click **"Choose a folder"**.
4. In the browser's directory picker, select this folder (`demo-authenticated-ingestion`).
5. Observe the client-side scan:
   - Status confirms files were scanned locally with SHA-256 digests.
   - Zero network requests were made during the local scan.
6. Select `enterprise_metadata_graph.json` and click **"Preview selected file"**.
   - Show the JSON structure, assets, and dependency relationships in the local preview.
7. Click **"Ingest selected file"**.
   - Two-phase preview & commit saves the 9 assets and 9 relationships atomically to your PostgreSQL workspace.
8. Click **"Import folder inventory"** to demonstrate inventory capture without synthetic lineage.
9. Click **"← Back to Kairos dashboard"**:
   - Open **Lineage Explorer** (`/lineage`): Show the 4-tier directed acyclic graph.
   - Click an edge: Open the **Edge Inspector** to show the exact evidence provenance.
   - Open **Catalog & schemas** (`/assets`): Inspect column schemas, data types, and PII badges.
   - Open **Glossary & PII** (`/glossary`, `/pii`): Show business definitions and evidence-backed classifications.
   - Open **Domains** (`/domains`) & **Data Products** (`/products`): Show data product bindings and SLA contracts.
