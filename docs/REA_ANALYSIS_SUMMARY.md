# REA Analysis Summary - KAIROS Frontend Components

**Generated**: September 23, 2026
**Tool**: REA v6.7.0 (JavaScript Application Analyzer)
**Scope**: `frontend/src/components` (16 React components)
**Analysis Size**: 12.4 MB

## Components Analyzed

REA identified and analyzed **16 React/TypeScript components** in the KAIROS frontend:

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **SearchPage** | SearchPage/SearchPage.tsx | Asset discovery and search interface |
| **EntityPage** | EntityPage/EntityPage.tsx | Entity/dataset detail view with tabs |
| **RightInspector** | Inspector/RightInspector.tsx | Tabbed inspector panel (Metadata, Lineage, Evidence) |
| **EvidenceInspector** | Inspector/EvidenceInspector.tsx | Evidence reasoning display |
| **LineageCanvas** | LineageCanvas/LineageCanvas.tsx | D3 interactive lineage graph |
| **LineageNode** | LineageNode/LineageNode.tsx | Individual node in lineage graph |
| **LineageEdge** | LineageEdge/LineageEdge.tsx | Edge representation in lineage |

### Supporting Components

| Component | File | Purpose |
|-----------|------|---------|
| **Header** | Header/Header.tsx | App header with controls |
| **LeftFilterRail** | LeftFilterRail/LeftFilterRail.tsx | Filter sidebar |
| **BitemporalBar** | BitemporalBar/BitemporalBar.tsx | Temporal context selector |
| **DirectionalExpansionPopover** | ExpansionPanel/DirectionalExpansionPopover.tsx | Expansion controls |
| **DetailsTab** | Inspector/DetailsTab.tsx | Metadata details panel |
| **EvidenceTab** | Inspector/EvidenceTab.tsx | Evidence tab content |
| **RelationshipsTab** | Inspector/RelationshipsTab.tsx | Relationships tab |
| **BenchmarkOracleCard** | Inspector/BenchmarkOracleCard.tsx | Benchmark display card |
| **REARecommendations** | UIEnhancements/REARecommendations.tsx | UI recommendations display |

## Key Findings

### 1. Module Dependencies

**External Packages Used**:
- `react` - UI framework (v18+)
- `@tanstack/react-query` - Data fetching & caching
- `@xyflow/react` - Interactive graph visualization
- `recharts` - Chart library
- `json-viewer` - JSON display component
- `tailwindcss` - Styling

**Internal Imports**:
- `@/api/client` - Centralized API client
- `@/components/*` - Component dependencies
- Local utility functions and types

### 2. Network Endpoints

REA identified these API calls from frontend code:

```
GET /api/v1/search                          → SearchPage
GET /api/v1/assets/{id}                     → EntityPage
GET /api/v1/assets/{id}/lineage             → LineageCanvas
GET /api/v1/assets/{id}/lineage/upstream    → Expansion buttons
GET /api/v1/assets/{id}/lineage/downstream  → Expansion buttons
GET /api/v1/evidence/{id}                   → EvidenceInspector
GET /api/v1/runs/{run_id}                   → Details view
GET /api/v1/dependency/{source}/{target}    → Evidence reasoning
```

### 3. Component Patterns

**Data Flow Pattern**:
```
SearchPage (discovery)
    ↓
EntityPage (selection)
    ↓
RightInspector (tabbed view)
    ├─ DetailsTab (metadata)
    ├─ EvidenceInspector (reasoning)
    └─ LineageCanvas (graph)
```

**State Management**:
- React Query for server state (API responses)
- React.useState for local component state
- Context API for global state (inferred)

**Rendering**:
- SearchPage: List/card-based component with pagination
- EntityPage: Tabbed interface with content switching
- LineageCanvas: D3-based interactive graph with XyFlow

### 4. UI/UX Patterns

**Search Experience**:
- Faceted filtering (asset type, namespace, columns)
- Search input with auto-complete
- Paginated results
- Result cards with hover actions

**Entity Details**:
- Tabbed navigation (Metadata | Lineage | Evidence)
- Horizontal tab bar
- Collapsible sections in each tab

