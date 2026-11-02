# Handout M3 — Ashwin (`ashwin-v-s`) · Catalog, Lineage & Evidence

**Stream:** M3 — the differentiator. Every conclusion on screen traces to a stored evidence row and says *why* it is believed.
**You own:** `backend/app/api/routes/{assets,lineage,dependency,search,metadata}.py`, `backend/app/identity/`, `backend/app/temporal/`, `backend/app/repositories/`, evidence + `edge_temporal_version` queries, the catalog/lineage/evidence UI slice, search (incl. `pgvector`), exports.
**Read first:** [KAIROS_ARCHITECTURE_V2.md](../KAIROS_ARCHITECTURE_V2.md) §3 C1/C2/C4, §4 L2 + invariants 9–11, §5.2–§5.3, §5.7 · **[KAIROS_PRODUCT_SPEC_PERPLEXITY.md](../KAIROS_PRODUCT_SPEC_PERPLEXITY.md) §3 Catalog, §4 Asset detail, §5 Lineage, §10 Evidence explorer (the literal component lists you must satisfy)** · [TEAM_GUIDE.md](../TEAM_GUIDE.md) §11 · [DATA_MODEL.md](../DATA_MODEL.md) · [PROJECT_STATUS_2026-11-02.md](../PROJECT_STATUS_2026-11-02.md)

---

## 1. What you have already shipped (evidence)

- Repo owner + the entire foundation: `c802ef4`/`2718f36` "Initial foundation: contracts, engine, baselines, metrics, CI" — `contracts/`, `research/reasoning`, `research/baselines`, `research/metrics`, CI, and the import-boundary guard are yours.
- PR #2 `M3: Complete Week 1 deliverables` (`352a399`): `backend/migrations/0001_core.sql` (identity, `raw_event` immutability trigger, `evidence`, `lineage_edge`, **`edge_temporal_version` bitemporal**, `execution_state`, `projection_outbox`), plus `tests/test_{temporal_oracle,identity,metrics,leakage,engine_rules,baselines}.py`. You authored `0001` itself; `0002`/`0003` were added later by Jatin, so part of the storage layer's audit trail sits outside your commits. The bitemporal storage layer — the hardest part of the research pack — is implemented and still green.
- **Since 2026-09-24 you have no commits and no PR.** Your stream is the one that has drifted furthest from the current product.

## 2. What is **not** done — your gaps

