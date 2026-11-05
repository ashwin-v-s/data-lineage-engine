# UI Patterns Synthesis - DataHub, OpenMetadata, Atlan → KAIROS

**Created**: September 23, 2026
**Synthesized From**: REA analysis (DataHub, OpenMetadata) + Public docs (Atlan)
**Purpose**: Identify common patterns and create KAIROS enhancement roadmap

## Executive Summary

Analyzed three leading metadata platforms to extract **8 core UI patterns** that should be adopted in KAIROS. These patterns represent the consensus best practices for metadata discovery and governance UIs.

## The 8 Universal UI Patterns

### Pattern 1: Faceted Search with Card Results

**Used by**: DataHub ✓ | OpenMetadata ✓ | Atlan ✓

**What it is**:
- Left sidebar or top bar with filter options
- Main area showing results as cards or list
- Each result card shows key metadata
- Pagination or infinite scroll

**Why it works**:
- Users can narrow down results without complex queries
- Visual preview helps with selection
- Progressive refinement (apply filters iteratively)
- Accessible to non-technical users

**KAIROS Implementation**:
```
Priority: HIGH (already partially implemented)
Effort: LOW (extend existing SearchPage)

Changes needed:
- Add filter panels if not present ✓ (already done)
- Card hover actions (copy, open, favorite) ✓ (done — star, copy ID/name, open)
- Result metadata preview ✓ (partially done)
- Pagination controls ✓ (done)
```

---

### Pattern 2: Tabbed Entity Details

**Used by**: DataHub ✓ | OpenMetadata ✓ | Atlan ✓

**What it is**:
- Entity name/type shown prominently
- Horizontal (or vertical) tab bar
- Each tab shows different view (Overview, Lineage, Quality, etc.)
- Tab counts show available content

**Why it works**:
- Organized information without overwhelming
- Users jump to specific concern
- Tab counts indicate data availability
- Reduces initial load time (lazy tab content)

**KAIROS Implementation**:
```
Priority: HIGH (already implemented)
Effort: LOW (optimize existing tabs)

Changes needed:
- Show tab counts (e.g., "Lineage (5)" ) ✓ (done)
- Lazy-load tab content ✓ (React Query)
- Add more tabs (Quality, Governance, Related) ✓ (7 tabs incl. Ownership, Audit, Evidence)
- Better tab icons ✓ (partially done)
```

---

### Pattern 3: Interactive Lineage Graph

**Used by**: DataHub ✓ | OpenMetadata ✓ | Atlan ✓

**What it is**:
- Force-directed or hierarchical D3 graph
- Nodes color-coded by type
- Edges show relationships (data flow)
- Controls: Zoom, Pan, Fit, Legend, Download
- Hover/Click for interactions

**Why it works**:
- Visual representation easier to understand than tables
- Interactive controls reduce cognitive load
- Zoom/Pan handle large graphs
- Download for documentation/sharing

**KAIROS Implementation**:
```
Priority: CRITICAL (core feature)
Effort: MEDIUM (extend existing LineageCanvas)

Changes needed:
- Column-level lineage toggle ✗ (high effort)
- Path highlighting on interaction ✗ (medium effort)
- Better node labels/sizing ✓ (done — truncation + hover tooltips)
- Legend toggle ✓ (done)
- Download as PNG ✗ (low effort)
```

---

### Pattern 4: Owner/Steward Assignment

**Used by**: DataHub ✓ | OpenMetadata ✓ | Atlan ✓

**What it is**:
- User avatar selector
- Multi-level roles (Owner, Steward, Reviewer)
- Role-based permissions
- Add/remove buttons

**Why it works**:
- Clear accountability
- Different roles for different concerns
- Visual indicator of responsibility
- Governance audit trail

**KAIROS Implementation**:
```
Priority: HIGH (governance requirement)
Effort: MEDIUM (new UI component + backend)

Changes needed:
- Owner dropdown selector ✗
- Steward multi-select ✗
- Reviewer assignment ✗
- API endpoint to save assignments ✗
- Permission checks based on role ✗
```

---

### Pattern 5: Data Quality Visualization

**Used by**: DataHub ✓ | OpenMetadata ✓ | Atlan ✓

