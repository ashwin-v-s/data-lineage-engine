# KAIROS UI/UX Enhancement Roadmap

**Created**: September 23, 2026
**Based On**: REA reverse-engineering analysis of DataHub, OpenMetadata, Atlan
**Scope**: M5 (API & UI) enhancements informed by competitor best practices
**Timeline**: 16 weeks (4 months)

---

## Vision

Transform KAIROS from a functional lineage viewer into an **enterprise-grade metadata discovery and governance platform** by adopting proven UI/UX patterns from industry leaders while maintaining KAIROS differentiators (bitemporal lineage, evidence-based reasoning).

---

## Enhancement Tiers

### Tier 1: High Impact, Low Effort (Weeks 1-2)
**Ship quickly to build momentum**

- [ ] 1.1 Search result hover actions
- [ ] 1.2 Tab content counts
- [ ] 1.3 Better node labels in lineage graph
- [ ] 1.4 Pagination controls on search
- [ ] 1.5 Result metadata preview cards

### Tier 2: High Impact, Medium Effort (Weeks 3-6)
**Foundation for governance features**

- [ ] 2.1 Owner/Steward assignment UI
- [ ] 2.2 Inline metadata editing
- [ ] 2.3 Entity action menu
- [ ] 2.4 Quick copy actions
- [ ] 2.5 Audit trail display

### Tier 3: Critical, Blocked Features (Weeks 7-10)
**Requires M4 completion**

- [ ] 3.1 Data quality scorecard
- [ ] 3.2 Quality dimension breakdown
- [ ] 3.3 Issues & alerts panel
- [ ] 3.4 Quality certifications display
- [ ] 3.5 Trend visualization

### Tier 4: Extended Lineage (Weeks 11-14)
**Advanced data flow visualization**

- [ ] 4.1 Column-level lineage toggle
- [ ] 4.2 Path highlighting on interaction
- [ ] 4.3 Relationship type filtering
- [ ] 4.4 Impact radius visualization
- [ ] 4.5 Downstream propagation analysis

### Tier 5: Discovery & Personalization (Weeks 15-16)
**Nice-to-have features**

- [ ] 5.1 Recently viewed carousel
- [ ] 5.2 Starred/favorited items
- [ ] 5.3 Search history
- [ ] 5.4 Quick links dashboard (optional)

---

## Detailed Feature Breakdown

## **TIER 1: High Impact, Low Effort (Weeks 1-2)**

### 1.1 Search Result Hover Actions

**What**: Quick action buttons appear on search result cards when hovering

**Why**: Reduces clicks to perform common operations (open, copy, save)

**Scope**:
- Open in new window
- Copy entity ID
- Copy entity name
- Add to favorites (backend tracking)

**Implementation**:
```tsx
// SearchResultCard.tsx
export const SearchResultCard = ({ result }) => {
  return (
    <Card onMouseEnter={() => setShowActions(true)}>
      <CardContent>{result.name}</CardContent>
      {showActions && (
        <ActionButtons>
          <Button icon="open" onClick={() => navigate(...)} />
          <Button icon="copy-id" onClick={() => copyToClipboard(result.id)} />
          <Button icon="star" onClick={() => toggleFavorite(result.id)} />
        </ActionButtons>
      )}
    </Card>
  );
};
```

**Backend Changes**: Track favorites in new endpoint `POST /api/v1/assets/{id}/favorites`

**Effort**: 1-2 days

**Impact**: ⭐⭐⭐ High (improves UX significantly)

---

### 1.2 Tab Content Counts

**What**: Show count of items in each tab (e.g., "Lineage (5)", "Evidence (3)")

**Why**: Users know what to expect without opening tab

**Scope**:
- Count nodes in lineage graph
- Count evidence records
- Count relationships

**Implementation**:
```tsx
// EntityPage.tsx
const tabCounts = {
  lineage: lineageData?.nodes?.length || 0,
  evidence: evidenceData?.records?.length || 0,
  relationships: relationshipData?.items?.length || 0,
};

<Tabs>
  <Tab label={`Lineage (${tabCounts.lineage})`} />
  <Tab label={`Evidence (${tabCounts.evidence})`} />
  <Tab label={`Relationships (${tabCounts.relationships})`} />
</Tabs>
```

**Backend Changes**: None (use existing endpoints)

**Effort**: 1-2 days

**Impact**: ⭐⭐ Medium (nice-to-have)

---

### 1.3 Better Node Labels in Lineage Graph

