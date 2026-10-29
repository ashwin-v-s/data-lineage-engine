# Atlan UI/UX Pattern Analysis

**Created**: September 23, 2026
**Method**: Public documentation and recorded demos (REA analysis not available for closed-source SaaS)
**Status**: Complete documentation from official sources

## Overview

Atlan is a collaborative metadata platform with closed-source frontend. Analysis based on:
- Official product documentation
- Public demo videos
- User reviews and blog posts
- Feature comparisons

## 1. Atlan Core UI Patterns

### 1.1 Dashboard & Quick Navigation

**Pattern**: Personalized dashboard with recommendation engine

```
┌─────────────────────────────────────────────────┐
│ ✨ Welcome Back, Alice!                         │
├─────────────────────────────────────────────────┤
│                                                 │
│ 🚀 Quick Links (Personalized)                   │
│ ┌──────────────────────────────────────────┐   │
│ │ ⭐ master_customer_data                  │   │
│ │ ⭐ revenue_fact_table                    │   │
│ │ ⭐ campaign_analytics_dashboard          │   │
│ └──────────────────────────────────────────┘   │
│                                                 │
│ 📊 Recently Viewed                              │
│ ┌──────────────────────────────────────────┐   │
│ │ orders_fact (1h ago)                     │   │
│ │ customers_dim (3h ago)                   │   │
│ │ stg_orders (yesterday)                   │   │
│ └──────────────────────────────────────────┘   │
│                                                 │
│ 💡 Recommended For You                          │
│ ┌──────────────────────────────────────────┐   │
│ │ ┌─────────────────────────────────────┐ │   │
│ │ │ 📊 dim_time                         │ │   │
│ │ │ Based on your recent activity       │ │   │
│ │ │ 87% match with your team's queries  │ │   │
│ │ └─────────────────────────────────────┘ │   │
│ │ ┌─────────────────────────────────────┐ │   │
│ │ │ 📈 product_hierarchy                │ │   │
│ │ │ Often used with: master_customer... │ │   │
│ │ └─────────────────────────────────────┘ │   │
│ └──────────────────────────────────────────┘   │
│                                                 │
│ [Browse Catalog] [Create New] [Explore]        │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Distinctive Features**:
- AI-powered recommendations
- Personalization based on team activity
- Match scores showing relevance
- One-click access to starred items
- Role-specific quick links

### 1.2 Entity Editor - Inline Editing

**Pattern**: Click-to-edit fields with permission-based access

```
┌──────────────────────────────────────────────────┐
│ 📊 orders_fact                                   │
│                                                  │
│ Basic Information:                               │
│ ┌─────────────────────────────────────────────┐ │
│ │ Name: [orders_fact ✎]                      │ │
│ │ Title: [Order Transactions ✎]              │ │
│ │ Description: [Main fact table... ✎]        │ │
│ │ Database: [prod_db ✎]                      │ │
│ │ Schema: [warehouse ✎]                      │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ Ownership & Governance:                         │
│ ┌─────────────────────────────────────────────┐ │
│ │ Owner:                                      │ │
│ │ [👤 Alice Chen (Owner)] ✕                  │ │
│ │ [+ Add Owner]                               │ │
│ │                                              │ │
│ │ Stewards:                                   │ │
│ │ [👤 Bob Smith (Data Steward)] ✕            │ │
│ │ [👤 Carol Lee (Domain Expert)] ✕           │ │
│ │ [+ Add Steward]                             │ │
│ │                                              │ │
│ │ Reviewers:                                  │ │
│ │ [👤 Dave Wilson (Data Consumer)] ✕         │ │
│ │ [+ Add Reviewer]                            │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ Classifications & Tags:                         │
│ ┌─────────────────────────────────────────────┐ │
│ │ [PII ✕] [Prod ✕] [Daily] [Master Data]   │ │
│ │ [+ Add Classification]                      │ │
│ │ [+ Add Business Term]                       │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ [Save Changes] [Cancel] [Revert]                │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Distinctive Features**:
- Role hierarchy: Owner → Stewards → Reviewers
- Click pencil icon to edit
- Multi-level user assignment
- Classifications and Business Terms separate
- Full audit trail of changes
- Permission-based field access