| # | Gap | Proof |
|---|---|---|
| G1 | **No evidence explorer and no edge inspector.** The Perplexity spec (§5, §10) makes these the differentiator: edge click → relationship type, state, evidence source, evidence id, coverage, evidence strength, valid/recorded time, explanation; plus raw vs normalized viewer, provenance chain (raw event → parser → normalized → canonical asset), conflict view, temporal view. None of it exists in `frontend/`. | absent from tree |
| G2 | **No time travel.** `edge_temporal_version` is populated by your own migration but no API route or UI queries `as_of` / `recorded_as_of`. Architecture v2 §7 M3 requires it, with honest disclosure of undated rows (D-14). | grep: only `docs/DATA_MODEL.md` |
| G3 | **Four-state results are not surfaced.** `execution_state` exists; nothing renders `OBSERVED/POSSIBLE/REFUTED_FOR_RUN/UNKNOWN` on the graph. M5's audit (§3 of `M5_FRONTEND_AUDIT_AND_ARCHITECTURE.md`) required the legend and the verbatim Section-19 wordings — still not done. | UI |
| G4 | **Search is keyword `LIKE` only.** No `pgvector` embeddings, no hybrid ranking, no permission-filtered retrieval — and the Perplexity P0 rule "RAG/search must not return metadata the caller cannot read" is untested. | `routes/search.py` |
| G5 | **Catalog is thin**: no facet filter rail (type/source/domain/owner/PII/freshness/quality/certification), no saved views, no pagination, no preview drawer, no honest empty states. | UI |
| G6 | **Capability registry is not consumed.** `capabilities.py` (1 route, uncommitted) exists but no UI gates tabs from it, which is exactly the "never show a tab as functional when the capability does not exist" rule. | untracked, unconsumed |
| G7 | **Canonical identity is incomplete:** `backend/app/identity/canonical_ids.py:254` raises `NotImplementedError` while §5.7 declares identity LOCKED; rename/schema-change handling unproven. | code |
| G8 | **Dead React tree in `main`.** PR #12 restored `frontend/src/App.tsx`, `components/Inspector/DetailsTab.tsx`, `components/LineageNode/LineageNode.tsx` — the merge itself records that nothing imports them. A decision (adopt or delete) is outstanding, and the D-17 spike recommendation (React Flow + Dagre) is still not in `frontend/package.json`. | PR #12 body |
| G9 | **Lineage screen is missing 6 of the 15 spec components:** node inspector, impact analysis, root-cause view, depth control (1/2/3/5/custom), **search-within-graph**, **mini-map**, and PNG/SVG/JSON export; column-level toggle exists only as data, not as a UI toggle. | checklist §5 vs `frontend/app.js` |
| G10 | **Asset detail is missing two spec tabs entirely** — Activity (metadata edits, ownership/tag/lineage changes, comments; the backing `asset_version` table already exists, M1 owns its write path) and Relationships (glossary terms, data products, dashboards, ML models, contracts). Overview/Schema/Lineage are also not gated by the registry. | checklist §4 |
| G11 | `docs/DATA_MODEL.md` §Open Design Decisions: D-13 (route identifiers) and D-14 (unknown effective time) are still undecided, and "NOT Indexed Yet: full-text search on diagnostics, JSONB fields". | docs |

## 2b. Executed today — defects that are **yours**, with the command that proved them

Evidence in [VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) §1, §3, §5.

| # | What I ran | What happened | Consequence |
|---|---|---|---|
| S1 | `pytest --cov=backend.app` | `lineage.py` **15 %** (140 of 165 statements missed), `search.py` **18 %**, `metadata.py` **16 %**, `owner.py` **15 %**, `audit.py` **9 %** (453 of 498 missed), `assets.py` 50 % | the whole "every conclusion shows why" claim is carried by code no test has ever executed |
| S2 | per-endpoint body coverage | **0 % executed:** `get_asset`, `get_lineage`, `expand_lineage`, `get_column_lineage`, `evidence_at_time`, `search_team_members`, `get_editable_metadata`, `validate_metadata_field`, plus every `rea.py` handler and all personalization endpoints (`star_asset`, `record_asset_view`, `list_starred_assets`) | the four-state read path, time travel and column lineage have **never run**. They are not "unverified" in the mild sense — the functions were entered and returned before reaching the logic |
| S3 | listed the served OpenAPI paths | **no lineage/evidence export route exists** (`/export-audit` is the only "export" in the API, and it is an audit export). **No vector or hybrid search** — `/search` is keyword only. **No evidence-explorer query route** beyond `/evidence-at-time` | spec §10 (the differentiator screen), item 11 (exports) and item 9 (hybrid search) have no backend. My earlier note "JSON export exists" was wrong: **no lineage export exists at all** |
| S4 | drove the UI in a browser and watched the network | clicked all 22 nav entries → **1 API call total** (`/auth/config`). The Evidence & reasoning, Time travel, Catalog and Lineage screens rendered entirely from in-page fixtures while the header claimed "records returned by the PostgreSQL catalog API" | your screens exist as markup and are not connected. `frontend/src/api/client.js` is correct — nothing calls it for catalog data, because `AssetCapabilitiesPanel.jsx` is **never imported by any module** |
| S5 | `GET /api/v1/assets/{id}/capabilities` unauthenticated | 401, and **1 % of its body is covered** (`capabilities.py` 67 % but the route function `get_asset_capabilities` sits in the missed range 198-225) | the registry that is supposed to gate every tab is neither tested nor consumed |
| S6 | `python scripts/check_openapi_drift.py` | `OpenAPI contract unchanged (67 paths)` ✅ | keep this — it is one of the two genuinely working gates |
| S7 | cross-referenced every frontend `fetch` against the 67-path contract | **the frontend calls 9 endpoints that never existed**: `/data-products`, `/incidents` (real one is `/governance/incidents`), `/proposals`, `/proposal-decision`, `/requests`, `/request-submit`, `/request-decision` (all in app.js), `/lineage/export`, `/pii-classification` (pii-lineage-enhancements.js) — the Data Products screen and the proposal/request flow can never work even with a healthy DB; conversely **54 of 67 real endpoints are called by no frontend file**, including your whole surface (`/lineage/{asset_id}/{direction}`, `/assets/{asset_id}`, `/downstream-impact`, `/column-lineage` is called but `/assets/{asset_id}/lineage` is not) | for each phantom endpoint: build it or delete the caller; for the uncalled real ones, decide which screen consumes them (with M4/M5) | report §9