**What it is**:
- Quality score (0-100%)
- Progress bar or color indicator (🟢🟡🔴)
- Per-column or per-dimension metrics
- Issues list with drill-down
- Trend over time

**Why it works**:
- At-a-glance health assessment
- Specific issues actionable
- Trends show improvement/degradation
- Supports prioritization (which to fix first)

**KAIROS Implementation**:
```
Priority: CRITICAL (M4 integration)
Effort: HIGH (depends on M4 API)

Changes needed:
- Quality score display ✗ (blocked on M4)
- Per-dimension breakdown ✗ (M4 reasoning)
- Issues panel ✗ (M4 evidence)
- Trend chart ✗ (requires M2 temporal)
- Integration with evidence (M4) ✗
```

---

### Pattern 6: Relationship/Dependency Graph

**Used by**: DataHub ✓ | OpenMetadata ✓ | Atlan ✓

**What it is**:
- Shows not just lineage but all relationships
- Multiple relationship types (lineage, business context, impact)
- Toggles for relationship type visibility
- Impact radius indicator (downstream count)

**Why it works**:
- More complete picture than just lineage
- Users understand full dependency graph
- Filter by relationship type reduces noise
- Impact indicator shows risk level

**KAIROS Implementation**:
```
Priority: HIGH (extends lineage)
Effort: MEDIUM (new API endpoint + UI)

Changes needed:
- Business relationship detection ✗
- Relationship type filtering ✗
- Impact radius calculation ✗ (recursive query)
- Multi-relationship graph rendering ✗
```

---

### Pattern 7: Inline Metadata Editing

**Used by**: Atlan ✓ | DataHub (partial) | OpenMetadata (partial)

**What it is**:
- Click pencil icon to edit field
- Inline form appears
- Save/Cancel buttons
- Full audit trail of changes
- Permission-based field access

**Why it works**:
- Faster than modal dialogs
- Context-aware editing
- Reduces navigation
- Audit compliance

**KAIROS Implementation**:
```
Priority: MEDIUM (improves UX)
Effort: MEDIUM (new component + API)

Changes needed:
- Click-to-edit component ✓ (EditableMetadata)
- Inline form rendering ✓ (description / tags)
- API endpoint PATCH /assets/{id} fields ✓ (partial)
- Audit logging ✗
- Permission checks ✗
```

---

### Pattern 8: Recent/Recommended Items

**Used by**: Atlan ✓ | DataHub (recent only) | OpenMetadata (none)

**What it is**:
- Recently viewed carousel
- AI-powered recommendations
- Starred/favorited items
- Quick access bar/sidebar

**Why it works**:
- Power users skip search
- Recommendations reduce exploration time
- Favorites support personalization
- Dashboard approach scalable

**KAIROS Implementation**:
```
Priority: LOW (convenience feature)
Effort: LOW-MEDIUM (simple tracking + UI)

Changes needed:
- Track recently viewed assets ✓ (localStorage)
- Recently viewed carousel ✓ (SearchPage "Quick Access")
- Starred/favorites button ✓ (search result cards)
- Save favorites to backend ✗ (local-only for now)
- (Skip AI recommendations for MVP)
```

---

## Pattern Adoption Roadmap for KAIROS

### Phase 1: Foundation (Complete M5)
✓ Pattern 1 (Faceted Search) - DONE
✓ Pattern 2 (Tabbed Details) - DONE
✓ Pattern 3 (Lineage Graph) - DONE
→ Add: Card hover actions, better labels

### Phase 2: Governance (Weeks 1-4)
→ Pattern 4 (Owner/Steward Assignment)
→ Pattern 7 (Inline Metadata Editing)
Effort: 4-6 weeks (API + UI)

### Phase 3: Quality & Impact (Weeks 5-10)
→ Pattern 5 (Data Quality) - depends on M4
→ Pattern 6 (Relationship Graph) - depends on M5 API
Effort: 6-8 weeks (requires M4 completion)

### Phase 4: Discovery (Weeks 11-14)
→ Pattern 8 (Recent/Recommended) - optional
Effort: 2-3 weeks (nice-to-have)

---

## Implementation Priority Matrix