**What**: Improve readability of node labels (truncation, tooltips, sizing)

**Why**: Large graphs become unreadable with small labels

**Scope**:
- Dynamic text truncation based on node size
- Tooltips on hover show full name
- Icons to indicate entity type
- Better font sizing for readability

**Implementation**:
```tsx
// LineageNode.tsx
const NodeLabel = ({ node, isSelected }) => {
  const maxLength = isSelected ? 50 : 15;
  const label = node.name.length > maxLength 
    ? node.name.substring(0, maxLength) + '...' 
    : node.name;
  
  return (
    <Title title={node.name}> {/* Full name in tooltip */}
      {getEntityIcon(node.type)} {label}
    </Title>
  );
};
```

**Backend Changes**: None

**Effort**: 2-3 days

**Impact**: ⭐⭐⭐ High (improves usability)

---

### 1.4 Pagination Controls on Search

**What**: Add previous/next buttons and "go to page" input

**Why**: Large result sets need navigation

**Scope**:
- Current/total page display
- Previous/Next buttons
- "Jump to page" input
- Results per page selector (10, 25, 50)

**Implementation**:
```tsx
// SearchPage.tsx - already has pagination, just improve UI
<PaginationControls>
  <Button 
    disabled={page === 1} 
    onClick={() => setPage(page - 1)}
  >
    Previous
  </Button>
  <Input 
    type="number" 
    value={page} 
    onChange={(p) => setPage(p)}
    min={1}
    max={totalPages}
  />
  <Text>of {totalPages}</Text>
  <Button 
    disabled={page === totalPages}
    onClick={() => setPage(page + 1)}
  >
    Next
  </Button>
</PaginationControls>
```

**Backend Changes**: None (use existing API)

**Effort**: 1 day

**Impact**: ⭐⭐ Medium

---

### 1.5 Result Metadata Preview Cards

**What**: Show key metadata on search result cards (owner, last updated, row count, tags)

**Why**: Better decision making before clicking

**Scope**:
- Owner name/avatar
- Last updated timestamp
- Data size / row count
- Tags/classifications
- Quality indicator (if M4 available)

**Implementation**:
```tsx
// SearchResultCard.tsx
export const SearchResultCard = ({ result }) => {
  return (
    <Card>
      <Header>
        <EntityIcon type={result.type} />
        <Title>{result.name}</Title>
        <Environment>{result.environment}</Environment>
      </Header>
      <Metadata>
        <MetadataItem icon="user" label="Owner" value={result.owner} />
        <MetadataItem icon="calendar" label="Updated" value={formatTime(result.updatedAt)} />
        <MetadataItem icon="database" label="Rows" value={formatNumber(result.rowCount)} />
        <MetadataItem icon="tag" label="Tags" value={result.tags.join(', ')} />
      </Metadata>
    </Card>
  );
};
```

**Backend Changes**: Ensure API returns all metadata (already does via GET /api/v1/assets/{id})

**Effort**: 2-3 days

**Impact**: ⭐⭐⭐ High (improves discovery)

---

## **TIER 2: High Impact, Medium Effort (Weeks 3-6)**

### 2.1 Owner/Steward Assignment UI

**What**: Dropdown selectors to assign Owner, Steward, Reviewer roles

**Why**: Governance requirement - clear accountability

**Scope**:
- Owner selector (single or multiple)
- Steward selector (multiple)
- Reviewer selector (multiple)
- Role-based permissions
- Save changes to backend
- Audit logging

**Implementation**:

```tsx
// OwnershipEditor.tsx
export const OwnershipEditor = ({ asset, onSave, isEditable }) => {
  const [owner, setOwner] = useState(asset.owner);
  const [stewards, setStewards] = useState(asset.stewards || []);
  
  const handleSave = async () => {
    await api.updateAsset(asset.id, {
      owner: owner.id,
      stewards: stewards.map(s => s.id),
    });
    onSave();
  };
  
  return (
    <Section>
      <Field label="Owner" required>
        <UserSelector 
          value={owner}
          onChange={setOwner}
          readOnly={!isEditable}
        />
      </Field>
      
      <Field label="Stewards">
        <UserMultiSelect
          values={stewards}
          onChange={setStewards}
          readOnly={!isEditable}
          maxSelections={5}
        />
      </Field>
      
      {isEditable && (
        <ActionButtons>
          <Button onClick={handleSave}>Save</Button>
          <Button onClick={onCancel} variant="secondary">Cancel</Button>
        </ActionButtons>
      )}
    </Section>
  );
};
```

