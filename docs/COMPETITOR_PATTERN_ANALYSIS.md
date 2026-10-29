# Competitor Pattern Analysis - DataHub, OpenMetadata, Atlan

**Created**: September 23, 2026
**Tool**: REA v6.7.0 JavaScript Application Analyzer
**Status**: Analysis in progress (DataHub, OpenMetadata queued; Atlan documented from public sources)

## Executive Summary

This document compares UI/UX patterns from three leading metadata management systems:
1. **DataHub** (LinkedIn open-source)
2. **OpenMetadata** (Collaborative Metadata Platform)
3. **Atlan** (Commercial SaaS)

The analysis uses REA reverse-engineering to identify shared patterns and inform KAIROS UI enhancements.

## System Comparison Matrix

| Feature | DataHub | OpenMetadata | Atlan | KAIROS (Current) |
|---------|---------|--------------|-------|-----------------|
| **Search** | Card-based + faceted filters | Advanced filters + sidebar | Quick links + saved searches | Faceted filters only |
| **Entity Details** | Modal/sidebar with tabs | Tabbed main view | Sidebar + inline edit | Tabbed right panel |
| **Lineage** | Interactive D3 graph | Table + graph toggle | Flow diagram | D3 graph (XyFlow) |
| **Quality** | Basic indicators | Per-column metrics | Badges + scores | None (M4 planned) |
| **Ownership** | Team/owner field | Role assignments | Steward/owner hierarchy | Metadata only |
| **Tagging** | Glossary terms | Classifications | Multi-select tags | None (M4 planned) |
| **Governance** | Policy enforcement | Policies + workflows | Business rules | None (M6 planned) |

## 1. DataHub UI Patterns

### 1.1 Search Experience

**Pattern**: Card-based results with inline actions

```
┌─────────────────────────────────────────────────┐
│  Search [          ] ✓  Advanced  Recent        │
├─────────────────────────────────────────────────┤
│ Filters (Sidebar):                              │
│  ☑ Entity Type: Dataset, Metric, Dashboard     │
│  ☑ Domain: [dropdown]                          │
│  ☑ Owner: [autocomplete]                       │
│  ☑ Tag: [multi-select]                         │
├─────────────────────────────────────────────────┤
│ Results:                                        │
│  ┌─────────────────────────────────────────┐   │
│  │ 📊 orders_fact                    ★      │   │
│  │ Prod | 1.2M rows | Last updated 2d ago  │   │
│  │ Owned by: data-eng@company.com          │   │
│  │ Tags: PII, Prod, Daily                  │   │
│  └─────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────┐   │
│  │ 📊 customers_dim                  ★      │   │
│  │ Warehouse | 450K rows | Updated daily   │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**Key Elements**:
- Star icon for favorites/bookmarking
- Quick hover actions (open, preview, copy link)
- Inline metadata preview
- Entity type icon
- Owner/team attribution
- Tag pills
- Last updated timestamp

**Implementation in KAIROS**:
- Add favorite/star button to search results
- Implement hover actions (copy ID, open in new window)
- Show owner field in result cards
- Display tags/classifications

### 1.2 Entity Details View

**Pattern**: Sidebar with stacked tabs

```
┌──────────────────┬────────────────────────────┐
│ Entity Overview  │ Details Tab (Active)       │
│                  │                            │
│ 📊 orders_fact   │ Basic Info:                │
│ TABLE            │  • Name: orders_fact       │
│ Prod             │  • Type: TABLE             │
│                  │  • Owner: data-eng@co      │
│ ⓘ Properties:   │  • Created: 2024-01-15    │
│  • Rows: 1.2M    │  • Updated: 2026-09-23    │
│  • Size: 2.3GB   │                            │
│                  │ Schema:                    │
│ 🔗 Relationships:│  • order_id (INT, PK)     │
│  • Uses: stg_..  │  • customer_id (INT, FK)  │
│  • Used by: rev_ │  • amount (DECIMAL)       │
│                  │  • created_at (TIMESTAMP) │
│ 👥 Owners:      │                            │
│  • Alice Chen    │ [Lineage] [Quality] [Docs]│
│  • Bob Smith     │                            │
│                  │                            │
└──────────────────┴────────────────────────────┘
```

**Key Elements**:
- Left sidebar with quick info
- Tab navigation (Details, Lineage, Quality, Documentation, etc.)
- Owner/team avatars
- Entity type & environment badge
- Collapsible sections
- Relationship graph mini-view

### 1.3 Lineage Visualization

**Pattern**: Interactive force-directed D3 graph with legend

```
                ┌─────────────────────┐
                │  Entity Legend      │
    ┌──────┐   │ □ Raw              │
    │orders├──────► [Legend Shown]   │
    └──────┘   │ □ Stage            │
       ▲        │ □ Analytics        │
       │        │ □ BI               │
       │        └─────────────────────┘
    ┌──────┐
    │stg_o │ (hover → highlight path)
    │rders │
    └──────┘
       │
       │ (double-click → expand)
       ▼
    ┌──────────┐
    │revenue_  │
    │summary   │
    └──────────┘