**Lineage Visualization**:
- Interactive D3 graph with zoom/pan
- Node labels with dataset names
- Edge connections between datasets
- Expansion buttons (upstream/downstream)
- Control panel (Fit, Isolate, Depth)

**Evidence Display**:
- Collapsible evidence sections
- Type badges (STATIC_AST, RUNTIME_PROBE, DIALECT_PROOF)
- JSON viewer for raw evidence
- Coverage metrics display

## REA Evidence Record

**Evidence ID**: `ev_828bd3274c289eb947ecf683e959e2938b48b7bc85cad51253ee7a8df179a4d0`

**Metadata**:
- Subject: `frontend/src/components` directory
- Digest (SHA256): `91096eb5d59ca8fa57f4cd4a596fbd6e2dbcb9c3061a4be5a55d6444b6fd485f`
- Analyzer: `rea-javascript-application` v1
- Format: Directory of TypeScript/React source files

**Graph Statistics**:
- Total nodes: 300+ (modules, imports, semantic relationships)
- Module relationships: Complete
- Semantic relationships: Validated
- External dependencies: Identified and classified

## Recommendations Based on REA Analysis

### High Priority

1. **Column-level Lineage Visualization**
   - Extend LineageCanvas to show column-to-column dependencies
   - Reference: OpenMetadata column_lineage pattern
   - Complexity: High
   - Impact: Critical for fine-grained data tracing

2. **Path Highlighting on Interaction**
   - Highlight source → target data flow path
   - Dims non-relevant edges
   - Reference: DataHub path highlighting
   - Complexity: Medium
   - Impact: Improves graph readability

3. **Data Quality Indicators**
   - Add quality badges/scores to nodes
   - Color coding by quality level
   - Reference: Atlan quality badges
   - Complexity: Medium
   - Impact: At-a-glance data health

### Medium Priority

4. **Saved Searches / Filters**
   - Persist favorite search combinations
   - Quick-access search templates
   - Reference: DataHub star/favorite
   - Complexity: Medium
   - Impact: Improves UX for power users

5. **Inline Metadata Editing**
   - Editable fields in EntityPage
   - Owner/steward assignment dropdowns
   - Tags and classifications
   - Reference: Atlan inline editing
   - Complexity: Medium
   - Impact: Faster metadata enrichment

6. **Evidence Timeline**
   - Show discovery sequence of evidence
   - Confidence build-up over time
   - Reference: DataHub event history
   - Complexity: Medium
   - Impact: Transparency in reasoning

### Low Priority

7. **Search History**
   - Recent searches carousel
   - Quick access to previous queries
   - Reference: Atlan quick links
   - Complexity: Low
   - Impact: Improves navigation speed

8. **Advanced Query Builder**
   - UI for complex search conditions
   - Boolean logic without SQL
   - Reference: OpenMetadata advanced filters
   - Complexity: High
   - Impact: Enables power users

## Next Steps

1. **Backend Integration**
   - Expose REA findings via `/api/v1/rea/*` endpoints
   - Cache analysis results
   - Return pattern recommendations

2. **UI Enhancement**
   - Display recommendations in settings/help panel
   - Track which recommendations are most useful
   - A/B test feature adoption

3. **Implementation Roadmap**
   - Start with High Priority items
   - Gather user feedback on each enhancement
   - Measure impact on lineage comprehension

4. **Competitor Analysis**
   - Use REA to analyze DataHub, OpenMetadata, Atlan codebases
   - Extract reusable UI components
   - Document pattern variations

## REA Analysis Files

- **Full Analysis**: `rea_analysis_result.json` (12.4 MB)
- **Module Graph**: Embedded in analysis (300+ nodes)
- **Semantic Graph**: Embedded in analysis (JS relationships)
- **Evidence Record**: Immutable, content-addressed

## References

- [REA Documentation](https://rea.tools/)
- [JavaScript Application Analysis Guide](https://rea.tools/guides/javascript-applications/)
- [DataHub GitHub](https://github.com/datahub-project/datahub)
- [OpenMetadata GitHub](https://github.com/open-metadata/OpenMetadata)
- [Atlan Platform](https://www.atlan.com/)