**Backend Changes**:
```
PATCH /api/v1/assets/{id}
Body: {
  owner: "user-id",
  stewards: ["user-id-1", "user-id-2"]
}

Returns: Updated asset with audit log
```

**Dependencies**:
- User management/directory API (LDAP, Okta, internal)
- Permission system (who can edit owner?)

**Effort**: 3-4 weeks (includes permission system)

**Impact**: ⭐⭐⭐⭐ Critical (governance foundation)

---

### 2.2 Inline Metadata Editing

**What**: Click pencil icon to edit field values directly

**Why**: Faster than modal dialogs, less disruptive

**Scope**:
- Edit Description
- Edit Owner (via selector)
- Edit Tags
- Edit Business Glossary terms
- Change frequency / SLA
- Permission checks per field

**Implementation**:

```tsx
// EditableField.tsx
export const EditableField = ({ 
  label, 
  value, 
  onSave, 
  editable = true,
  multiline = false 
}) => {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value);
  
  if (!editing) {
    return (
      <Field>
        <Label>{label}</Label>
        <DisplayValue>{value || '—'}</DisplayValue>
        {editable && (
          <EditButton onClick={() => setEditing(true)}>✎</EditButton>
        )}
      </Field>
    );
  }
  
  return (
    <Field>
      <Label>{label}</Label>
      <Input
        value={tempValue}
        onChange={(e) => setTempValue(e.target.value)}
        multiline={multiline}
        autoFocus
      />
      <ButtonGroup>
        <Button onClick={() => {
          onSave(tempValue);
          setEditing(false);
        }}>Save</Button>
        <Button onClick={() => setEditing(false)} variant="secondary">Cancel</Button>
      </ButtonGroup>
    </Field>
  );
};

// Usage in EntityPage
<EditableField
  label="Description"
  value={entity.description}
  onSave={(desc) => updateEntity({ description: desc })}
  multiline
/>
```

**Backend Changes**:
```
PATCH /api/v1/assets/{id}
Body: {
  description: "New description",
  owner: "new-owner-id",
  tags: ["tag1", "tag2"]
}

Audit: Log who changed what and when
```

**Effort**: 2-3 weeks

**Impact**: ⭐⭐⭐⭐ High (improves metadata quality)

---

### 2.3 Entity Action Menu

**What**: More/options menu (⋮) with additional actions

**Why**: Keep UI clean while providing advanced options

**Scope**:
- Edit Description
- Change Owner
- Add Tags
- Export Metadata
- Share Link
- View Audit Trail
- Delete/Archive

**Implementation**:

```tsx
// EntityActionMenu.tsx
export const EntityActionMenu = ({ entity }) => {
  return (
    <DropdownMenu>
      <MenuButton title="Actions">⋮</MenuButton>
      <MenuItems>
        <MenuItem onClick={editDescription}>Edit Description</MenuItem>
        <MenuItem onClick={changeOwner}>Change Owner</MenuItem>
        <MenuItem onClick={addTags}>Add Tags</MenuItem>
        <Separator />
        <MenuItem onClick={exportMetadata}>Export Metadata</MenuItem>
        <MenuItem onClick={shareLink}>Share Link</MenuItem>
        <MenuItem onClick={viewAuditTrail}>View Audit Trail</MenuItem>
        <Separator />
        <MenuItem variant="danger" onClick={deleteEntity}>Delete</MenuItem>
      </MenuItems>
    </DropdownMenu>
  );
};
```

**Effort**: 1-2 weeks

**Impact**: ⭐⭐⭐ High (organized UX)

---

### 2.4 Quick Copy Actions

**What**: Copy buttons for common values (ID, Name, Full Path)

**Why**: Users often need to copy identifiers for scripting/reporting

**Scope**:
- Copy asset ID
- Copy asset name
- Copy full path (schema.table)
- Copy connection string (if applicable)
- Visual feedback ("Copied!")

**Implementation**:

```tsx
// CopyButton.tsx
export const CopyButton = ({ value, label = "Copy" }) => {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <Button 
      onClick={handleCopy}
      variant="ghost"
      title={value}
    >
      {copied ? '✓ Copied!' : `📋 ${label}`}
    </Button>
  );
};

// Usage in EntityPage
<Header>
  <Title>{entity.name}</Title>
  <CopyButton value={entity.id} label="Copy ID" />
  <CopyButton value={entity.name} label="Copy Name" />
  <CopyButton 
    value={`${entity.database}.${entity.schema}.${entity.name}`}
    label="Copy Path"
  />
</Header>
```

