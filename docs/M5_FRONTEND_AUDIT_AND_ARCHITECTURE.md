# Kairos M5 Architecture & Implementation Audit: Stage-1 Lineage Frontend

**Role**: Member 5 (API & UI Lead)  
**Date**: 2026-09-23  
**Status**: DRAFT FOR REVIEW & APPROVAL  
**Primary Source Reference**: `docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md` (Sections 10, 11, 12, 17, 19, 34, 46) & `docs/TEAM_GUIDE.md` (Section 12)

---

## Executive Summary

This document presents the complete architectural and implementation audit for **Member 5 (M5)**. It evaluates the provided Stitch visual prototype against the locked requirements of the Kairos architecture, establishes the exact boundaries between team members, specifies the target **React + TypeScript** application architecture, and formalizes the REST API contracts required under `/api/v1`.

---

## 1. What Already Exists

### 1.1 Stitch Visual Prototype (`frontend/index.html` & `frontend/app.js`)
- **Visual Design**: High-fidelity visual styling, dark-mode design tokens, custom SVG filters, CSS classes, and layout scaffolding for the "Temporal Lineage Cockpit".
- **Interface Structure**: 
  - Dual bitemporal controls bar ($T_v$ vs $T_k$).
  - Left Filter Rail (entity types, relationship types, 4-state filters, depth stepper).
  - Floating Canvas HUD (granularity toggle, zoom, fit, isolate, trace path).
  - SVG topological graph with D-14 hazard badge.
  - Atlan / Neo4j Bloom style Directional Expansion popover.
  - Minimap HUD.
  - Right Inspector panel with tabbed navigation (`Details`, `Evidence`, `Relationships`).
- **Limitation**: Currently implemented as static/mock markup with vanilla DOM manipulation. Data is hardcoded in the HTML structure rather than dynamically rendered from API payloads.

### 1.2 FastAPI Backend Core (`backend/app/`)
- `backend/app/main.py`: Fully operational FastAPI application with CORS middleware, structured error handling (`{"error": {"code", "message", "details", "request_id"}}`), and route definitions for all Section 17 operations.
- `backend/app/schemas/`: Typed Pydantic models implementing the Section 17 contract:
  - `HealthResponse`, `SearchResponse`, `EntitySummary`.
  - `LineageResponse`, `LineageNode`, `LineageEdge`.
  - `DependencyResponse`, `CoverageVectorModel`, `EvidenceRef`.
  - `RunResponse`, `RunLineageResponse`, `EvidenceListResponse`.
  - `IngestResponse`, `BenchmarkOracleResponse`.
- `backend/app/mock_repo.py`: In-memory bitemporal repository serving Section 11 worked examples, the Section 19 cockpit topology (`orders_fact` anchor + upstream/downstream), dynamic evaluation via `FourStateEngine`, and `D-14` warning flags.
- `docs/openapi.json`: OpenAPI 3.1 schema specification exported from the FastAPI application.

### 1.3 Foundation Contracts & Reasoning Engine
- `contracts/`: Shared dataclasses for `DependencyKey`, `CoverageVector`, `StaticEvidence`, `RuntimeEvidence`, `PredictorInput`, and `TemporalContext`.
- `research/reasoning/engine.py`: `FourStateEngine` implementing deterministic evaluation rules R1 through R5.
- `scripts/check_import_boundaries.py`: Architectural boundary enforcement script ensuring no leakage between research ground truth and production prediction inputs.

### 1.4 Runtime & Development Environment
- Python 3.11 with FastAPI 0.104.1 and `httpx 0.27.2` (compatible with `starlette.testclient.TestClient`).
- Node.js `v22.20.0` and npm `11.6.2` available in the development environment.

---

## 2. What the Architecture Requires (Stage 1 Lineage Explorer — Locked)

Per Section 19 (`docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md`), Stage 1 is **LOCKED** with the following non-negotiable requirements:

| Component | Architecture Specification |
|---|---|
| **Entity Search** | Search input calling `GET /api/v1/search?q=...`. Selecting an entity anchors and centers the graph on that entity. |
| **Lineage Graph** | Directed graph with upstream and downstream traversal, depth stepper ($1..10$), and granularity switch (Dataset vs Column). Graph truncation (`truncated: true`) must be visible if limits are reached. |
| **Dual Time Controls** | **Valid at ($T_v$)** and **Known as of ($T_k$)** must be separate controls. **Never merged into one date picker.** Defaults mean "latest". |
| **Historical Banner** | When either $T_v$ or $T_k$ is set: `"Showing historical lineage. Valid at X. Known as of Y."` |
| **4-State Text** | Must use the **verbatim canonical sentences** from Section 19 (see Section 2.1). No paraphrasing. |
| **Uncertainty Rules** | - Never render "no runtime event" as negative evidence.<br/>- Never draw a `POSSIBLE` edge as absence or a faded/broken line that implies "no dependency".<br/>- **Never show a numeric confidence score** or percentage.<br/>- Multi-redundant styling: state must be identifiable by label + icon/glyph + border pattern, **never color alone**. |
| **Node Details** | Clicking a node loads name, type, namespace, canonical UUID, schema version, and columns into the Inspector. |
| **Edge Details** | Clicking an edge calls `GET /api/v1/runs/{run_id}/dependency/{source}/{target}` and opens the Evidence Dossier panel (`GET /api/v1/evidence/{dependency}`). |
| **Evaluation Mode** | Ground truth (`PROPAGATED` / `NOT_PROPAGATED`) is hidden by default and only viewable in a clearly flagged Benchmark Hazard Mode. |
| **API Exclusivity** | The frontend calls `/api/v1` exclusively. It **must never** reimplement storage queries, SQL parsing, or reasoning logic. |

### 2.1 Mandatory Section 19 Verbatim State Text

| State | Locked UI Interpretation Text |
|---|---|
| `OBSERVED` | *"At least one source value was observed to contribute to at least one target output in this run. This does not imply contribution to every row or every run."* |
| `REFUTED_FOR_RUN` | *"No propagation was established for this run under the declared complete-evaluation conditions. This is not a universal claim that the dependency can never occur."* |
| `POSSIBLE` | *"Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run."* |
| `UNKNOWN` | *"Kairos cannot safely evaluate this dependency because relevant semantics, identity, schema or instrumentation is unsupported or ambiguous."* |

---

## 3. What Is Missing

1. **Vite + React + TypeScript Build Scaffolding**:
   - `frontend/` currently lacks `package.json`, Vite configuration, TypeScript configurations (`tsconfig.json`), and build/dev dependencies.
2. **Dynamic Graph Engine**:
   - The mockup uses hardcoded SVG paths (`<path d="M 330 240..."/>`). When new nodes are added, filtered, or expanded, manual SVG math fails. A declarative graph canvas (React Flow) with automated layout (Dagre) is required.
3. **Typed API Client & Caching Layer**:
   - No asynchronous client utilizing TanStack React Query to fetch, cache, and synchronize graph queries with $T_v$ / $T_k$ state.
4. **Interactive Bitemporal Query Reactivity**:
   - Changes to the time sliders must trigger parameter updates to `/api/v1/lineage/{entity}?as_of=...&recorded_as_of=...` and reactively update node states and edge styles.
5. **Dynamic Selection State**:
   - Selecting a node or edge must trigger live detail fetching for the Inspector drawer.
6. **Live Directional Expansion Engine**:
   - Clicking `+ Upstream (n)` or `+ Downstream (n)` must trigger partial graph expansion queries (`/api/v1/lineage/{id}/upstream?depth=1`).

---

## 4. What Can Be Reused

1. **Tailwind Design System & Tokens**:
   - Complete color palette (`surface: #051424`, `primary: #8ed5ff`, `tertiary: #ffbf9e`, `secondary: #d0bcff`, `error: #ffb4ab`), typography settings (`Inter`, `JetBrains Mono`), and custom borders can be directly applied to the React app.
2. **Visual Components & Layout Specs**:
   - The 3-zone cockpit layout: Compact Left Filter Rail (collapsible), Dominant Canvas (>60%), and Right Inspector (collapsible with tabbed dossier views).
   - The Atlan / Bloom style Directional Expansion popover UI.
   - The D-14 Hazard Pill and Benchmark Evaluation Mode hazard styling.
3. **Backend Endpoints & Mock Fixtures**:
   - The FastAPI endpoints in `backend/app/main.py` and models in `backend/app/schemas/` match the exact data shapes needed by the UI.

---

## 5. What Needs to Be Changed

1. **Decouple Data from View**:
   - Remove hardcoded graph nodes (`orders_fact`, `stg_customer_orders`, etc.) from HTML. Replace with a dynamic graph canvas fed by the API.
2. **Migrate from Vanilla JS to React + TypeScript**:
   - Encapsulate the UI into structured, reusable React components with strict TypeScript types for props and API responses.
3. **Adopt React Flow (`@xyflow/react`) for Canvas**:
   - Replace absolute SVG coordinate math with React Flow nodes, custom node templates (Table, View, Job, Stream), custom edges with pattern strokes, and Dagre automated layout.
