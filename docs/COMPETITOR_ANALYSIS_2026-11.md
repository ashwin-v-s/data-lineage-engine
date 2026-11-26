# Competitive analysis: data catalogs, lineage and observability platforms

**Prepared:** 2026-11-26
**Scope:** compare Kairos against the platforms that sell the same job — find,
understand and trust data through metadata, lineage and governance — and record
which capabilities Kairos must provide.
**Method:** vendor documentation, product pages and independent comparisons
published up to 2026-11-26. Feature claims are the vendors' own; they were not
purchased, trialled or benchmarked. Where a capability is edition-gated the
analysis says so.

This is a product-gap document, not a claim that Kairos matches these products.
Kairos is a lineage-and-evidence engine with governance workflows; the
established platforms are broad catalogs with hundreds of connectors.

---

## 1. The market, grouped by the job it does

| Group | Products | Job they win |
| --- | --- | --- |
| Metadata / context platforms | DataHub (Core + Cloud), OpenMetadata, Atlan | Catalog everything, map lineage, serve context to people and AI agents |
| Governance suites | Collibra, Alation, Informatica EDC | Stewardship, policy, glossary and audit for regulated enterprises |
| Discovery-first catalogs | Select Star, Secoda, DataGalaxy, OvalEdge, data.world | Fast time-to-value discovery, documentation, popularity and trust signals |
| Observability / quality | Monte Carlo, Elementary, Soda, Great Expectations | Detect freshness, volume, schema and distribution failures |
| Lineage / OpenLineage | Marquez, OpenLineage, Amundsen | Open standard event lineage and impact analysis |

Kairos competes most directly with the first and fourth groups: a metadata graph
with bitemporal, evidence-backed lineage plus quality and incident workflows.

---

## 2. Capability matrix

Legend: **●** first-class, **◐** partial / edition-gated, **—** not a product
focus, **K** Kairos today.

| Capability | DataHub | OpenMetadata | Atlan | Alation | Collibra | Monte Carlo | Elementary | Select Star | Secoda | DataGalaxy | OvalEdge | K |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dataset lineage | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| Column-level lineage | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| Impact / blast radius | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| Bitemporal / as-of lineage | ◐ | ◐ | — | ◐ | ◐ | — | — | — | — | — | — | ● |
| Evidence states (observed/possible/refuted) | ◐ | ◐ | — | — | — | ◐ | — | — | — | — | — | ● |
| Connector breadth | ● 140–150+ | ● 130–150+ | ● 100+ | ● | ● | ● | ◐ dbt-first | ● | ● | ● | ● | ◐ 4 formats + PG |
| Business glossary | ● | ● | ● | ● | ● | — | ◐ | ◐ | ◐ | ● | ● | ● |
| Glossary term approval | ● | ● | ● | ● | ● | — | — | — | — | ◐ | ◐ | ● |
| Domains | ● | ● | ● | ● | ● | — | — | ◐ | ◐ | ● | ● | ● |
| Data products / contracts | ● | ● | ● | ◐ | ● | — | — | ◐ | ◐ | ◐ | ◐ | ◐ stored, not enforced |
| Ownership / stewardship | ● | ● | ● | ● | ● | ◐ | ◐ | ● | ● | ● | ● | ● |
| PII classification | ● | ● | ● | ● | ● | — | ◐ | ● | ● | ● | ● | ● |
| Classification propagation along lineage | ● | ● | ● | ◐ | ◐ | — | — | ◐ | ◐ | ◐ | ◐ | ● added 2026-11-26 |
| Asset certification / endorsement | ● Cloud | ● | ● | ● | ● | — | — | ◐ | ◐ | ● | ◐ | ● added 2026-11-26 |
| Asset discussions / comments | ● | ● | ● | ● | ● | ◐ | — | ◐ | ◐ | ◐ | ◐ | ● added 2026-11-26 |
| Usage / popularity ranking | ● | ● | ● | ● | ◐ | ◐ | ● | ● | ● | ● | ● | ◐ UI opens only |
| Quality assertions | ● | ● | ● | ● | ◐ | ● | ● | ◐ | ● | ◐ | ◐ | ◐ metadata-only |
| Row-level / custom SQL checks | ● | ● | ● | ● | ◐ | ● | ● | ◐ | ● | ◐ | ◐ | — |
| Anomaly detection | ● Cloud | ● | ● | ◐ | — | ● | ◐ | ◐ | ◐ | — | ◐ | — |
| Freshness SLAs + scheduling | ● | ● | ● | ● | ◐ | ● | ● | ◐ | ● | ◐ | ◐ | ● |
| Incidents + lifecycle | ● | ● | ● | ● | ◐ | ● | ◐ | ◐ | ◐ | — | ◐ | ● |
| Quality scorecard / trend | ● | ● | ● | ● | ● | ● | ● | ● | ● | ◐ | ◐ | ● added 2026-11-26 |
| Alerts: email / Slack / Teams | ● | ● | ● | ● | ● | ● | ● | ● | ● | ◐ | ◐ | ◐ email |
| Activity feed / announcements | ● | ● | ● | ● | ◐ | ◐ | — | ◐ | ◐ | ◐ | ◐ | — |
| RBAC / policies | ● | ● | ● | ● | ● | ◐ | ◐ | ● | ● | ● | ● | ◐ workspace roles |
| Audit log / versioning / rollback | ● | ● | ● | ● | ● | ◐ | — | ◐ | ◐ | ◐ | ◐ | ● |
| REST API / SDK / webhooks | ● | ● | ● | ● | ● | ● | ◐ | ● | ● | ● | ● | ● |
| MCP server / AI agent access | ● | ● | ● | ● | — | ◐ | ◐ | ◐ | ● | — | — | — |
| Natural-language / semantic search | ● | ● | ● | ● | ◐ | — | ◐ | ● | ● | ● | ● | ◐ blocked on embeddings |
| Saved searches / collections | ● | ● | ● | ● | ● | — | — | ● | ● | ● | ● | — |
| Access request workflow | ● Cloud | ● | ● | ● | ● | — | — | ◐ | ◐ | ◐ | ◐ | ◐ catalog-level |