**Effort**: 1 week

**Impact**: ⭐⭐⭐ High (improves daily workflows)

---

### 2.5 Audit Trail Display

**What**: Show who changed what and when

**Why**: Governance/compliance requirement

**Scope**:
- Timeline of changes
- Show field, old value, new value
- User who made change
- Timestamp
- Reason/comment (if provided)

**Implementation**:

```tsx
// AuditTrail.tsx
export const AuditTrail = ({ assetId }) => {
  const { data: auditEvents } = useQuery(
    ['audit', assetId],
    () => api.getAuditTrail(assetId)
  );
  
  return (
    <Section title="Audit Trail">
      <Timeline>
        {auditEvents?.map(event => (
          <TimelineItem key={event.id}>
            <Timestamp>{formatTime(event.timestamp)}</Timestamp>
            <User>{event.user.name}</User>
            <Change>
              Changed <Field>{event.field}</Field> from 
              <OldValue>{event.oldValue}</OldValue> to 
              <NewValue>{event.newValue}</NewValue>
            </Change>
            {event.reason && <Reason>Reason: {event.reason}</Reason>}
          </TimelineItem>
        ))}
      </Timeline>
    </Section>
  );
};
```

**Backend Changes**:
```
GET /api/v1/assets/{id}/audit
Returns: [
  {
    id: string,
    timestamp: ISO8601,
    user: { id, name, email },
    field: string,
    oldValue: any,
    newValue: any,
    reason?: string
  }
]
```

**Effort**: 1-2 weeks

**Impact**: ⭐⭐⭐ High (compliance support)

---

## **TIER 3: Critical, Blocked Features (Weeks 7-10)**

*Requires M4 (Dependency Reasoning) completion*

### 3.1 Data Quality Scorecard

**What**: Display overall quality score (0-100%) with color indicator

**Why**: At-a-glance data health assessment

**Scope**:
- Overall quality score
- Color indicator (🟢 Good, 🟡 Warning, 🔴 Critical)
- Last evaluated timestamp
- Link to quality details

**Implementation**:

```tsx
// QualityScorecard.tsx
export const QualityScorecard = ({ asset }) => {
  const quality = asset.quality;
  
  const statusColor = 
    quality.score >= 80 ? 'green' :
    quality.score >= 60 ? 'yellow' :
    'red';
  
  return (
    <Card>
      <Title>Data Quality</Title>
      <ScoreDisplay>
        <Score color={statusColor}>{quality.score}%</Score>
        <ScoreBar value={quality.score} />
      </ScoreDisplay>
      <Metadata>
        <Item label="Last Evaluated" value={formatTime(quality.timestamp)} />
        <Item label="Issues" value={quality.issueCount} />
      </Metadata>
      <Link href={`/assets/${asset.id}/quality`}>View Details →</Link>
    </Card>
  );
};
```

**Backend Changes**: M4 provides quality scores via existing endpoint

**Effort**: 1-2 weeks (mostly UI, data from M4)

**Impact**: ⭐⭐⭐⭐ Critical (governance visibility)

---

### 3.2 Quality Dimension Breakdown

**What**: Show quality across multiple dimensions (Completeness, Accuracy, Timeliness, etc.)

**Why**: Different issues have different severity/impact

**Scope**:
- Completeness %
- Accuracy %
- Timeliness %
- Validity %
- Uniqueness %
- Each with color indicator

**Implementation**:

```tsx
// QualityDimensions.tsx
export const QualityDimensions = ({ asset }) => {
  const dimensions = asset.quality.dimensions || [];
  
  return (
    <Section title="Quality Dimensions">
      <Grid columns={2}>
        {dimensions.map(dim => (
          <DimensionCard key={dim.name}>
            <DimensionName>{dim.name}</DimensionName>
            <Score color={getColor(dim.score)}>
              {dim.score}%
            </Score>
            <ScoreBar value={dim.score} />
            <Status>{getStatus(dim.score)}</Status>
          </DimensionCard>
        ))}
      </Grid>
    </Section>
  );
};
```

**Effort**: 1 week

**Impact**: ⭐⭐⭐⭐ High (detailed insights)

---

### 3.3 Issues & Alerts Panel

**What**: List of specific quality issues with drill-down