### 1.3 Relationship Graph

**Pattern**: Knowledge graph with context-aware relationships

```
                ┌─────────────────┐
                │  orders_fact    │
                │  📊 TABLE       │
                └────────┬────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼─────┐    ┌───▼────┐    ┌─────▼────┐
    │customers_ │    │stg_    │    │revenue_  │
    │dim        │    │orders  │    │summary   │
    │📊 DIM    │    │📊 STG  │    │📊 MART   │
    └────┬─────┘    └───┬────┘    └─────┬────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                    ┌────▼────┐
                    │business_ │
                    │metrics   │
                    │📊 METRIC │
                    └──────────┘

Relationship Types:
━━━━━━━━━━━  Lineage (data flow)
─ ─ ─ ─ ─   Business Context
═════════   Impact (downstream)
```

**Distinctive Features**:
- Knowledge graph showing all relationships
- Multiple relationship types
- Context-aware entity icons
- Impact radius indicator (how many downstream)
- Business context separate from lineage
- Drill-down available on each relationship

### 1.4 Data Quality Framework

**Pattern**: Comprehensive quality scorecard with metrics breakdown

```
┌──────────────────────────────────────────────┐
│ Data Quality                                 │
├──────────────────────────────────────────────┤
│                                              │
│ Overall Quality Score: 87% 🟢               │
│ ████████░ (Last Updated: 2h ago)            │
│                                              │
│ Quality Dimensions:                          │
│ ┌────────────────────────────────────────┐  │
│ │ Completeness:  92% 🟢 Complete         │  │
│ │ ████████░                              │  │
│ │                                        │  │
│ │ Accuracy:      84% 🟡 Needs Work       │  │
│ │ ████░░░░░                              │  │
│ │                                        │  │
│ │ Timeliness:    95% 🟢 On-Time          │  │
│ │ █████████░                             │  │
│ │                                        │  │
│ │ Validity:      88% 🟢 Valid            │  │
│ │ ████████░                              │  │
│ │                                        │  │
│ │ Uniqueness:    91% 🟢 Unique           │  │
│ │ █████████░                             │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Issues & Alerts:                             │
│ ┌────────────────────────────────────────┐  │
│ │ ⚠️  Critical Issues: 3                 │  │
│ │   • Duplicate rows in order_id (0.2%) │  │
│ │   • NULL values in customer_id (1.5%) │  │
│ │   • Data type mismatch in created_at  │  │
│ │                                        │  │
│ │ ℹ️  Warnings: 2                       │  │
│ │   • Missing recent data (48h lag)     │  │
│ │   • High variance in row counts       │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Quality Certifications:                      │
│ ┌────────────────────────────────────────┐  │
│ │ ✅ Production Ready (Certified)        │  │
│ │ ✅ Privacy Compliant (GDPR)            │  │
│ │ ❌ SOC2 Compliant (Pending)            │  │
│ └────────────────────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

**Distinctive Features**:
- Multi-dimensional quality scoring
- Color-coded severity (🟢🟡🔴)
- Specific issues with impact percentage
- Quality certifications/badges
- Integration with monitoring systems
- Trend analysis over time

### 1.5 Collaborative Features

**Pattern**: Real-time collaboration and workflow

```
┌──────────────────────────────────────────┐
│ Discussions & Activities                 │
├──────────────────────────────────────────┤
│                                          │
│ 💬 @Alice Chen mentioned you (2h ago)   │
│    "This table has PII - needs review"  │
│    [View Conversation]                  │
│                                          │
│ ✅ @Bob Smith approved changes (5h ago) │
│    "Data governance policy compliance"  │
│    [View Approval]                      │
│                                          │
│ 🔔 Certification Status Changed (1d ago)│
│    From: Pending → Approved              │
│    By: Carol Lee (Data Governance)       │
│                                          │
│ [Add Comment] [Tag Team] [Assign Task]   │
│                                          │
└──────────────────────────────────────────┘
```

**Distinctive Features**:
- Inline comments and discussions
- @mentions and team collaboration
- Approval workflows
- Certification tracking
- Activity timeline
- Task assignment integration

## 2. Comparison: Atlan vs. KAIROS

| Feature | Atlan | KAIROS (Current) | Gap |
|---------|-------|------------------|-----|
| **Dashboard** | AI-powered recommendations | None | High |
| **Inline Editing** | Click pencil to edit | Read-only | High |
| **Role Hierarchy** | Owner/Steward/Reviewer | Metadata only | High |
| **Quality Scorecard** | Multi-dimensional | None (M4 planned) | Critical |
| **Relationships** | Knowledge graph | Lineage only | High |
| **Collaboration** | Comments/Approvals | None | Medium |
| **Workflow** | Certification workflows | None | Medium |
| **Impact Analysis** | Visual downstream impact | Partial | High |
| **Business Context** | Business terms/lineage | Lineage only | Medium |

## 3. Implementation Priority for KAIROS

### High Priority (Align with KAIROS M2-M5)
1. **Inline Editing UI** (complements M5 API)
2. **Owner/Steward Assignment** (governance support)
3. **Quality Scorecard** (leverage M4 reasoning)
4. **Impact Analysis** (show downstream effects)
5. **Collaboration Panel** (comments/discussions)

### Medium Priority (Future Phases)
6. **Business Context Graph** (complement lineage)
7. **AI Recommendations** (learning from usage patterns)
8. **Workflow Integration** (governance workflows)

### Low Priority (Advanced Features)
9. **Certification Workflows** (governance audit trail)
10. **Team Analytics** (usage trends)

## 4. Key Atlan Differentiators to Adapt

### 4.1 Role Hierarchy
- Not just "owner" but Owner/Steward/Reviewer roles
- Permissions based on role
- Visible indicator of role next to name
- Support for multiple stewards

### 4.2 Quality Dimensions
- Multi-metric scoring (not just one number)
- Color-coded severity levels
- Specific issues with percentages
- Integration with monitoring systems

### 4.3 Relationship Types
- Lineage (technical data flow)
- Business Context (conceptual relationships)
- Impact (downstream propagation)
- Separate visualization toggles

### 4.4 Change Tracking
- Every field change tracked
- User and timestamp recorded
- Full audit trail visible
- Rollback capability for admins

## 5. Atlan Patterns for KAIROS Implementation

### Pattern 1: Click-to-Edit Field
```tsx
<EditableField 
  value={owner}
  onSave={(newOwner) => updateOwner(newOwner)}
  editIcon="✎"
  permission="edit_owner"