### What the matrix says

1. **Kairos already leads on lineage epistemology.** Bitemporal intervals and
   four-state evidence (`OBSERVED`, `POSSIBLE`, `REFUTED_FOR_RUN`, `UNKNOWN`)
   are not matched as a first-class model by the catalogs, which mostly show
   lineage and quality as current-state facts.
2. **Kairos is behind on connectors.** This is the single largest gap and it is
   not closable by UI work: DataHub and OpenMetadata both advertise 130–150+
   sources; Kairos ingests metadata graphs, SQL, dbt manifests, CSV headers,
   file inventories, OpenLineage events and one PostgreSQL source.
3. **Kairos was behind on table-stakes trust surfaces.** Certification,
   discussion, popularity and a quality scorecard are present in nearly every
   competitor and were missing here. They are now implemented (section 4).
4. **Kairos is behind on executed data quality.** Assertions evaluate imported
   metadata only. Every observability competitor runs queries against the
   warehouse (freshness, volume, custom SQL, anomalies). Kairos is honest about
   this: custom SQL returns `501`, and a freshness assertion with no runtime
   evidence is `SKIPPED`, not `FAIL`.
5. **AI access is becoming table stakes.** DataHub, OpenMetadata, Atlan and
   Alation all ship an MCP server or agent surface. Kairos has none.

---

## 3. Competitor notes (what specifically they offer)

### DataHub (Core and Cloud)