**Why**: Users know exactly what needs fixing

**Scope**:
- Issue severity (Critical, Warning, Info)
- Issue type (Duplicate, NULL, Mismatch, etc.)
- Affected rows/columns
- Recommended action

**Implementation**:

```tsx
// QualityIssues.tsx
export const QualityIssues = ({ asset }) => {
  const issues = asset.quality.issues || [];
  const criticalCount = issues.filter(i => i.severity === 'critical').length;
  
  return (
    <Section title={`Quality Issues (${criticalCount} critical)`}>
      <IssueList>
        {issues.map(issue => (
          <IssueCard key={issue.id} severity={issue.severity}>
            <IssueSeverity>{issue.severity.toUpperCase()}</IssueSeverity>
            <IssueType>{issue.type}</IssueType>
            <IssueDescription>{issue.description}</IssueDescription>
            <IssueImpact>
              Affects {issue.rowCount} rows ({issue.percentage}%)
            </IssueImpact>
            <IssueAction>{issue.recommendedAction}</IssueAction>
            <MoreButton onClick={() => showDetails(issue.id)}>Details →</MoreButton>
          </IssueCard>
        ))}
      </IssueList>
    </Section>
  );
};
```

**Effort**: 2 weeks

**Impact**: ⭐⭐⭐⭐ Critical (actionable insights)

---

### 3.4 Quality Certifications Display

**What**: Show if data has been certified (verified by governance team)

**Why**: Indicates trustworthiness / approval

**Scope**:
- Certification badge (✅)
- Certifier name/team
- Certification date
- Expiration date (if applicable)
- Uncertify button (admin only)

**Implementation**:

```tsx
// CertificationBadge.tsx
export const CertificationBadge = ({ certification, isAdmin }) => {
  if (!certification) {
    return <CertifyButton>Request Certification</CertifyButton>;
  }
  
  return (
    <Badge status="certified">
      <Icon>✅</Icon>
      <Text>Certified by {certification.certifier}</Text>
      <Date>{formatDate(certification.date)}</Date>
      {isAdmin && (
        <Button onClick={uncertify} variant="ghost">Remove</Button>
      )}
    </Badge>
  );
};
```

**Effort**: 1-2 weeks

**Impact**: ⭐⭐⭐ High (governance support)

---

### 3.5 Trend Visualization

**What**: Show quality score trend over time (chart)

**Why**: Users see if quality is improving or degrading

**Scope**:
- Line chart showing score over past 30/90 days
- Comparison with previous period
- Alerts for significant drops

**Implementation**:

```tsx
// QualityTrend.tsx
import { LineChart, Line, XAxis, YAxis } from 'recharts';

export const QualityTrend = ({ asset }) => {
  const trendData = asset.quality.trend || [];
  const currentScore = trendData[trendData.length - 1]?.score;
  const previousScore = trendData[0]?.score;
  const change = ((currentScore - previousScore) / previousScore * 100).toFixed(1);
  
  return (
    <Section title="Quality Trend">
      <TrendMetrics>
        <Metric>
          <Label>30-Day Change</Label>
          <Value change={change}>{change > 0 ? '+' : ''}{change}%</Value>
        </Metric>
      </TrendMetrics>
      <Chart>
        <LineChart data={trendData}>
          <XAxis dataKey="date" />
          <YAxis domain={[0, 100]} />
          <Line type="monotone" dataKey="score" stroke="#2563eb" />
        </LineChart>
      </Chart>
    </Section>
  );
};
```

**Effort**: 1-2 weeks

**Impact**: ⭐⭐⭐ High (strategic insights)

---

## **TIER 4: Extended Lineage (Weeks 11-14)**

### 4.1 Column-Level Lineage Toggle

**What**: Toggle between dataset-level and column-level lineage graphs

**Why**: Fine-grained understanding of data transformations

**Scope**:
- Toggle button in lineage toolbar
- Column nodes show individual columns
- Aggregated view shows tables only
- Maintains zoom/pan position

**Implementation**:

```tsx
// LineageCanvas.tsx
export const LineageCanvas = ({ entity }) => {
  const [granularity, setGranularity] = useState('dataset');
  
  const graphData = granularity === 'dataset'
    ? formatDatasetLineage(entity)
    : formatColumnLineage(entity);
  
  return (
    <Container>
      <Toolbar>
        <Button
          active={granularity === 'dataset'}
          onClick={() => setGranularity('dataset')}
        >
          Dataset Level
        </Button>
        <Button
          active={granularity === 'column'}
          onClick={() => setGranularity('column')}
        >
          Column Level
        </Button>
      </Toolbar>
      <D3Graph data={graphData} />
    </Container>
  );
};
```