/>
```

### Pattern 2: Role Selector
```tsx
<RoleSelector
  roles={[
    { role: 'Owner', user: 'Alice', removable: true },
    { role: 'Steward', user: 'Bob', removable: true },
    { role: 'Reviewer', user: 'Carol', removable: false }
  ]}
  onAdd={(role) => addUser(role)}
/>
```

### Pattern 3: Quality Scorecard
```tsx
<QualityCard
  overallScore={87}
  dimensions={[
    { name: 'Completeness', score: 92, status: 'good' },
    { name: 'Accuracy', score: 84, status: 'warning' },
    { name: 'Timeliness', score: 95, status: 'good' },
  ]}
  issues={criticalIssues}
/>
```

### Pattern 4: Relationship Graph
```tsx
<RelationshipGraph
  entity={currentEntity}
  relationshipTypes={['lineage', 'business_context', 'impact']}
  showImpactRadius={true}
/>
```

## 6. Integration with KAIROS M5

These Atlan patterns integrate directly with existing KAIROS endpoints:

| Component | KAIROS Endpoint | Implementation |
|-----------|-----------------|-----------------|
| Owner/Steward | M5 API PUT /assets/{id} | Form field + dropdown |
| Quality Metrics | M4 Integration via API | Read-only scorecard |
| Impact Analysis | Recursive GET /downstream | Graph traversal + UI |
| Relationships | GET /assets/{id}/lineage | Multi-type filtering |
| Comments | New endpoint PUT /assets/{id}/comments | Activity panel |

## 7. References

- [Atlan Product Tour](https://www.atlan.com/product-tour/)
- [Atlan Governance](https://www.atlan.com/governance/)
- [Atlan Data Quality](https://www.atlan.com/data-quality/)
- [Atlan Collaboration](https://www.atlan.com/collaboration/)