**What this changes for you:** your stream is the least *shipped* and the most *claimed*. The route layer you already wrote is plausible; what is missing is (a) tests that execute the bodies, (b) the export + hybrid-search + evidence-explorer endpoints, (c) a UI that actually calls them. Do not add another lineage feature until a request from a browser returns rows you can point at.

## 3. What you need to do

**Wave 0**
1. Review + PR the uncommitted `capabilities.py` and the `openapi.json` delta (contract change needs your sign-off as evidence-semantics owner).
2. Decide G8 and record it: either delete the three dead `.tsx` files in a revert PR or write the migration plan that mounts them. Do not leave both trees in `main`.

**Wave 2 — make lineage honest on screen**
3. Edge inspector (P0): one API `GET /api/v1/lineage/edges/{edge_id}/evidence` returning §5.2 records, and a UI panel with relationship type, state, evidence source + id, coverage (complete/partial/unknown), **evidence strength as the rule-derived ordinal `High/Medium/Low` (C1 — the stored `confidence` stays `null`, the API returns the label, the client never computes a score and never prints a percentage)**, valid/recorded time, and the explanation sentence. Tests: `tests/test_lineage_evidence.py`, `frontend/__tests__/edge-inspector.test.js`.
4. Evidence state legend + four verbatim Section-19 wordings; assert in a test that "no runtime event" is never rendered as a negative.
5. Evidence explorer (P1): raw sanitized payload, normalized view, provenance chain, conflict view (two disagreeing evidence records), temporal view.
6. Time travel: `?as_of=` / `?recorded_as_of=` on lineage + asset queries against `edge_temporal_version`; separate T_v / T_k pickers in the UI (never one merged control); display the historical banner; disclose undated rows instead of implying complete history. Resolve D-13/D-14 with M1/M5 and write the answers into `DATA_MODEL.md`.
7. Canonical identity: finish `canonical_ids.py:254`, add rename/schema-change tests (identity stability is a Perplexity P0 correctness item: "Test duplicate ingestion and canonical identity stability").