**Backend Changes**: Already supports via `?granularity=COLUMN` parameter

**Effort**: 2-3 weeks

**Impact**: ⭐⭐⭐⭐ Critical (core KAIROS feature)

---

### 4.2 Path Highlighting on Interaction

**What**: When user clicks a path, highlight it and dim non-relevant edges

**Why**: Reduces visual clutter in large graphs

**Scope**:
- Click source node
- Click target node
- Show path from source to target
- Highlight nodes and edges in path
- Dim others

**Implementation**:

```tsx
// LineageCanvas.tsx - updated
export const LineageCanvas = ({ entity }) => {
  const [selectedPath, setSelectedPath] = useState(null);
  
  const handleNodeClick = (nodeId) => {
    if (!selectedPath || selectedPath.target !== nodeId) {
      const path = findPath(graph, selectedPath?.source || nodeId, nodeId);
      setSelectedPath({ source: selectedPath?.source || nodeId, target: nodeId, path });
    } else {
      setSelectedPath(null);
    }
  };
  
  const nodeOpacity = (nodeId) => 
    !selectedPath || selectedPath.path.includes(nodeId) ? 1 : 0.2;
  
  const edgeOpacity = (sourceId, targetId) =>
    !selectedPath || selectedPath.path.includes(`${sourceId}-${targetId}`) ? 1 : 0.1;
  
  return (
    <D3Graph
      data={graphData}
      onNodeClick={handleNodeClick}
      nodeOpacity={nodeOpacity}
      edgeOpacity={edgeOpacity}
    />
  );
};
```

**Effort**: 2-3 weeks

**Impact**: ⭐⭐⭐⭐ High (UX improvement)

---

### 4.3 Relationship Type Filtering

**What**: Toggle visibility of different relationship types (lineage, business, impact)

**Why**: Users can focus on specific relationship types

**Scope**:
- Checkbox filters for relationship types
- Lineage (technical data flow)
- Business Context (glossary terms, etc.)
- Impact (downstream propagation)

**Implementation**:

```tsx
// LineageFilters.tsx
export const LineageFilters = ({ activeTypes, onChange }) => {
  return (
    <FilterPanel>
      <Label>Relationship Types</Label>
      <Checkbox
        checked={activeTypes.includes('lineage')}
        onChange={() => toggleType('lineage')}
      >
        Lineage (Data Flow)
      </Checkbox>
      <Checkbox
        checked={activeTypes.includes('business')}
        onChange={() => toggleType('business')}
      >
        Business Context
      </Checkbox>
      <Checkbox
        checked={activeTypes.includes('impact')}
        onChange={() => toggleType('impact')}
      >
        Impact (Downstream)
      </Checkbox>
    </FilterPanel>
  );
};
```

**Effort**: 1-2 weeks

**Impact**: ⭐⭐⭐ High (flexibility)

---

### 4.4 Impact Radius Visualization

**What**: Show how many nodes are downstream from current entity

**Why**: Users understand risk/scope of changes

**Scope**:
- Badge on node showing downstream count
- Highlight downstream nodes on hover
- Show propagation depth

**Implementation**:

```tsx
// LineageNode.tsx - enhanced
export const LineageNode = ({ node, impactRadius, onHover }) => {
  const downstreamCount = impactRadius?.[node.id] || 0;
  
  return (
    <Group onMouseEnter={() => onHover(node.id)}>
      <NodeShape status={node.status} />
      <NodeLabel>{node.name}</NodeLabel>
      {downstreamCount > 0 && (
        <ImpactBadge title={`${downstreamCount} downstream nodes`}>
          {downstreamCount}
        </ImpactBadge>
      )}
    </Group>
  );
};
```

**Effort**: 1-2 weeks

**Impact**: ⭐⭐⭐ High (strategic view)

---

### 4.5 Downstream Propagation Analysis

**What**: Show full impact of changes to an entity

**Why**: Users understand change scope before modification

**Scope**:
- Show all downstream entities
- Show propagation depth (1st, 2nd, 3rd level)
- Color code by distance
- Show transformation logic (if available)

**Implementation**:

```tsx
// DownstreamImpact.tsx
export const DownstreamImpact = ({ entity }) => {
  const { data: impact } = useQuery(
    ['impact', entity.id],
    () => api.getDownstreamImpact(entity.id)
  );
  
  return (
    <Section title="Downstream Impact">
      <ImpactTree>
        {impact?.levels.map((level, depth) => (
          <Level key={depth} depth={depth}>
            <LevelLabel>Level {depth + 1} ({level.nodes.length} entities)</LevelLabel>
            <NodeList>
              {level.nodes.map(node => (
                <ImpactNode key={node.id} depth={depth}>
                  <NodeName>{node.name}</NodeName>
                  <TransformationType>{node.transformationType}</TransformationType>
                </ImpactNode>
              ))}
            </NodeList>
          </Level>
        ))}
      </ImpactTree>
    </Section>
  );
};
```

**Backend Changes**:
```
GET /api/v1/assets/{id}/downstream-impact
Returns: {
  levels: [
    { nodes: [...], depth: 1 },
    { nodes: [...], depth: 2 },
    ...
  ],
  totalAffected: number
}
```

**Effort**: 2-3 weeks

**Impact**: ⭐⭐⭐⭐ Critical (risk assessment)

---

## **TIER 5: Discovery & Personalization (Weeks 15-16)**

### 5.1 Recently Viewed Carousel

**What**: Show recently accessed assets at top of search/dashboard

**Why**: Quick access to frequently used entities

**Scope**:
- Track asset views in localStorage/backend
- Show 5-10 most recent
- Click to open
- Clear history option

**Implementation**:

```tsx
// RecentlyViewed.tsx
export const RecentlyViewed = () => {
  const { data: recent } = useQuery(
    ['recently-viewed'],
    () => api.getRecentlyViewed(10),
    { staleTime: 1000 * 60 * 60 } // Cache 1 hour
  );
  
  if (!recent?.length) return null;
  
  return (
    <Carousel title="Recently Viewed">
      {recent.map(asset => (
        <CarouselItem key={asset.id}>
          <EntityCard
            entity={asset}
            onClick={() => navigate(`/assets/${asset.id}`)}
          />
        </CarouselItem>
      ))}
      <CarouselAction onClick={clearHistory}>Clear</CarouselAction>
    </Carousel>
  );
};
```

**Backend Changes**:
```
GET /api/v1/me/recently-viewed?limit=10
POST /api/v1/me/recently-viewed/{assetId}
DELETE /api/v1/me/recently-viewed
```

**Effort**: 1 week

**Impact**: ⭐⭐ Medium (convenience)

---

### 5.2 Starred/Favorited Items

**What**: Users can star entities to create personal shortcuts

**Why**: Personalization, quick access to important entities

**Scope**:
- Star icon in search results and entity header
- Show starred items in dashboard/sidebar
- Filter search by starred only
- Sync across sessions

**Implementation**:

```tsx
// StarButton.tsx
export const StarButton = ({ assetId, isStarred, onToggle }) => {
  const [loading, setLoading] = useState(false);
  
  const handleToggle = async () => {
    setLoading(true);
    try {
      if (isStarred) {
        await api.unstarAsset(assetId);
      } else {
        await api.starAsset(assetId);
      }
      onToggle(!isStarred);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Button
      onClick={handleToggle}
      disabled={loading}
      title={isStarred ? 'Unstar' : 'Star'}
    >
      {isStarred ? '⭐' : '☆'}
    </Button>
  );
};
```

**Backend Changes**:
```
POST /api/v1/assets/{id}/star
DELETE /api/v1/assets/{id}/star
GET /api/v1/me/starred-assets
```

**Effort**: 1-2 weeks

**Impact**: ⭐⭐ Medium (personalization)

---

### 5.3 Search History

**What**: Show previous searches for quick re-run

**Why**: Users often repeat similar searches

**Scope**:
- Track search queries
- Show recent searches in dropdown
- One-click re-run
- Clear history option

**Implementation**:

```tsx
// SearchHistoryDropdown.tsx
export const SearchHistoryDropdown = () => {
  const [history, setHistory] = useState(
    JSON.parse(localStorage.getItem('searchHistory') || '[]')
  );
  
  const handleSelectHistory = (query) => {
    onSearch(query);
    addToHistory(query);
  };
  
  return (
    <Dropdown>
      <DropdownTitle>Recent Searches</DropdownTitle>
      {history.map((query, idx) => (
        <DropdownItem key={idx} onClick={() => handleSelectHistory(query)}>
          {query}
        </DropdownItem>
      ))}
      <DropdownSeparator />
      <DropdownAction onClick={() => clearHistory()}>
        Clear History
      </DropdownAction>
    </Dropdown>
  );
};

// Track searches
const addToHistory = (query) => {
  const history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
  const updated = [query, ...history.filter(q => q !== query)].slice(0, 10);
  localStorage.setItem('searchHistory', JSON.stringify(updated));
};
```