4. **Strict Error and Loading States**:
   - Add loading skeletons, network error banners, and empty search results.

---

## 6. What Belongs to Other Team Members (Strict Boundaries)

To comply with the project contract and the import boundary rules:

- **Member 1 (Static Lineage)**: Owns SQLGlot AST extraction, construct support matrix (`SUPPORT_MATRIX.md`), and the B1 baseline. *M5 must not write SQL parsing logic in the UI or backend.*
- **Member 2 (Runtime Evidence & Ground Truth)**: Owns OpenLineage normalizer and ProvSQL / ground truth generation. *M5 must never synthesize real runtime events or leak ground truth into standard lineage views.*
- **Member 3 (Bitemporal Storage & DB Authority)**: Owns PostgreSQL migrations, table DDL, identity UUID generation, and SQL temporal queries. *M5 works against mock repositories today and will swap to M3's `PostgresRepository` when ready.*
- **Member 4 (Reasoning Engine & Experiments)**: Owns `FourStateEngine`, rules R1–R5, MCAR loss simulator, and benchmark protocol. *M5 only displays the engine's output states and must never invent reasoning logic in the frontend.*

---

## 7. Recommended React + TypeScript Frontend Architecture

```
frontend/
├── package.json               # React 18/19, TypeScript, @xyflow/react, @dagrejs/dagre, @tanstack/react-query
├── vite.config.ts             # Vite configuration with proxy to http://127.0.0.1:8000
├── tailwind.config.js         # Ported Kairos Forensic design tokens
├── tsconfig.json              # Strict TypeScript configuration
└── src/
    ├── api/                   # Typed API client
    │   ├── client.ts          # Fetch wrapper with error envelope handling
    │   ├── types.ts           # TypeScript interfaces matching backend/app/schemas/
    │   └── queries.ts         # TanStack Query hooks (useLineage, useSearch, useDependency, useEvidence)
    ├── components/
    │   ├── header/
    │   │   ├── Header.tsx     # Brand, quick search, density toggle, benchmark mode toggle
    │   │   └── SearchBar.tsx  # Debounced autocomplete search calling /api/v1/search
    │   ├── temporal/
    │   │   ├── TemporalBar.tsx      # Dual pickers (Valid at, Known as of) + Delta indicator
    │   │   └── HistoricalBanner.tsx # Mandatory Section 19 audit banner
    │   ├── graph/
    │   │   ├── LineageCanvas.tsx    # React Flow canvas with Dagre layout auto-positioning
    │   │   ├── CanvasControls.tsx   # Granularity switch, zoom/fit controls, minimap
    │   │   ├── nodes/
    │   │   │   ├── BaseNode.tsx     # Reusable node chrome with category tags and schema version
    │   │   │   ├── TableNode.tsx    # Column table preview, expand buttons
    │   │   │   └── JobNode.tsx      # Transformation job node
    │   │   ├── edges/
    │   │   │   └── LineageEdge.tsx  # Multi-redundant 4-state edges (stroke textures, D-14 hazard pill)
    │   │   └── popovers/
    │   │       └── DirectionalPopover.tsx # Atlan/Bloom upstream/downstream expansion menu
    │   ├── sidebar/
    │   │   └── LeftFilterRail.tsx   # Granularity, Relationship type, 4-state filters, depth stepper
    │   ├── inspector/
    │   │   ├── RightInspector.tsx   # Tab container (Details | Evidence | Relationships)
    │   │   ├── DetailsTab.tsx       # Key-value properties, canonical UUID, verbatim state sentence
    │   │   ├── EvidenceTab.tsx      # AST SELECT, runtime probes, dialect proofs, coverage vector
    │   │   ├── RelationshipsTab.tsx # Graph neighborhood summary
    │   │   └── BenchmarkOracleCard.tsx # Ground Truth card (visible ONLY in benchmark mode)
    │   └── common/
    │       ├── StateBadge.tsx       # Multi-redundant state badge (icon + pattern + text)
    │       └── D14WarningBadge.tsx  # Warning for unknown effective time windows
    ├── hooks/
    │   ├── useTemporalState.ts      # Synchronization of T_v, T_k and Live toggle
    │   └── useGraphLayout.ts        # Dagre automatic hierarchical layout calculation
    ├── App.tsx                      # Root cockpit layout & active selection state
    └── main.tsx                     # Entry point
```

---

## 8. API Contracts Needed by the Frontend (Section 17)

The frontend communicates with `/api/v1` via the following strongly typed schemas:

```typescript
// 1. Lineage Graph Traversal
GET /api/v1/lineage/{entity}?as_of={Tv}&recorded_as_of={Tk}&granularity={COLUMN|DATASET}&depth={1..10}
Response: {
  anchor_entity_id: string;
  nodes: Array<{
    id: string;
    name: string;
    entity_type: "TABLE" | "VIEW" | "JOB" | "COLUMN" | "STREAM";
    namespace: string;
    schema_version?: string;
    columns: string[];
    metadata: Record<string, any>;
  }>;
  edges: Array<{
    edge_id: string;
    source_id: string;
    target_id: string;
    relationship_type: "DERIVED_FROM" | "READS" | "WRITES" | "TRANSFORMS";
    granularity: "DATASET" | "COLUMN";
    reasoning_state: "OBSERVED" | "REFUTED_FOR_RUN" | "POSSIBLE" | "UNKNOWN";
    operator?: string;
    d14_warning: boolean;
    temporal_range: { valid_from: string; valid_to: string | null; tx_from: string; tx_to: string | null; };
  }>;
  temporal_context: { as_of: string | null; recorded_as_of: string | null; };
  granularity: string;
  depth: number;
  truncated: boolean;
}

// 2. Entity Search Autocomplete
GET /api/v1/search?q={query}&type={type}&limit=20
Response: {
  query: string;
  results: Array<{
    id: string;
    name: string;
    entity_type: string;
    namespace: string;
    description?: string;
    column_count?: number;
    row_count?: number;
  }>;
  total: number;
}

// 3. Single Edge Dependency Reasoning & Exact State Text
GET /api/v1/runs/{run_id}/dependency/{source}/{target}?as_of={Tv}&recorded_as_of={Tk}
Response: {
  run_id: string;
  source: { column_id: string; display: string };
  target: { column_id: string; display: string };
  granularity: string;
  state: "OBSERVED" | "REFUTED_FOR_RUN" | "POSSIBLE" | "UNKNOWN";
  interpretation: string; // Locked Section 19 verbatim sentence
  temporal_context: { as_of: string | null; recorded_as_of: string | null };
  coverage: {
    run_covered: boolean;
    operator_covered: boolean;
    source_dataset_covered: boolean;
    target_dataset_covered: boolean;
    source_columns_covered: string[];
    target_columns_covered: string[];
    branches_covered: boolean;
    coverage_mode: string;
    parser_status: string;
  };
  evidence: Array<{
    evidence_id: string;
    type: string;
    source_system: string;
    event_time?: string;
    raw_payload_hash?: string;
  }>;
  reasoning: { engine_version: string; rule_id: string };
  warnings: string[];
  is_mock: boolean;
}

// 4. Evidence Records Dossier
GET /api/v1/evidence/{dependency}
Response: {
  dependency: string;
  records: Array<{
    evidence_id: string;
    evidence_type: string;
    source_system: string;
    event_time: string;
    payload_hash: string;
    details: Record<string, any>;
  }>;
  total: number;
}

// 5. Benchmark Oracle (Hazard Mode Only)
GET /api/v1/evaluation/oracle/{run_id}
Response: {
  warning: string;
  run_id: string;
  records: Array<{
    run_id: string;
    source: string;
    target: string;
    expected_truth_label: "PROPAGATED" | "NOT_PROPAGATED";
    inferred_state: string;
    matches: boolean;
    oracle_hash: string;
  }>;
  is_evaluation_mode: boolean;
}
```

---

## 9. Implementation Plan & Next Steps

Upon your approval, execution will proceed in the following ordered phases:

1. **Phase 1: React + Vite + TypeScript Setup**:
   - Initialize `frontend/` package with React, TypeScript, Vite, Tailwind CSS, `@xyflow/react`, and `@dagrejs/dagre`.
2. **Phase 2: API Client & Query Hooks**:
   - Implement typed API client (`src/api/client.ts`) and React Query hooks (`src/api/queries.ts`) connecting to `/api/v1`.
3. **Phase 3: Interactive Bitemporal Bar & Header**:
   - Wire dual $T_v$ and $T_k$ controls, Live toggle, and the Section 19 mandatory historical banner.
4. **Phase 4: Lineage Canvas & Directional Expansion**:
   - Implement React Flow custom nodes and edges with Dagre layout and Atlan/Bloom directional expansion popovers.
5. **Phase 5: Inspector Panel & Evidence Dossiers**:
   - Wire node and edge selection to live `/api/v1/runs/.../dependency` and `/api/v1/evidence/...` endpoints.
6. **Phase 6: Verification & End-to-End Testing**:
   - Run API contract tests, check import boundaries, and verify full interaction in the browser.