**Wave 3 — discovery**
8. Catalog: facet filters, saved views ("My assets", "Critical", "Stale", "PII"), pagination, preview drawer, honest empty states, per-row fields from spec §3.
9. Search: keyword + `pgvector` hybrid with graph expansion, all queries RLS-scoped; add a test proving a non-member cannot retrieve an asset by search or embedding. Keep the "keyword vs semantic" distinction visible in the UI label.
10. Lineage screen completeness: node inspector (asset summary, schema, owner, freshness, incidents), depth control 1/2/3/5/custom, **search-within-graph**, **mini-map**, filters, and the 2D/3D toggle against the existing `observatory.js` (the spec says preserve the 3D view — it is a visualization layer, not an ingestion claim). Then column-level toggle, path highlighting, impact radius / downstream propagation view, root-cause trace.
11. Exports: PNG/SVG client-side + **JSON of the visible subgraph including the evidence states** (note: no lineage export exists today — do not assume `audit.py`'s export is it). Decide client-vs-server with M1 (checklist §15 D10).
12. Consume the capability registry for every tab of Asset Detail; unsupported ⇒ render "not available because <reason>". Add the two missing tabs (Activity from `asset_version`, Relationships from glossary/product/contract links).
13. Every inspector you ship must answer the spec's five questions about the thing it shows: *what do we know · how do we know it · when did we learn it · for which run or period · what remains unknown*. Use that as the acceptance checklist for the edge inspector, the evidence explorer, and the freshness panel — if a question has no answer on screen, the panel is unfinished.

## 4. Definition of done (your gate)

Clicking any visible edge opens a panel whose every word comes from a stored evidence row; a declared or parsed edge can never look runtime-observed; a missing event never looks like "no lineage"; the same graph can be re-queried at a past time and shows what was known then; search results respect workspace membership.

**Additions from today's measurement (§2b):** `lineage.py`, `search.py`, `assets.py` and `audit.py` each have a test that **executes the handler body and asserts on returned rows** (they are at 0-18 % today); at least one browser request to `/catalog`, `/lineage`, `/column-lineage` and `/evidence-at-time` returns real rows and is screenshotted with the network panel visible; `GET /assets/{id}/capabilities` is consumed by a mounted component; and the export + hybrid-search + evidence-explorer endpoints exist in the served OpenAPI or are written out of scope in `DECISION_LOG.md` with a reason.

## 5. Do not

- Do not add a numeric confidence anywhere (C1), and do not import `confidence`-style heuristics from the REA/Atlan analysis docs — `REA_ANALYSIS_SUMMARY.md` is already unverifiable (it names components and dependencies that do not exist in this repo).
- Do not fabricate lineage from similar names, and do not broaden the SQL corpus beyond the restricted research scope to make the graph look fuller.
- Do not edit `contracts/` semantics alone — M1/M5 review, and update the OpenAPI snapshot in the same PR.

---

## 6. Full-project completion backlog — catalog, lineage, evidence to 100 %

### Fix (broken today)
| # | Task | DoD |
|---|---|---|
| F1 | Decide per phantom endpoint (S7): build `/lineage/export` + `/pii-classification`, repoint `/incidents` caller to the real `/governance/incidents`, route proposals/requests/data-products decisions to M4, delete dead callers | zero frontend calls to non-existent routes |
| F2 | Catalog search screen renders no input in demo (browser §14) — the search form at app.js:437 is unreachable | search screen has a working input that calls `/api/v1/search` |
| F3 | `dependency.py:303-315` defaults absent coverage JSON to fully-covered (evidence-first violation) | absent coverage ⇒ UNKNOWN contribution, test pins it |
| F4 | `/catalog` unbounded evidence×edge dumps; add caps + `X-Result-Truncated` | 10k-edge workspace stays under the 1 MB envelope with named truncation |

### Build (missing for 100 %)
| # | Task | DoD |
|---|---|---|
| B1 | **Evidence strength High/Med/Low** as an API-derived rule (C1 #14, v2 C1) + **conflict view** | strength computed from evidence mix, never stored opinion; conflicts render side-by-side |
| B2 | **Domains** (C1 #4): entity, page, asset/owner/steward mapping | domains CRUD + scoping on assets |
| B3 | Catalog pagination (C1 #13-row) + asset-row missing fields (incident count, popularity) | page/page_size on /catalog + /search with totals header |
| B4 | Asset profile gaps: Relationships tab (terms/products/contracts), Schema tab PK/constraints, per-asset Evidence tab | all four tabs render from API data |
| B5 | Lineage exports: PNG/SVG/JSON-with-evidence (D10) | all three download; JSON carries evidence refs |
| B6 | Root-cause view (upstream walk + incident overlay), mini-map (P2, optional) | root-cause demoable; mini-map only if time remains |

Coordinates with M4: stewardship/product endpoints they build are your callers; agree the response shapes first.