**Effort**: 1 week

**Impact**: ⭐⭐ Medium (convenience)

---

## Implementation Timeline

### Summary by Week

```
Week 1-2:   Tier 1 (5 features) - Foundation
            - Search hover actions
            - Tab counts
            - Better node labels
            - Pagination UI
            - Metadata preview cards

Week 3-6:   Tier 2 (5 features) - Governance
            - Owner/Steward assignment
            - Inline editing
            - Action menu
            - Copy buttons
            - Audit trail

Week 7-10:  Tier 3 (5 features) - Quality (blocked on M4)
            - Quality scorecard
            - Quality dimensions
            - Issues panel
            - Certifications
            - Trend visualization

Week 11-14: Tier 4 (5 features) - Advanced Lineage
            - Column-level toggle
            - Path highlighting
            - Relationship filtering
            - Impact radius
            - Downstream propagation

Week 15-16: Tier 5 (3 features) - Discovery
            - Recently viewed
            - Starred items
            - Search history
```

---

## Success Metrics

### Tier 1 Metrics
- Search result click-through rate ↑ 20%
- Time to find asset ↓ 30%
- User satisfaction: Improve to 4.2/5

### Tier 2 Metrics
- Owner assignment rate ↑ 80%
- Edit frequency ↑ (governance updates)
- Metadata completeness ↑ 60%

### Tier 3 Metrics (after M4)
- Quality-aware decisions ↑
- Data quality improvement ↑
- Governance compliance ↑

### Tier 4 Metrics
- Column lineage usage ↑
- Impact analysis usage ↑
- Change risk assessment ↑

### Tier 5 Metrics
- Recently viewed usage ↑
- Star/favorite rate ↑
- Search repeat reduction ↓

---

## Dependencies & Blockers

### Must Have Before Tier 3
- ✅ M4 (Dependency Reasoning) - CRITICAL
- ✅ M2 (Data Storage) - for temporal context

### Must Have Before Tier 2
- ✅ User/Permission system
- ✅ Audit logging system

### Optional but Recommended
- User directory (LDAP/Okta)
- Analytics/telemetry
- Feature flag system

---

## Adoption Strategy

### Phase 1: Internal Beta (Week 1-2)
- Deploy Tier 1 features
- Internal team testing
- Gather feedback
- Iterate based on UX issues

### Phase 2: Early Adopters (Week 3-6)
- Beta release to select users
- Monitor adoption
- Collect feature requests
- Plan Tier 2 prioritization

### Phase 3: General Availability (Week 7+)
- Roll out each tier to all users
- Monitor usage metrics
- Support & training
- Continuous iteration

---

## Risk Mitigation

### Technical Risks
- **Large lineage graphs cause performance issues**: Use virtualization, pagination
- **API rate limits**: Implement caching, debouncing
- **Permission system delays**: Stub with simple owner-only model initially

### User Risks
- **UI changes cause confusion**: Provide in-app help tooltips, documentation
- **New features go unused**: Track adoption, provide training
- **Data quality metrics misinterpreted**: Add clear explanations, certification process

---

## Next Steps

1. **Approve Roadmap** - Get stakeholder sign-off
2. **Plan Tier 1** - Break into stories for sprint planning
3. **Design Tier 1 UX** - Mockups and prototype
4. **Develop Tier 1** - Build and test
5. **Deploy & Monitor** - Release and gather feedback
6. **Plan Tier 2** - Based on Tier 1 learnings

---

## References

- [KAIROS Architecture](../KAIROS_CLAUDE_CONTEXT.md)
- [Competitor Pattern Analysis](./COMPETITOR_PATTERN_ANALYSIS.md)
- [UI Patterns Synthesis](./UI_PATTERNS_SYNTHESIS.md)
- [Atlan Pattern Analysis](./ATLAN_PATTERN_ANALYSIS.md)
- [REA Integration](./REA_INTEGRATION.md)

---

**Prepared by**: KAIROS Enhancement Team  
**Date**: September 23, 2026  
**Version**: 1.0  
**Status**: Ready for Implementation