```

**Key Elements**:
- Force-directed graph layout
- Node types color-coded
- Edge directions with arrows
- Hover highlights connection
- Double-click to expand level
- Zoom/pan controls
- Fit to screen button
- Legend toggle
- Download as image option

**Differentiator**: Path highlighting on interaction

---

## 2. OpenMetadata UI Patterns

### 2.1 Search & Filters

**Pattern**: Left sidebar with collapsible filter sections

```
┌──────────────────┬────────────────────────────┐
│ Filters          │ Results                    │
│                  │                            │
│ ▼ Entity Type    │ ┌──────────────────────┐  │
│  ☑ Table (42)   │ │ 📊 orders_fact       │  │
│  ☑ Dashboard (8)│ │ TABLE · Production    │  │
│  ☑ Metric (15)  │ │ Updated 2d ago       │  │
│  ☐ Pipeline (3) │ │ Col: 12              │  │
│                  │ │ Rows: 1.2M           │  │
│ ▼ Database       │ │ Quality: 98% ⬤       │  │
│  ☑ PostgreSQL   │ └──────────────────────┘  │
│  ☑ Snowflake    │                            │
│  ☑ BigQuery     │ ┌──────────────────────┐  │
│                  │ │ 📊 customers_dim     │  │
│ ▼ Tier           │ │ TABLE · Warehouse    │  │
│  ☑ Gold          │ │ Quality: 95% ⬤       │  │
│  ☑ Silver        │ │ Owner: Analytics Team│  │
│  ☑ Bronze        │ └──────────────────────┘  │
│                  │                            │
│ ▼ Owner          │ [1-20 of 847]  ← → [ ] □ │
│  [autocomplete]  │                            │
│                  │                            │
└──────────────────┴────────────────────────────┘
```

**Key Elements**:
- Left sidebar filters (always visible)
- Collapsible sections with counts
- Multi-select with checkboxes
- Autocomplete for owner/team
- Right main content area
- Pagination footer
- Quality scores on cards
- Column count in preview

### 2.2 Entity Details - Tabbed View

**Pattern**: Horizontal tabs with data-driven content

```
┌─────────────────────────────────────────────────┐
│ 📊 orders_fact                                  │
│ [Overview] [Lineage] [Docs] [Quality] [+5]     │
├─────────────────────────────────────────────────┤
│ Overview Tab (Active):                          │
│                                                 │
│ Details:                                        │
│ ┌───────────────────────────────────────────┐  │
│ │ Table: orders_fact                        │  │
│ │ Database: prod_db | Schema: warehouse     │  │
│ │ Description: Main orders fact table...    │  │
│ └───────────────────────────────────────────┘  │
│                                                 │
│ Quality Metrics:                                │
│ ┌─────────────────────────────────────────┐   │
│ │ Completeness: 98% ⬤ │ Uniqueness: 92%  │   │
│ │ Validity: 99% ⬤     │ Timeliness: 100% │   │
│ └─────────────────────────────────────────┘   │
│                                                 │
│ Column Details:                                 │
│ ┌─────────────┬──────┬──────────┬─────────┐   │
│ │ Name        │ Type │ Nullable │ Quality │   │
│ │ order_id    │ INT  │ No       │ 100% ✓  │   │
│ │ customer_id │ INT  │ No       │ 98% ⚠   │   │
│ │ amount      │ DEC  │ No       │ 99% ✓   │   │
│ └─────────────┴──────┴──────────┴─────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Key Elements**:
- Horizontal tab bar at top
- Tab counts (Overview, Lineage, +5 more)
- Scrollable tabs if too many
- Quality metrics prominently displayed
- Per-column quality indicators
- Collapsible sections
- Data preview in tables
- Edit buttons inline

### 2.3 Column-Level Lineage

**Pattern**: Table view with nested lineage