- 140–150+ connectors, unified search, dbt metrics and semantic models, BI
  glossary ingestion, document ingestion, chunking and semantic embedding
  ([Core vs Cloud](https://docs.datahub.com/docs/managed-datahub/managed-datahub-overview)).
- Column-level lineage with impact analysis and metadata propagation
  (tag PII or a description once and it propagates downstream)
  ([lineage](https://docs.datahub.com/docs/features/feature-guides/lineage),
  [product page](https://datahub.com/products/data-lineage)).
- Assertions: freshness, volume, field, custom SQL; active warehouse queries or
  ingestion-driven evaluation; anomaly detection; incidents; subscriptions and
  email/Slack/Teams notifications
  ([Observe](https://docs.datahub.com/docs/features/feature-guides/observe),
  [assertions](https://docs.datahub.com/docs/managed-datahub/observe/assertions)).
- Business glossary, domains, ownership, RBAC/policy engine, audit logs.
- MCP server for agents: search, lineage traversal, schema inspection, SQL
  generation ([MCP](https://docs.datahub.com/docs/features/feature-guides/mcp)).
- Cloud 2.4 adds certification of assets and context documents
  ([release blog](https://datahub.com/blog/datahub-cloud-v2-4)).

### OpenMetadata

- 130–150+ connectors; catalog, quality and glossary in one metadata graph.
- Table and column lineage, lineage layers and search.
- Data quality: table/column tests, no-code and SQL tests, test suites, health
  dashboard, resolution workflow, alerts
  ([quality guide](https://docs.open-metadata.org/v2.0.x/how-to-guides/data-quality-observability/quality)).
- Glossary terms with typed relations, classifications/PII, domains, data
  products, data contracts, metrics, knowledge graph
  ([features](https://docs.open-metadata.org/v1.13.x/features),
  [1.13 announcement](https://blog.open-metadata.org/announcing-openmetadata-1-13-123d66609468)).
- Collaboration: activity feed, announcements, tasks, conversation threads,
  user mentions ([OECD summary](https://oecd.ai/en/catalogue/tools/openmetadata)).
- REST API, SDKs, events, webhooks and an MCP server
  ([API](https://docs.open-metadata.org/v2.0.x/api-reference)).

### Atlan

- 100+ certified connectors into an enterprise data graph; active metadata from
  query activity and dbt runs; 4–6 week deployment claim
  ([buyer's guide](https://atlan.com/data-catalog-tools)).
- Certification status, quality verdicts, failed-check summaries, READMEs,
  owners, tags, domains and glossary terms exposed as MCP tools
  ([MCP tools](https://docs.atlan.com/product/capabilities/atlan-ai/references/mcp-tools)).

### Alation

- ML-assisted search that surfaces popular assets; descriptions, terms,
  policies and documentation.
- Trust signals: lineage, tags, quality, trust flags, endorsements and comments
  ([product](https://www.alation.com/product-overview)).
- Usage-based ranking and stewardship coverage analytics; MCP and API access
  ([data catalog](https://www.alation.com/product/data-catalog)).

### Collibra

- Governance-first: stewardship workflows, policy management, business
  glossary, lineage and audit for regulated enterprises. Chosen when auditable
  stewardship process matters more than time-to-value
  ([comparison](https://www.dataarchitect.co/blog/data-catalog-tools)).

### Monte Carlo / Elementary / Soda / Great Expectations

- Monte Carlo: freshness, volume, schema and distribution anomaly monitoring,
  lineage-based impact and incident routing.
- Elementary: dbt-native observability and catalog with rolling 30-day table
  usage, AI catalog and AI governance that flags missing documentation, unowned
  assets and inconsistent tags
  ([catalog](https://docs.elementary-data.com/cloud/features/collaboration-and-communication/catalog)).
- Soda / Great Expectations: quality rules as code executed in pipelines, with
  results published to a dashboard
  ([governance tool comparison](https://www.ps3g.com/guides/data-governance-tools)).

### Select Star / Secoda / DataGalaxy / OvalEdge

- Discovery-first: automatic documentation, column lineage, PII flags,
  popularity and certification.
- OvalEdge explicitly ranks curation by popularity score, importance score and
  actual consumption, and suggests stewards
  ([product](https://ovaledge.com/product/data-catalog)).
- DataGalaxy surfaces definitions, owners, certification and trust indicators
  inside BI tools through a browser extension
  ([product](https://www.datagalaxy.com/en/data-catalog/)).

### Marquez / OpenLineage / Amundsen

- OpenLineage standardises run/job/dataset events with extensible facets;
  Marquez provides the reference lineage service. Amundsen is a discovery and
  lineage catalog with slower recent release velocity
  ([comparison](https://thedatagovernor.com/open-source-data-catalog-tools)).

---

## 4. Gaps closed in this change (2026-11-26)

These were missing entirely and are now implemented end to end (migration, API,
UI, tests, docs):

| Capability | Why it is table stakes | What was added |
| --- | --- | --- |
| **Asset certification** | DataHub Cloud, OpenMetadata, Atlan, Alation and DataGalaxy all expose a trust/endorsement badge and filter | `asset_certification` table, `PUT/DELETE /trust/assets/{id}/certification`, read-time `CERTIFIED`/`EXPIRING`/`EXPIRED` state, Trust Center register |
| **Asset discussions** | OpenMetadata conversations, Alation comments, DataHub/Atlan collaboration | `asset_discussion` threaded table, list/post/resolve endpoints, Trust Center discussion pane |
| **Usage / popularity** | Alation popularity ranking, Elementary 30-day usage, OvalEdge popularity score | `asset_engagement` aggregate counter (no user identity), recorded on asset open, top-5 ranking in Trust Center |
| **Quality scorecard and trend** | DataHub/OpenMetadata health dashboards, every observability vendor | `GET /quality/scorecard` and a shared builder: latest result per assertion, pass rate excluding SKIPPED/ERROR, daily trend, uncovered assets |
| **PII inheritance along lineage** | DataHub propagates tags/descriptions; catalogs derive classification downstream | `POST /governance/classifications/propagate` plus a pure lineage walk that only proposes unclassified downstream columns from `PII_SOURCE`/inherited seeds, records the exact edge ids, and marks the result `POSSIBLE` |

The PII propagation change also removes a documented placeholder: the PII screen
previously disabled `PII_INHERITED` because no derivation pipeline existed.

---

## 5. Remaining gaps — capabilities Kairos must provide

Ordered by competitive risk. Each item states the honest blocker.

### P0 — blocks enterprise comparison

1. **Connector breadth.** 4 import formats + one PostgreSQL source vs 130–150+.
   Required: Snowflake, BigQuery, Redshift, Databricks, dbt Cloud, Airflow,
   Looker, Tableau, Power BI, Kafka, S3, Glue, Synapse, Fabric. The connector
   contract already exists (`source_connection`, capability model); each source
   needs an adapter, credential handling and tests.
2. **Executed data quality.** Metadata-only assertions cannot detect a volume
   drop or a NULL spike. Required: a reviewed, parameterised, read-only query
   runner with `data:preview` permission, plus volume/row-count, column-value,
   custom-SQL and anomaly assertion types. Until then custom SQL must stay 501.
3. **Semantic search.** Hybrid search is coded but unembedded (no
   `OPENAI_API_KEY`; 103 datasets, 0 embeddings). Required: an embedding
   provider decision, backfill, and a re-embedding job on metadata change.
4. **MCP server / agent access.** DataHub, OpenMetadata, Atlan and Alation ship
   one. Required: a read-only MCP tool surface over search, asset detail,
   lineage, impact and quality, authenticated with the existing API keys.

### P1 — expected in a mid-market evaluation

5. **Query-log usage analytics.** We record UI opens, not warehouse query
   frequency. Required: ingest query history from supported warehouses, rank by
   executions and distinct users.
6. **Data contract enforcement.** Contracts and clause links are stored, but
   nothing evaluates them. Required: map clauses to assertions, compute
   `MONITOR`/`WARN`/`BLOCK` outcomes, and expose a contract health verdict.
7. **Slack / Teams notifications.** Email and in-app only. Required: workspace
   notification channels with signed delivery and per-event routing.
8. **Activity feed and announcements.** No workspace-wide change feed or
   scheduled announcement. Required: a read model over `audit_event` plus
   announcement records.
9. **Saved searches and collections.** Users can star assets but not save a
   query or curate a shared collection. Required: saved-search and
   collection/collection-item tables with workspace sharing.
10. **Metadata propagation for descriptions and tags.** PII now propagates;
    descriptions and tags do not. Required: explicit, opt-in propagation with
    provenance and rollback.

### P2 — polish and reach

11. Manual lineage editing with audit (no-code edge creation).
12. Asset README / rich documentation beyond a 500-character description.
13. Access-request approval that grants actual source access (today stewardship
    records a decision only).
14. Browser-extension / BI-tool context surface.
15. Column-level quality results and a per-column scorecard.
16. Data profiling statistics (row count, null ratio, distinct count) from
    imported profiles.

---

## 6. Verification performed for the shipped gaps

- `python -m pytest -q` → **886 passed, 83 skipped** (24 new tests).
- `python -m ruff check` over every changed Python file → clean.
- `python scripts/check_openapi_drift.py` → unchanged after regeneration,
  **134 paths** (127 before this change).
- `python scripts/check_ui_claims.py` → every Trust Center request maps to a
  documented endpoint.
- `python scripts/db/check_migrations.py` → numbering 0001–0019, verify-list
  coverage and RLS declarations pass.
- `cd frontend && npm run build` → succeeds.

### Live database verification

Migration `0019_trust_collaboration.sql` **was applied** to the shared Supabase
project on 2026-11-26:

- `python scripts/db/verify_applied.py` → PASS, 51 tracked tables present,
  including `asset_certification`, `asset_discussion`, `asset_engagement`.
- `python scripts/db/verify_rls.py --table asset_certification asset_discussion asset_engagement`
  → 3/3 PASS, connecting role cannot bypass RLS.
- API smoke against the live database: overview 200, certify 200, certification
  list 200, comment 201, discussion 200, resolve 200, scorecard 200, propagation
  dry-run 200, propagation write 1 created then 0 on a second run, revoke 200,
  recorded open incremented engagement `None → 1`. Temporary rows were removed
  and the counter restored.

Not verified: the hosted deployment does not include this code yet, and the new
Trust Center has not been rendered in a browser. See `docs/TRUST_CENTER.md` §6.

---

## 7. Sources

- DataHub: [Core vs Cloud](https://docs.datahub.com/docs/managed-datahub/managed-datahub-overview),
  [lineage](https://docs.datahub.com/docs/features/feature-guides/lineage),
  [observe](https://docs.datahub.com/docs/features/feature-guides/observe),
  [assertions](https://docs.datahub.com/docs/managed-datahub/observe/assertions),
  [MCP](https://docs.datahub.com/docs/features/feature-guides/mcp),
  [Cloud 2.4](https://datahub.com/blog/datahub-cloud-v2-4),
  [GitHub](https://github.com/datahub-project/datahub)
- OpenMetadata: [features](https://docs.open-metadata.org/v1.13.x/features),
  [quality](https://docs.open-metadata.org/v2.0.x/how-to-guides/data-quality-observability/quality),
  [API](https://docs.open-metadata.org/v2.0.x/api-reference),
  [1.13](https://blog.open-metadata.org/announcing-openmetadata-1-13-123d66609468),
  [GitHub](https://github.com/open-metadata/OpenMetadata)
- Atlan: [buyer's guide](https://atlan.com/data-catalog-tools),
  [MCP tools](https://docs.atlan.com/product/capabilities/atlan-ai/references/mcp-tools)
- Alation: [product overview](https://www.alation.com/product-overview),
  [data catalog](https://www.alation.com/product/data-catalog)
- Collibra / market comparisons:
  [DataArchitect](https://www.dataarchitect.co/blog/data-catalog-tools),
  [Toolverly](https://toolverly.com/blog/data-catalog-platforms),
  [Domo](https://www.domo.com/learn/article/best-data-catalog-tools)
- Observability: [Elementary catalog](https://docs.elementary-data.com/cloud/features/collaboration-and-communication/catalog),
  [governance tool comparison](https://www.ps3g.com/guides/data-governance-tools)
- Discovery-first: [OvalEdge](https://ovaledge.com/product/data-catalog),
  [DataGalaxy](https://www.datagalaxy.com/en/data-catalog/),
  [fastero](https://fastero.com/blog/best-data-catalog-tools-for-data-teams-2026)
- Open source lineage: [the data governor comparison](https://thedatagovernor.com/open-source-data-catalog-tools)
