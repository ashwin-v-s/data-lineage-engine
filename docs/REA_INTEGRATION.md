# REA Integration with KAIROS

## Overview

[REA (Reverse Engineer Anything)](https://github.com/morluto/rea) is integrated into KAIROS to enable:

1. **Automated component analysis** - Extract patterns from KAIROS React components
2. **Competitor pattern extraction** - Learn from DataHub, OpenMetadata, and Atlan UI patterns
3. **UI enhancement recommendations** - Get prioritized feature suggestions based on industry best practices
4. **Implementation guidance** - Step-by-step guides for implementing recommended features

## Architecture

### Components

```
REA Integration
├── Backend Service (backend/app/services/rea_integration.py)
│   ├── Component analysis (JavaScript app structure)
│   ├── Pattern extraction (modules, imports, endpoints)
│   └── Recommendation generation
├── API Endpoints (backend/app/api/routes/rea.py)
│   ├── /api/v1/rea/recommendations - Get all recommendations
│   ├── /api/v1/rea/patterns/{component} - Analyze specific component
│   ├── /api/v1/rea/competitor/{system} - Analyze competitor patterns
│   └── /api/v1/rea/implementation-guide - Implementation steps
└── Frontend UI (frontend/src/components/UIEnhancements/REARecommendations.tsx)
    └── Display recommendations with filtering and drill-down
```

### Data Flow

```
1. Python Script / API Call
   ↓
2. REA CLI (`npx rea-agents@latest analyze-javascript-application`)
   ↓
3. Component Analysis (modules, imports, dependencies)
   ↓
4. Pattern Extraction
   ↓
5. Recommendation Generation
   ↓
6. API Response / Frontend Display
```

## Usage

### 1. Via Python Script

Analyze components and generate recommendations:

```bash
# Analyze KAIROS components
python scripts/rea_ui_analysis.py analyze-components

# Extract patterns
python scripts/rea_ui_analysis.py extract-patterns

# Generate UI recommendations
python scripts/rea_ui_analysis.py recommend
```

Output: JSON with analysis results

### 2. Via Backend API

Get recommendations through REST endpoints:

```bash
# Get all UI recommendations
curl http://localhost:8000/api/v1/rea/recommendations

# Analyze SearchPage component
curl http://localhost:8000/api/v1/rea/patterns/search

# Analyze competitor patterns
curl http://localhost:8000/api/v1/rea/competitor/datahub
curl http://localhost:8000/api/v1/rea/competitor/openmetadata
curl http://localhost:8000/api/v1/rea/competitor/atlan

# Get implementation guide
curl http://localhost:8000/api/v1/rea/implementation-guide
curl http://localhost:8000/api/v1/rea/implementation-guide?component=lineage
```

### 3. Via Frontend UI

The REA Recommendations component displays recommendations in the UI:

```tsx
import { REARecommendations } from '@/components/UIEnhancements/REARecommendations';

export function MyPage() {
  return (
    <div>
      <REARecommendations />
    </div>
  );
}
```

## Recommendations Output

The system generates recommendations organized by UI area:

### 1. Search Experience
- **Current**: Basic faceted search with type/namespace filters
- **Improvements**:
  - Saved searches / filters (DataHub pattern)
  - Full-text search with relevance
  - Advanced query builder (OpenMetadata)
  - Search history and suggestions

### 2. Entity Details
- **Current**: Tabbed view (Metadata, Lineage, Evidence)
- **Improvements**:
  - Owner/steward assignment (Atlan)
  - Inline tagging and annotations
  - Data quality scorecard (OpenMetadata)
  - Related assets widget

### 3. Lineage Visualization
- **Current**: D3 interactive graph with Fit/Isolate/Depth
- **Improvements**:
  - Column-level lineage toggle (OpenMetadata)
  - Path highlighting on hover (DataHub)
  - Impact analysis / downstream propagation (Atlan)
  - Data quality badges on nodes
  - Node filtering by type/system

### 4. Evidence and Reasoning
- **Current**: Collapsible panel with coverage details
- **Improvements**:
  - Evidence timeline (DataHub history pattern)
  - Provenance and confidence scores
  - Evidence comparison across runs
  - Drill-down to source SQL/config

## Competitor Pattern Database

### DataHub Patterns
- **URL**: https://github.com/datahub-project/datahub
- **Key Patterns**:
  - Card-based search results with hover actions
  - Left sidebar + main content layout
  - Interactive D3 lineage with zoom/pan
  - Inline glossary term linking

### OpenMetadata Patterns
- **URL**: https://github.com/open-metadata/OpenMetadata
- **Key Patterns**:
  - Left sidebar with nested filter options
  - Horizontal tab bar with data-driven tab counts
  - Per-column quality metrics
  - Column-level lineage in table view

### Atlan Patterns
- **URL**: https://www.atlan.com/
- **Key Patterns**:
  - Personalized quick links (Recent, Starred, Recommended)
  - Inline editable tags and classifications
  - User avatar selector for owner assignment
  - Carousel of related assets with relationship reason

## Implementation Guide

### Phase 1: Pattern Analysis
Extract UI patterns from competitor using REA:

```bash
# Analyze DataHub frontend
rea analyze-javascript-application /path/to/datahub/web

# Get modules and imports
# Output: modules[], imports[], endpoints[]
```

### Phase 2: Design Adaptation
Map competitor pattern to KAIROS:
- Review React version compatibility
- Check state management approach
- Align with API contracts
- Match styling system (Tailwind, Material-UI)
- Verify accessibility (WCAG 2.1)

### Phase 3: Implementation
Build the feature in KAIROS:
1. Create new component or modify existing
2. Wire to backend API (`/api/v1/...`)
3. Add React Query or state management
4. Implement error handling & loading states
5. Add TypeScript types

### Phase 4: Verification
Test against original pattern:
- Visual regression testing
- Interaction testing (Playwright)
- Performance profiling
- Accessibility audit

## Integration with KAIROS Architecture

### M1: Data Ingestion
No direct impact - REA analyzes existing data structures

### M2: Data Storage
REA patterns are stored in session/memory, not persisted to database

### M3: Query Processing
No impact - REA operates on source code, not lineage queries

### M4: Dependency Reasoning
REA can enhance visualization of reasoning with:
- Evidence timeline
- Confidence scores
- Source drilling

### M5: API & UI
**Primary integration point**:
- REA analysis results feed into UI recommendations
- New endpoints expose analysis capabilities
- Frontend components consume recommendations

## Performance Considerations

### Caching
- Recommendations cached for 1 hour (frontend React Query)
- REA analysis cached in session (not re-run on each API call)
- Competitor patterns hardcoded (no external fetching)

### Timeout
- Default: 300 seconds per REA command
- Configurable via `REA_INTEGRATION_TIMEOUT` env var
- Large frontend bundles may take longer

### Resource Usage
- REA runs in subprocess (separate from FastAPI)
- Analysis is I/O bound (file reading + pattern matching)
- Memory usage: ~200-500MB per analysis

## Troubleshooting

### REA Not Found
```
Error: npx rea-agents@latest not found
```
**Solution**: Install Node.js and npm globally
```bash
npm install --global rea-agents
```

### Analysis Timeout
```
Error: REA command timeout after 300s
```
**Solution**: Increase timeout or simplify scope
```bash
# In backend/app/services/rea_integration.py:
# self.timeout_seconds = 600  # Increase to 10 minutes
```

### JSON Parse Error
```
Error: JSON decode error: Expecting value
```
**Solution**: REA may have output non-JSON (warnings, logs). Check stderr in logs.

### Component Not Found
```
Error: Path not found: frontend/src/components/SearchPage
```
**Solution**: Verify component path is correct and files exist

## Future Enhancements

1. **Real-time analysis hook**: Analyze components on file save
2. **A/B testing integration**: Track which recommendations improve UX metrics
3. **User feedback loop**: Rate recommendation usefulness
4. **Automated implementation**: Generate component code from patterns
5. **Multi-language support**: REA analysis for Python backend patterns
6. **Benchmark suite**: Compare KAIROS UI metrics against competitors

## References

- [REA GitHub](https://github.com/morluto/rea)
- [REA Documentation](https://rea.tools/)
- [REA Showcases](https://rea.tools/showcase/)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [DataHub GitHub](https://github.com/datahub-project/datahub)
- [OpenMetadata GitHub](https://github.com/open-metadata/OpenMetadata)
- [Atlan Platform](https://www.atlan.com/)