```
┌─────────────────────────────────────────────┐
│ Column Lineage                              │
├─────────────────────────────────────────────┤
│ Target: orders_fact.order_id                │
│                                             │
│ Source Columns:                             │
│ ┌──────────────────────────────────────┐   │
│ │ orders.id                            │   │
│ │   └─ [CAST] → INT                    │   │
│ │       └─ orders_fact.order_id        │   │
│ │                                      │   │
│ │ stg_orders.id                        │   │
│ │   └─ [JOIN] customer on cust_id      │   │
│ │       └─ orders_fact.customer_id     │   │
│ └──────────────────────────────────────┘   │
│                                             │
│ View SQL: [Link]  Copy: [Link]              │
│                                             │
└─────────────────────────────────────────────┘
```

**Key Elements**:
- Tree structure showing transformations
- Transformation operators (CAST, JOIN, SUM, etc.)
- Direct column tracing
- SQL preview link
- Copy path button

---

## 3. Atlan UI Patterns

### 3.1 Quick Links & Personalization

**Pattern**: Dashboard-like quick navigation

```
┌─────────────────────────────────────────────────┐
│ Welcome Back, Alice! 👋                         │
├─────────────────────────────────────────────────┤
│ 🌟 Recently Viewed                              │
│ ┌──────────────────────────────────────────┐   │
│ │ 📊 orders_fact    [Edit] [Share]        │   │
│ │ 📊 customers_dim                        │   │
│ │ 📈 revenue_dashboard                    │   │
│ └──────────────────────────────────────────┘   │
│                                                 │
│ ⭐ Starred                                      │
│ ┌──────────────────────────────────────────┐   │
│ │ 📊 master_dataset                       │   │
│ │ 📈 business_metrics                     │   │
│ └──────────────────────────────────────────┘   │
│                                                 │
│ 🔗 Recommended                                  │
│ ┌──────────────────────────────────────────┐   │
│ │ 📊 stg_orders (related to orders_fact)  │   │
│ │ 📊 dim_time (often used with orders)    │   │
│ └──────────────────────────────────────────┘   │
│                                                 │
│ [Browse All] [Create New]                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Key Elements**:
- Personalized dashboard
- Recently viewed carousel
- Starred/favorited items
- Recommendations based on usage
- Quick action buttons
- Clear CTA (Browse, Create)

### 3.2 Inline Metadata Editing

**Pattern**: Click-to-edit fields with role-based permissions

```
┌──────────────────────────────────────────────┐
│ 📊 orders_fact                               │
│                                              │
│ Owner: [Alice Chen ✕] [+ Add]  (Editable)   │
│ Steward: [Bob Smith ✕]         (Editable)   │
│ Reviewer: [Carol Lee ✕] [+ Add] (View only) │
│                                              │
│ Tags: [PII ✕] [Prod ✕] [+ Add Tag]         │
│                                              │
│ Certifications:                              │
│  ☑ Verified by Data Governance (2026-09-20) │
│  ☐ SOC2 Compliant                           │
│                                              │
│ Related Assets:                              │
│ ┌────────────────────────────────────────┐  │
│ │ 📊 stg_orders (source)   [Unlink]     │  │
│ │ 📊 revenue_summary (uses) [Unlink]    │  │
│ │ [+ Link another asset]                │  │
│ └────────────────────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

**Key Elements**:
- Click-to-edit fields
- User avatars with action menus (✕ to remove)
- Multi-select tag input
- Add buttons for multi-value fields
- Inline relationships with unlink option
- Role-based field visibility
- Certification/verification badges
- Timestamp of changes

### 3.3 Related Assets Carousel

**Pattern**: Suggested related items with reason shown

```
┌──────────────────────────────────────────┐
│ Related Datasets                         │
├──────────────────────────────────────────┤
│ ← [████ orders_fact(current) ████] →    │
│                                          │
│ ┌─────────────────────────────────────┐ │
│ │ 📊 stg_orders                       │ │
│ │ Stage Table · Prod Warehouse        │ │
│ │ Reason: Used in lineage             │ │
│ │ Match Score: 95%                    │ │
│ │ [Open] [Link]                       │ │
│ └─────────────────────────────────────┘ │
│                                          │
│ ┌─────────────────────────────────────┐ │
│ │ 📊 customers_dim                    │ │
│ │ Dimension Table · Warehouse         │ │
│ │ Reason: Joined in transformations   │ │
│ │ Match Score: 92%                    │ │
│ │ [Open] [Link]                       │ │
│ └─────────────────────────────────────┘ │
│                                          │
│ ← [████ revenue_summary ████] →         │
│                                          │
└──────────────────────────────────────────┘
```

