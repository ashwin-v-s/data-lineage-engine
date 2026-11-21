# KAIROS — Master Presentation Flow

One coherent 15-minute journey. Everything below was executed; the two steps
marked **LIMITED** must be phrased honestly (see the guide for wording).

**Before the audience arrives (5 min):** open the app, sign in, land on
**Home**, wait for **LIVE**, open **Lineage** once so the graph is warm, then
return to **Home**. Keep a second tab on `/docs` (OpenAPI) for proof questions.

| Time | Beat | Where | What you say / do | Depends on |
| --- | --- | --- | --- | --- |
| 0:00 | Frame the problem | Home | "Metadata platforms tell you what tables exist. Kairos also tells you **how sure it is**, and why." Point at the provenance badge: LIVE. | session |
| 1:00 | Identity & tenancy | sidebar bottom | "Sign-in is Supabase; every query below is scoped to this workspace by row-level security, not by the UI." | `/me/workspaces` |
| 2:00 | The estate | Home → All assets | Open the asset table, filter `fct`, show columns count and owners. Mention that synthetic demo data models a revenue stack. | catalog |
| 4:00 | Ingestion | Operations → Import metadata | Show the five fixture families. Explain preview (no writes) → commit (atomic) → idempotent replay. If you cannot use the file picker live, show `POST /api/v1/ingest/commit` and the resulting `import_id`. | ingest API |
| 6:00 | Dataset lineage | Lineage | Start at `fct_daily_revenue`, expand to sources and the executive dashboard. 8 nodes / 8 edges. Click one edge, open its evidence. | edges + evidence |
| 8:00 | Evidence reasoning | Evidence & reasoning | Four states. "Static imports are DECLARED, runtime events are OBSERVED, absence is UNKNOWN, never a fabricated edge." | evidence rows |
| 9:00 | Governance | Domains → Glossary → Data products | Domain `Finance & Revenue`; term `GMV` APPROVED and linked to the mart; product `Executive Revenue Intelligence` bundling the mart and the KPI. | governance APIs |
| 11:00 | Quality & freshness | Data quality, Freshness | **LIMITED (quality):** show the assertion + PASS result and explain the panel wiring gap. Freshness SLA 48/60/120 min, status UNKNOWN without a runtime signal. | quality_result, freshness_sla |
| 12:30 | Operations & trust | Workspace administration | Members and roles, invite form, owner protection, audit events. Mention API keys and webhooks exist. | membership |
| 13:30 | Search & 3D | Catalog search, 3D observatory | Search `revenue` (13 hits); open the observatory as the optional spatial view of the same graph. | search |
| 14:30 | Close | Home | "Everything you saw came from one catalog contract; the limits are stated in the product, not hidden." | — |

## Alternate tracks

**If the audience is technical (engineers):** spend 4 minutes on the ingestion
contract and idempotency, then lineage evidence, then finish with the defect
list (`KAIROS_END_TO_END_TEST_REPORT.md` §7) — it demonstrates engineering
honesty and gives them something to review.

**If the audience is governance/compliance:** Sign-in → Domains → Glossary →
Data products → PII classification → Evidence & reasoning → Quality →
Administration. Skip ingestion internals; describe it in one sentence.

**If something fails live:** keep the API and database tabs open. Every claim in
the flow can be reproduced with a `GET /api/v1/...` call and, for the demo
workspace, a database row id listed in the data catalog.

## Feature dependencies (do not reorder)

```
sign-in ──► workspace context ──► catalog ──► lineage ──► edge evidence
                                      │
                                      ├─► search / observatory
                                      ├─► governance (needs catalog assets)
                                      ├─► quality (needs a dataset id)
                                      └─► freshness (needs a dataset id)
```

- Governance forms populate their dataset pickers from `/catalog`; if the
  catalog is empty the forms are unusable.
- Quality and freshness both take a dataset id, so they follow the catalog.
- Incidents and notifications depend on freshness evaluations, which depend on
  a runtime signal — do not schedule them before ingestion.

## Timing budget

| Segment | Minutes |
| --- | --- |
| Frame + identity | 2 |
| Catalog | 2 |
| Ingestion | 2 |
| Lineage + evidence | 3 |
| Governance | 2 |
| Quality + freshness + ops | 2.5 |
| Search + observatory + close | 1.5 |

## Transitions (spoken bridges)

- Home → All assets: "That count is a summary; let's open the inventory behind it."
- All assets → Import: "Where did these rows come from? Here is the pipeline that wrote them."
- Import → Lineage: "A list of tables is not a system. The relationships are."
- Lineage → Evidence: "And a relationship is only as good as its evidence."
- Evidence → Governance: "Evidence tells us what is true; governance decides what it means."
- Governance → Quality/Freshness: "Meaning needs measurement."
- Quality → Admin: "Measurement needs owners."
- Admin → Close: "And owners need an audit trail — which is the audit feed you saw."

## Known limitations to state once, calmly

1. Column-level lineage is not yet produced by the adapters.
2. The Data quality panel does not yet consume stored results (API/DB proof only).
3. Time travel is empty for static evidence because imports carry no effective time.
4. Duplicate asset rows come from adapter type reconciliation, not from duplicate imports.
5. Sources, GitHub, OpenLineage, email and the scheduler need credentials not present in this deployment.