```
Impact vs. Effort:

            LOW EFFORT              HIGH EFFORT
HIGH        1. Search Actions       5. Quality Viz
IMPACT      2. Tab Counts           6. Relationships
            7. Inline Edit          4. Owner/Steward
            8. Recent Items         3. Column Lineage

LOW         (Skip these)
IMPACT
```

**Recommended Order**:
1. **Immediate** (High Impact, Low Effort):
   - Search result hover actions
   - Tab content counts
   - Better node labels in lineage

2. **Next Sprint** (High Impact, Medium Effort):
   - Owner/Steward UI
   - Inline editing
   - Relationship graph basics

3. **After M4** (Critical but Blocked):
   - Quality scorecard
   - Quality dimension visualization

4. **Nice-to-Have** (Lower Priority):
   - Recent/recommended
   - Trending features
   - Advanced discovery

---

## Pattern Variants: System Differences

### Search Paradigm
- **DataHub**: Card-based + hover actions
- **OpenMetadata**: Sidebar filters + table view
- **Atlan**: Dashboard + personalized recommendations
- **KAIROS Best**: Hybrid (cards + filters + recent)

### Quality Display
- **DataHub**: Badge + link to quality page
- **OpenMetadata**: Multi-dimensional scorecard
- **Atlan**: Certified/verified badges + issues list
- **KAIROS Best**: Scorecards + issues + evidence

### Relationships
- **DataHub**: Lineage only
- **OpenMetadata**: Column-level lineage
- **Atlan**: Business + technical relationships
- **KAIROS Best**: Bitemporal lineage + evidence-based

---

## Technical Implementation Guidelines

### 1. Search Result Cards
```tsx
interface ResultCard {
  entity: Entity;
  onHover?: () => void;
  actions?: {
    favorite?: () => void;
    copy?: () => void;
    open?: () => void;
  };
  showTags?: boolean;
  showOwner?: boolean;
  showQuality?: boolean;  // M4 integration
}
```

### 2. Owner Selector
```tsx
interface OwnerSelector {
  roles: Role[];  // Owner, Steward, Reviewer
  onAdd: (role: Role, user: User) => void;
  onRemove: (role: Role, userId: string) => void;
  permissions?: RolePermissions;
  readOnly?: boolean;
}
```

### 3. Lineage Graph Extensions
```tsx
interface LineageGraphEnhancements {
  showColumnLevel?: boolean;
  highlightPath?: {source: string; target: string};
  relationshipTypes?: ('lineage' | 'business' | 'impact')[];
  impactRadius?: boolean;
  showLegend?: boolean;
}
```

### 4. Quality Scorecard
```tsx
interface QualityScorecard {
  overallScore: number;  // 0-100
  dimensions: QualityDimension[];  // Per-dimension scores
  issues: QualityIssue[];  // Critical issues
  certifications?: Certification[];  // M4 evidence
  trends?: TrendData;  // Over time
}
```

---

## Testing Strategy

### Pattern 1-3: Existing Features
- Regression testing (ensure no breaking changes)
- A/B test action visibility (does hover help?)
- Performance testing (card rendering at scale)

### Pattern 4-7: New Features
- Unit tests for new components
- Integration tests with backend API
- Accessibility testing (WCAG 2.1)
- User acceptance testing (UAT)

### Pattern 8: Optional Features
- Optional feature flag
- User preference setting
- Metrics tracking (if implemented)

---

## Success Metrics

### Pattern 1-3 (Search & Navigation)
- Search result click-through rate ↑
- Time to find asset ↓
- User satisfaction score ↑

### Pattern 4-7 (Governance & Editing)
- Owner assignment rate ↑
- Metadata completeness ↑
- Edit operation count ↑
- Audit log entries ↑

### Pattern 8 (Discovery)
- Search bypass rate ↑ (using recent/recommendations)
- Time to known asset ↓
- New user onboarding time ↓

---

## References & Sources

- [DataHub GitHub](https://github.com/datahub-project/datahub)
- [DataHub Features](https://datahub.io/docs)
- [OpenMetadata GitHub](https://github.com/open-metadata/OpenMetadata)
- [OpenMetadata Docs](https://docs.open-metadata.com/)
- [Atlan Platform](https://www.atlan.com/)
- [Atlan Features](https://www.atlan.com/product/)
- [REA Analysis](https://rea.tools/)