**Key Elements**:
- Carousel navigation (← →)
- Current item highlighted
- Reason for relationship
- Match/relevance score
- Quick action buttons
- Scrollable if many items

---

## 4. KAIROS Current State vs. Recommendations

### 4.1 Gap Analysis

| Feature Area | KAIROS | Gap | Priority | Effort |
|--------------|--------|-----|----------|--------|
| Search Results | Faceted filters | No favorites/actions | Medium | Low |
| Entity Sidebar | Left sidebar | Read-only | High | Medium |
| Ownership | Metadata field | No assignment UI | High | Medium |
| Quality | None (M4) | Missing metrics | Critical | High |
| Tags/Terms | None | Missing tagging UI | Medium | High |
| Column Lineage | None | Missing fine-grained tracing | Critical | High |
| Lineage Path | Hover focus | No highlight on other path | High | Medium |
| Related Assets | None | Missing suggestions | Low | Medium |
| Edit Inline | None | Metadata read-only | Medium | Medium |

### 4.2 Implementation Roadmap

**Phase 1: Quick Wins (Weeks 1-2)**
- [ ] Add favorite/star button to search
- [ ] Quick hover actions (copy, open)
- [ ] Owner field in result cards
- [ ] Pagination in results

**Phase 2: Ownership & Governance (Weeks 3-4)**
- [ ] Owner/Steward dropdown selectors
- [ ] Inline edit mode with save/cancel
- [ ] Role-based field visibility
- [ ] Certification badges

**Phase 3: Quality & Tagging (Weeks 5-8)**
- [ ] Integration with M4 quality scores
- [ ] Tag/classification UI
- [ ] Column quality metrics
- [ ] Per-column tagging

**Phase 4: Advanced Lineage (Weeks 9-12)**
- [ ] Column-level lineage toggle
- [ ] Path highlighting/dimming
- [ ] Tree view for transformations
- [ ] Impact analysis (downstream)

**Phase 5: Discovery & Personalization (Weeks 13-16)**
- [ ] Recently viewed carousel
- [ ] Recommended related assets
- [ ] Saved search templates
- [ ] User preferences

---

## 5. Shared Patterns Across All Three

### 5.1 Search Paradigm
All three use **faceted search** with:
- Left/top filter panel
- Main results area (cards or table)
- Filters for entity type, owner, tags
- Advanced search option
- Pagination

### 5.2 Entity Details
All three use **tabbed navigation**:
- Overview/Details tab
- Lineage tab
- Quality/Metadata tab
- Relationships/Dependencies
- Documentation

### 5.3 Lineage Visualization
All three provide:
- Interactive graph (D3/force-directed layout)
- Node types with icons/colors
- Zoom/pan controls
- Expand/collapse functionality
- Legend for entity types

### 5.4 Ownership & Governance
All three support:
- Team/user assignment
- Role-based permissions
- Certification/verification
- Audit trail

---

## 6. KAIROS Differentiation Opportunities

### 6.1 Unique Strengths
1. **Bitemporal Context** - Show lineage at specific points in time (KAIROS M2)
2. **Evidence-Based Reasoning** - Display 4-state reasoning for uncertain dependencies (KAIROS M4)
3. **Column-Level by Default** - Focus on column tracing from start (KAIROS M1)

### 6.2 Adoption Strategies
1. Borrow proven patterns from DataHub/OpenMetadata
2. Add KAIROS-specific features (temporal slicing, reasoning visualization)
3. Emphasize data quality through evidence (M4 integration)
4. Make lineage more interactive (path highlighting, impact analysis)

---

## 7. REA Analysis Files

**Status**: In Progress
- `rea_datahub_analysis.json` - Queued (DataHub frontend: 200+ components expected)
- `rea_openmetadata_analysis.json` - Queued (OpenMetadata frontend: 150+ components expected)
- `rea_kairos_analysis.json` - Complete (16 components, 300+ relationships)

**Next Steps**:
1. Extract component patterns from DataHub analysis
2. Extract component patterns from OpenMetadata analysis
3. Create side-by-side implementation comparison
4. Prioritize features for KAIROS based on user value

---

## References

- [DataHub GitHub](https://github.com/datahub-project/datahub)
- [DataHub Docs](https://datahub.io/)
- [OpenMetadata GitHub](https://github.com/open-metadata/OpenMetadata)
- [OpenMetadata Docs](https://docs.open-metadata.com/)
- [Atlan Platform](https://www.atlan.com/)
- [REA Documentation](https://rea.tools/)
