# Data Lineage & Metadata Engine (Kairos): Final Architecture & Research Execution Pack

## Document Control and Status Legend

| Field | Value |
|---|---|
| Version | 1.0-pack-draft |
| Date | 2026-09-20 |
| Status | DRAFT FOR TEAM APPROVAL. Freeze only after all five members have read and approved it. |
| Audience | The five-person team (M1 to M5). Written to be readable by a second-year engineering student. |
| Canonical source | `docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md` (this Markdown file) |
| Derived copy | `docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.docx` (formatted for reading and sharing) |
| Source materials | Listed in Appendix B. The Kairos v1.0 Team Execution Contract is the primary source. |
| Pack owner | TBD (the team assigns one person to maintain this file) |

Every claim in this document carries, or sits under, one of these status labels.

| Label | Meaning |
|---|---|
| **LOCKED** | Changing it requires a written decision record (Section 48). |
| **PROVISIONAL** | Best current design. Isolated behind an interface. Not validated. |
| **PENDING TEAM DECISION** | Deliberately unresolved. The team must decide. Nothing here may invent the answer. |
| **TO BE VALIDATED** | A claim or capability that has not been tested in our environment. |
| **KNOWN PRIOR ART** | Established by earlier work. We do not claim it as ours. |
| **REJECTED** | Considered and dropped as currently framed. Kept on record. |
| **NOT IMPLEMENTED** | No code exists yet. |
| **EXPERIMENTALLY VALIDATED** | A defined experiment or test has passed. Nothing in this pack has this label yet. |
| **NOT YET MEASURED** | A number that will come from an experiment. It must never be filled in by guessing. |

> **Reading order.** Everyone reads Sections 1 to 19, 28 and 29 first. Then read your own section (30 to 34) and Sections 35 to 37. Read Sections 46 and 47 last: they list what is still open and where sources disagreed.

## 1. Executive Summary

Kairos is an open-source, self-hostable data lineage and metadata engine built as a university project. It has two separable parts.

- **Project A, historical lineage infrastructure.** It ingests lineage evidence, stores it in PostgreSQL with two time dimensions (valid time and transaction time), and answers questions such as "what was the lineage valid at time X, according to what we knew at time Y". This is engineering work. It must remain useful even if Project B fails. Status: **LOCKED** as a design, **NOT IMPLEMENTED** as code.
- **Project B, execution-conditioned reasoning.** It asks whether reasoning about coverage, static SQL semantics and incomplete runtime evidence reduces false conclusions about which dependencies actually occurred in one specific run, compared with simpler strategies. This is a research hypothesis. Status: **PROVISIONAL**. It is not a result.

A concrete example of the problem Project B studies:

```
CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary
```

Static analysis says both `country` and `salary` can affect `adjusted_salary`. If one particular run contains no US rows, `salary` did not actually contribute in that run. A runtime tool that saw no event for `salary` might wrongly conclude "no dependency", or might have simply missed the event. Kairos must be able to tell these situations apart, and must never treat "we saw nothing" as "it did not happen".

Where the project stands today:

| Area | Status |
|---|---|
| Design contract (Kairos v1.0 Team Execution Contract) | Exists as a draft. Freeze pending team approval. |
| Repository and code (migrations, parsers, ETL, API, UI, integration tests) | **NOT IMPLEMENTED**. The original repository was lost. |
| ProvSQL feasibility spike | **NOT YET MEASURED**. Result unavailable. |
| Benchmark SQL cases and `research/protocol/v1.yaml` | **NOT IMPLEMENTED** |
| Experiment outputs, statistics, performance numbers | **NOT YET MEASURED**. Any old numbers are self-reported and must not be reused. |
| Kill criteria thresholds | **PENDING TEAM DECISION** |
| Olist license check, team machine matrix | **PENDING TEAM DECISION** |

What this pack decides: the architecture, roles of each component, storage authority, interfaces, API shape, repository layout, team split, workflow, experiment structure and the order of work.

What this pack deliberately leaves open: numbers (thresholds, sample sizes, seeds), the ProvSQL outcome, the exact benchmark cases, environment choices and the graph library. Section 46 lists each one with a decision owner.

## 2. Project Scope

**In scope (MVP).**

- Historical lineage storage and queries with valid time and transaction time.
- Ingestion from three sources: SQL text (SQLGlot), OpenLineage runtime events, and a dbt `manifest.json`.
- Auditable, immutable raw evidence kept separate from derived reasoning results.
- Four-state execution-conditioned reasoning over a restricted deterministic SQL subset.
- A versioned API under `/api/v1` and a small research UI (staged, Section 19).
- A standalone research runner that works without the API, the UI or Neo4j.

**Out of scope unless reopened by a decision record.** Authentication UI, enterprise access control, Airflow integration, LLM or RAG features, graph neural networks, cloud deployment, Kubernetes, multiple graph stores, streaming orchestration, arbitrary SQL, outer joins (including LEFT JOIN) in the ground-truth-backed benchmark, dynamic SQL, window functions, UDFs, enterprise policy engines and a connector marketplace. Status: **LOCKED**.

**MVP ladder** (from the contract). Status: **LOCKED**.

| Step | Content |
|---|---|
| MVP-0 | Research core: fixtures, ground truth, loss simulator, baselines, metrics. No UI, API or Neo4j. |
| MVP-1 | PostgreSQL historical lineage. |
| MVP-2 | OpenLineage, SQLGlot and dbt ingestion. |
| MVP-3 | API. |
| MVP-4 | UI (Stage 1, Section 19). |
| MVP-5 | Integrated demo. |

If the research hypothesis fails, the team keeps everything in MVP-1 to MVP-5 that passes its engineering tests, removes superiority and novelty claims about the reasoning method, and reports the negative result with a failure analysis.

## 3. Research Question

> Can coverage-aware reasoning over static lineage and incomplete runtime evidence reduce false conclusions about execution-specific dependencies, compared with simpler lineage strategies (static-only, runtime-only, naive union)?

Status: **PROVISIONAL** hypothesis. **TO BE VALIDATED**. The question must not be changed after seeing data (Section 28).

Terminology rule: use "execution-specific dependency", "runtime contribution" and "execution-conditioned lineage". Do not use "causal" anywhere, because the method does not establish causality. Status: **LOCKED**.

## 4. Research Hypothesis

The central hypothesis is that, when runtime lineage evidence is incomplete, explicitly reasoning about observation coverage together with static transformation semantics reduces false conclusions compared with static-only, runtime-only or naive combination strategies.

Sub-hypotheses. All are **PROVISIONAL**, and none has been tested.

| ID | Statement | Compared against |
|---|---|---|
| H1 | Under incomplete observation, the proposed method has a lower false-refutation rate. | B2 (negative-assumption runtime-only) |
| H2 | The proposed method makes fewer false conclusions (false OBSERVED plus false REFUTED_FOR_RUN) than naive union. | B3 |
| H3 | Adding the active REFUTED_FOR_RUN state and the coverage gate improves outcomes over simpler state models. | B4 and B5 |
| H4 | Reasoning overhead is practical. The threshold comes from a pilot and is not assumed. | B2 latency |

> **Design note for the team.** B2 refutes anything not positively observed. H1 is therefore close to true by construction as loss increases. It is a sanity check, not strong evidence. The scientifically informative contrasts are B3, B4, B5 and the ablations (Section 25). Do not present a win over B2 as the main result.

Result classification (Supported, Inconclusive, Rejected) must be defined before any full run. The earlier specification proposed "consistent across at least 3 of 4 loss levels". The loss grid now has six levels (Section 22), so that rule no longer applies. The replacement rule is **PENDING TEAM DECISION** (D-05 in Section 46).

## 5. What Is Prior Art

Nothing in this table is claimed as our invention. Citations below were carried over from the project's earlier specification. Independent re-verification of each citation is **PENDING**: no team member has re-checked them in this rebuild.

| Concept | Status | Reference as recorded in the earlier specification |
|---|---|---|
| Bitemporal data and property graphs | **KNOWN PRIOR ART** | Rost et al., arXiv:2111.13499 (2021); a 2025 ADBIS paper extends it. |
| Point-in-time lineage in commercial tools | **KNOWN PRIOR ART** | Solidatus and Atlan document shipped features. |
| Per-node history of lineage | **KNOWN PRIOR ART** | AWS DataZone `ListLineageNodeHistory` (per node, not whole-graph). |
| Certain, possible and unknown answers over incomplete data | **KNOWN PRIOR ART** | Imielinski and Lipski (1984); Libkin, ACM TODS (2016), on SQL three-valued logic. |
| Tuple and cell provenance in SQL | **KNOWN PRIOR ART** | ProvSQL (PostgreSQL extension). Capabilities **TO BE VALIDATED** locally. |
| Static and runtime lineage, OpenLineage, SQL lineage extraction | **KNOWN PRIOR ART** | OpenLineage, SQLGlot, dbt. |
| Graph drift detection, lineage quality scoring, link prediction, lineage-as-code, CI validation, RAG or LLM provenance graphs | **KNOWN PRIOR ART** | Not pursued as contributions. |
| Structure-aware reconciliation of conflicting lineage | **REJECTED** as a contribution | An earlier prototype showed no advantage over simple weighted evidence. Prototype code and logs are lost. |
| GNN anomaly detection on lineage graphs | **KNOWN PRIOR ART**, out of scope | PeerJ Computer Science, 2026 (as recorded). |
| US Patent 10,025,878 B1 | Existence recorded only | Make no infringement or patentability claim. That needs separate professional analysis. |

Claims about DataHub, OpenMetadata and Marquez lacking a whole-graph historical reconstruction query came from an earlier review. Use only this wording: "In our review of DataHub, OpenMetadata and Marquez, we did not find a documented whole-graph historical reconstruction query with these semantics." Re-check before any public presentation. Never write "no open-source tool can do this."

Old prototype numbers (for example a link-prediction AUC of about 0.50 to 0.56, or incremental maintenance being slower than full recomputation) were self-reported and their code is lost. They are not experimental evidence.

## 6. What We Are and Are Not Claiming

**What we are NOT claiming.** We do not claim to have invented:

- bitemporal lineage or bitemporal data,
- provenance or provenance tracking,
- incomplete-information semantics,
- the four-state vocabulary as a theoretical logic (it maps onto established certain, possible and unknown semantics),
- runtime lineage or OpenLineage,
- SQL parsing or graph lineage,
- generic lineage reconciliation or generic graph analytics.

We also do not claim that combining these components is novel by itself, that an `as_of` parameter is novel, or that the system is a replacement for DataHub, OpenMetadata or Atlan.

**Established mapping (conceptual only).**

| Our state | Established concept |
|---|---|
| OBSERVED | certain or definite TRUE |
| REFUTED_FOR_RUN | certain or definite FALSE, only under declared complete evaluation |
| POSSIBLE | possible answer |
| UNKNOWN | UNKNOWN |

**The potential contribution, stated carefully.**

> An operational, coverage-aware method for assigning established dependency semantics to lineage relationships under incomplete runtime evidence, together with an empirical evaluation of whether this reduces false conclusions compared with simpler lineage strategies.

This contribution remains **PROVISIONAL** until experimentally validated. If the hypothesis fails, the honest outcome is a strong engineering project plus a reported negative result.

Secondary items (each a system or engineering contribution, not a theory claim): an independent ground-truth methodology for a defined SQL subset, a documented evidence-precedence rule, an open reproducible benchmark and a self-hostable reference implementation.

## 7. One-Page Architecture

```
  SQL text            dbt manifest           OpenLineage events
     |                     |                        |
     v                     v                        v
+---------------------------------------------------------------+
|              EVIDENCE / METADATA LAYER  (M1, M2)              |
|   raw evidence (immutable)  ->  normalized evidence           |
+---------------------------------------------------------------+
                               |
                               v
+---------------------------------------------------------------+
|              POSTGRESQL  =  AUTHORITY  (M3)                   |
|   identity, temporal versions, evidence, derived states       |
+---------------------------------------------------------------+
            |                                    |
            v                                    v  optional, rebuildable
+-------------------------+          +---------------------------+
| BITEMPORAL LINEAGE      |          | NEO4J PROJECTION          |
| QUERIES (M3)            |          | only after a measured need|
+-------------------------+          +---------------------------+
            |
            v
+---------------------------------------------------------------+
|        EXECUTION-CONDITIONED REASONING  (M4)                  |
|   OBSERVED / REFUTED_FOR_RUN / POSSIBLE / UNKNOWN             |
+---------------------------------------------------------------+
            |
            v
      FastAPI /api/v1  (M5)   ->   UI  (M5)
```

The whole project fits in one hierarchy:

```
DATA -> EVIDENCE -> TEMPORAL LINEAGE -> EXECUTION-CONDITIONED REASONING -> QUERY/API -> UI
```

Keep these roles separate. This separation is **LOCKED**.

| Component | Role | Must never be used as |
|---|---|---|
| PostgreSQL | The only authoritative store | (n/a) |
| Neo4j | Optional, rebuildable read projection | An authority, or a correctness dependency |
| ProvSQL or ReferenceInterpreter | Independent ground truth | A predictor input |
| OpenLineage | Runtime observation evidence | Ground truth |
| SQLGlot | Static semantic evidence (what is possible) | Ground truth, or proof of execution |
| dbt manifest | Declared static metadata | Runtime observation |
| Reasoning engine | Interpretation under incomplete evidence | A source of raw evidence |

## 8. End-to-End Data Flow

**Path 1: ingestion and query (the product).**

```
raw input (SQL / event / manifest)
   -> source adapter -> normalization -> validation
   -> evidence candidate
   -> PostgreSQL transaction (raw evidence + normalized evidence + diagnostics)
   -> conflict detection (conflicts are flagged, never overwritten)
   -> lineage edge + temporal version created or closed
   -> reasoning engine writes a derived state (references its evidence)
   -> optional Neo4j projection via outbox
   -> API query -> UI
```

**Path 2: the experiment. Two isolated paths that meet only at the metrics step.**

```
REFERENCE PATH (ground truth)             OBSERVATION PATH (prediction)
---------------------------------         ----------------------------------
benchmark case (SQL + data)               same case, same execution
      |                                         |
      v                                         v
PostgreSQL + ProvSQL                      runtime evidence capture
(or ReferenceInterpreter)                 (OpenLineage / provider events)
      |                                         |
      v                                         v
GroundTruthProvider                       seeded loss simulator
      |                                   -> remaining events + coverage info
      v                                         |
PROPAGATED / NOT_PROPAGATED                     v
per prediction unit                       ReasoningEngine (+ static evidence)
      |                                         |
      |                                         v
      +--------------> METRICS <--------  4-state predictions
```

**Leakage boundary (LOCKED).** The reasoning engine must never read ground truth, the labels PROPAGATED or NOT_PROPAGATED, or ProvSQL output. Section 14 defines the enforcement mechanisms.

**Path 3: temporal query.** A request supplies an entity, optional `as_of` (valid time) and optional `recorded_as_of` (transaction time). The repository returns the edges whose valid interval contains `as_of` according to the knowledge that existed at `recorded_as_of`.

## 9. Component Architecture

All components are **NOT IMPLEMENTED**. Owners follow the locked team split (Section 29).

| ID | Component | Owner | Responsibility | Depends on (interface) |
|---|---|---|---|---|
| C1 | Static lineage provider (SQLGlot adapter) | M1 | SQL and schema in, static dependency evidence out | StaticLineageProvider |
| C2 | dbt manifest adapter | M1 | `manifest.json` in, static evidence out | StaticLineageProvider |
| C3 | Runtime evidence provider (ETL, OpenLineage) | M2 | Raw events in, normalized runtime evidence out | RuntimeEvidenceProvider |
| C4 | Ground-truth providers | M2 | Independent PROPAGATED or NOT_PROPAGATED per unit | GroundTruthProvider |
| C5 | Identity and PostgreSQL schema | M3 | Canonical IDs, migrations, constraints | StorageRepository |
| C6 | Temporal engine | M3 | Valid time and transaction time queries, late corrections | StorageRepository |
| C7 | Neo4j projection (optional) | M3 | Rebuildable graph copy with status tracking | StorageRepository |
| C8 | Reasoning engine | M4 | Four-state derivation with explanation | ReasoningEngine |
| C9 | Loss simulator and missingness models | M4 | Seeded removal of runtime evidence | (research runner) |
| C10 | Baselines B1 to B5 | M4 (B1 adapter by M1) | Comparison strategies | ReasoningEngine |
| C11 | Metrics and experiment runner | M4 | Pure metric functions, protocol-driven runs | (research runner) |
| C12 | FastAPI application | M5 | `/api/v1` routes, schemas, errors | StorageRepository, ReasoningEngine |
| C13 | Web UI (Stage 1) | M5 | Lineage explorer, evidence panel, temporal controls | `/api/v1` only |
## 10. Storage Architecture

**LOCKED decision: PostgreSQL is the only authoritative persistent store.**

- PostgreSQL holds assets, dataset and column versions, jobs, runs, raw events, evidence, logical edges, temporal versions, derived states, ground truth, experiment results and projection status.
- Neo4j is optional, derived, rebuildable and never authoritative. If the two disagree, PostgreSQL is correct and Neo4j is stale or divergent.
- Neo4j is introduced only after a measured need is demonstrated (gate below). The research runner must work without it.

**Logical tables** (from the contract; exact columns are frozen in numbered migrations by M3). Status: **PROVISIONAL**.

| Table | Purpose | Rules |
|---|---|---|
| `dataset`, `dataset_version` | Canonical datasets and schema versions | Identity tuple defined below in this section |
| `column` | Columns tied to a dataset version | Identity includes schema version |
| `job`, `execution_run` | Jobs and specific executions | Run ID from the source when present |
| `raw_event` | Untouched incoming payloads | Immutable. Payload hash. Unique event ID. |
| `evidence` | Normalized, source-tagged evidence | Immutable. No row is ever created from "absence of an event". |
| `lineage_edge` | Logical edges | Identity per the logical-edge tuple |
| `edge_temporal_version` | Valid and transaction intervals per edge | Half-open interval checks |
| `execution_state` | Derived four-state results | Versioned. References evidence, coverage, temporal context and engine version. |
| `ground_truth` | Independent PROPAGATED or NOT_PROPAGATED | Separate schema `evaluation`. Not readable by the predictor role. |
| `projection_outbox` | Neo4j projection status | PENDING, APPLIED, FAILED, STALE |
| `experiment_result` | Protocol-driven results | Hashes and versions recorded (Section 42) |

**Canonical identities** (**LOCKED**, from the contract). Names are display values, never universal identifiers.

```
Dataset       (source_system, namespace, database, schema, name, asset_type)
Column        (dataset_id, schema_version, column_name)
Job           (namespace, name)
Run           source run ID if present, else deterministic fingerprint + generated UUID
Evidence      source event ID, else SHA-256 of the canonical payload
Logical edge  (source_id, target_id, granularity, operator_fingerprint, query_fingerprint)
Prediction    (run_id, source_column_id, target_column_id, granularity, temporal_context)
```

Renames and schema versions create new identities unless an explicit alias record exists. Required identity tests: same column name in two datasets, quoted identifiers, case differences, renames, drops, moves, schema versions, duplicate events and aliases.

**Database rules.** UUID primary keys, foreign keys, canonical uniqueness constraints, state checks, half-open interval checks, unique event IDs, and indexes for identity, run, source and target traversal, fingerprints and temporal ranges. All schema changes are numbered migrations. Manual schema edits are forbidden.

**Neo4j decision gate (PENDING TEAM DECISION, D-06).** Before any Neo4j work starts, M3 measures PostgreSQL-only traversal (recursive queries with a depth limit) on graph sizes the team agrees to target. Result: **NOT YET MEASURED**. The team then decides whether PostgreSQL is adequate. If Neo4j is added, it is an idempotent projection fed from `projection_outbox`, and deleting and rebuilding it from PostgreSQL must be a tested operation.

## 11. Bitemporal Model

Bitemporal lineage is the historical infrastructure layer. It is **KNOWN PRIOR ART** and is never marketed as our novelty. It answers two different questions.

| | Question | API parameter | UI label |
|---|---|---|---|
| Valid time | What relationship was true in the pipeline at time t? | `as_of` | **Valid at** |
| Transaction time | What did Kairos know, or hold as recorded knowledge, at time r? | `recorded_as_of` | **Known as of** |

Both parameters together mean: the state that was valid at t, according to knowledge held at r. Neither parameter returns the latest current valid-time view unless it is omitted. Status: **LOCKED**.

**Half-open intervals** (**LOCKED**):

```
valid_from <= t AND (valid_to IS NULL OR t < valid_to)
transaction_from <= r AND (transaction_to IS NULL OR r < transaction_to)
```

**Separate time fields.** `event_time`, `effective_time`, `ingestion_time` and `transaction_from` are distinct. Detection time must never replace effective time when the effective time is known. A late correction closes the prior transaction interval and inserts a corrected record. Raw history is never deleted.

**Starting schema sketch** (**PROVISIONAL**; M3 justifies the final schema in `docs/DATA_MODEL.md`):

```
edge_temporal_version
  version_id            UUID  PK
  edge_id               UUID  FK -> lineage_edge
  valid_from            TIMESTAMPTZ
  valid_to              TIMESTAMPTZ NULL       -- NULL means still open
  effective_time_status TEXT  KNOWN / UNKNOWN  -- unknown is explicit, never guessed
  transaction_from      TIMESTAMPTZ NOT NULL
  transaction_to        TIMESTAMPTZ NULL
  evidence_id           UUID  FK -> evidence
  source_system         TEXT
  correction_of         UUID  NULL             -- links a corrected version to the prior one
```

The idea behind the earlier `recorded_at` and `superseded_at` fields is retained, but they are expressed as `transaction_from` and `transaction_to`.

**Worked example 1: a late correction (illustrative dates).** The real pipeline changed on 2026-03-01: edge A to B was replaced by A to C. Kairos detected the change on 2026-03-10.

| Query | Result | Why |
|---|---|---|
| Valid at 2026-03-05, Known as of 2026-03-05 | A to B | On 03-05 Kairos still believed A to B. |
| Valid at 2026-03-05, Known as of 2026-03-11 | A to C | After the correction, the record says A to C was valid on 03-05. |
| Valid at 2026-03-05, Known as of omitted (latest) | A to C | Latest knowledge about that valid time. |
| Valid at omitted, Known as of 2026-03-05 | A to B | The graph as Kairos held it then. |

Storage effect: the old edge version gets `valid_to = 2026-03-01`; the correction has `transaction_from = 2026-03-10`; the prior transaction interval is closed at 2026-03-10, not deleted. These four rows show why a single date picker is ambiguous: "what was true" and "what we knew" are different questions.

**Unknown effective time (PENDING TEAM DECISION, D-14).** The contract requires unknown effective time to be represented explicitly. How those edges appear in `as_of` results is undecided. Suggested default for M3 to evaluate: keep them out of `as_of` results by default, return them in a `warnings` list and allow an explicit include flag.

**Required temporal tests** (M3 owns): before interval, at start, inside, at end, after; late event; correction; deletion; reopen; overlapping intervals; combined `as_of` plus `recorded_as_of`; timezone normalization.

## 12. Evidence Model

Raw evidence is immutable, source-tagged and kept separate from derived reasoning. Pipeline:

```
raw event -> normalized evidence -> conflict detection -> derived state (versioned)
```

**Evidence record** (**PROVISIONAL** sketch; not every field is always available):

| Field | Meaning |
|---|---|
| `evidence_id` | Source event ID, or SHA-256 of the canonical payload |
| `evidence_type` | `STATIC_DEPENDENCY`, `DBT_DECLARED`, `RUNTIME_POSITIVE`, `RUNTIME_NEGATIVE_EVALUATION` |
| `source_system` | `sqlglot`, `dbt_manifest`, `openlineage`, other provider |
| `run_id` | Null for static evidence |
| `source_entity`, `target_entity` | Dataset IDs |
| `source_column`, `target_column` | Column IDs, when column-level |
| `granularity` | `DATASET`, `COLUMN`, `TUPLE_CELL` |
| `operator`, `query_fingerprint`, `schema_fingerprint`, `expression_fingerprint` | For static evidence |
| `event_time`, `effective_time`, `ingestion_time`, `transaction_from` | The four separate time fields |
| `valid_from`, `valid_to` | When the evidence implies the relationship held |
| `coverage` | Structured coverage vector (Section 14). Never a single number. |
| `parser_status` | `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, for static evidence |
| `diagnostics`, `conflict_flag` | Unsupported constructs, disagreements |
| `payload_reference`, `raw_payload_hash` | Pointer to the untouched `raw_event` |

**Classification of information** (each kind must be kept apart):

| Kind | Example | Stored as evidence? |
|---|---|---|
| Observed | An OpenLineage event says job J read dataset D | Yes |
| Inferred | SQLGlot infers that `salary` feeds `adjusted_salary` | Yes, as static possibility only |
| Missing | No event arrived for a dependency | **No row.** Absence is never stored as a negative record. |
| Coverage information | Which operators and branches were instrumented | Yes, as the coverage vector on evidence |
| Independent ground truth | ProvSQL says PROPAGATED | **No.** Separate `evaluation` schema. |

**How "no event" cannot become "did not occur" (LOCKED design rule).**

1. The evidence-type list has no "absent" value. Absence produces no row.
2. The only path to REFUTED_FOR_RUN is a `RUNTIME_NEGATIVE_EVALUATION` record. A provider may emit it only when its coverage vector declares complete evaluation for the scope it claims. Application validation and tests must reject an incomplete one.
3. Dataset-level runtime evidence must never be presented as column-level propagation without column-level facets or an independent provider.
4. Conflicting evidence is retained and flagged. It is never overwritten, and never silently dropped.

**Ingestion rules** (**LOCKED**). Idempotent by event ID or canonical payload fingerprint. Retries, duplicates, out-of-order events, late events and corrected events preserve raw inputs and create diagnostics where needed. Partial failures create diagnostics and never silently drop records.

**Reconciliation between sources** (**PROVISIONAL**, a system feature and not a research claim). Trust tiers for display are runtime evidence, then SQLGlot static evidence, then dbt manifest. Every edge keeps its `source_system` so conflicts are inspectable. The older rule "most recent `recorded_at` wins" is **REJECTED** because it overwrites silently: all versions are retained and the conflict is flagged.

## 13. Ground Truth Architecture

Ground truth must be independent of everything the reasoning engine consumes. Status: **LOCKED**.

**Two label vocabularies (LOCKED).**

| Where | Labels | Question answered |
|---|---|---|
| Ground truth (provider output) | `PROPAGATED`, `NOT_PROPAGATED` | Did at least one source value contribute to a target output, under the defined reference execution semantics? |
| Predictor output | `OBSERVED`, `REFUTED_FOR_RUN`, `POSSIBLE`, `UNKNOWN` | What can Kairos responsibly conclude from its evidence? |

Do not define an automatic "correct four-state label" from ground truth. Scoring uses the outcome table in Section 15.

**Prediction unit** (LOCKED): `(run_id, source_column_id, target_column_id, granularity, temporal_context)`. Dataset lineage, column lineage and tuple or cell propagation are separate relations. Never score a dataset-level prediction against column-level truth.

**Provider abstraction** (LOCKED):

```
GroundTruthProvider
   |-- ProvSQLProvider              (primary candidate, PROVISIONAL)
   |-- ReferenceInterpreterProvider (independent fallback, NOT IMPLEMENTED)
```

Nothing outside `research/ground_truth/` may import ProvSQL types. Ground truth is generated once, stored as versioned and hashed artifacts, and read only by the metrics step.

**Independence rules.**

- The ground-truth provider must not import SQLGlot, the ingestion code, the evidence-normalization layer or the reasoning engine.
- Ground truth is never used as input to prediction and never used to tune the predictor.
- Ground truth may be produced on one designated machine (for example one member's Linux or WSL2 setup) and shared as hashed files, so other members do not need ProvSQL installed. This is a design suggestion, **PROVISIONAL**.

**ProvSQL feasibility gate.** Status: **TO BE VALIDATED**. Result: **NOT YET MEASURED**. Do not state that the spike succeeded, that installation is complete or that any benchmark query is supported until M2 records evidence.

Spike checklist (M2 records OS, PostgreSQL version, compiler, extension version, commands, test queries, expected output, actual output, limitations and a reproduction command):

1. Native PostgreSQL install. 2. WSL2 if native fails. 3. Docker only as a last resort. 4. PostgreSQL version compatibility (the earlier spec says 15 or later is required; this is unverified). 5. Compile and install the extension. 6. Basic provenance query. 7. Tuple-level provenance. 8. Cell-level (where-) provenance, if it exists. 9. Aggregation provenance. 10. CASE provenance. 11. INNER JOIN provenance. 12. Subquery and NULL-sensitive expressions.

Time box: short (**PENDING TEAM DECISION**; the directive says do not spend days on installation). Decision tree:

| Outcome | Action |
|---|---|
| Native works | Use it. Record versions. |
| Only WSL2 works | Recommend WSL2 as the ground-truth environment. |
| Only Docker works | Reopen the "no Docker in primary path" decision with a written record. |
| ProvSQL unusable, or lacks needed output | Implement `ReferenceInterpreterProvider` for the supported SQL subset. |

**Critical open question: column-level truth (PENDING, D-11).** The prediction unit is column-level, but provenance tools may return provenance for whole tuples. Deriving "which column mattered" from tuple provenance would require knowing which columns each operator uses, which is exactly what SQLGlot computes. That would break independence. The spike must therefore answer: does the provider expose cell-level (where-)provenance, or another independent way to decide column-level contribution? If not, the team must either use the `ReferenceInterpreterProvider` (which evaluates column contribution directly), or narrow the primary prediction unit. Do not hide this by silently deriving column truth from static analysis.

**Contribution semantics.** Contribution is defined by the provenance mechanism, not by loose "influence". A row that was scanned does not count as contributing. For aggregates, a source tuple contributes only if the provenance expression for the output shows it. Whether ProvSQL exposes this in usable form is **TO BE VALIDATED**. Earlier notes describe a "nonzero coefficient" formulation. Treat that as unverified.

**Known restrictions.** LEFT JOIN and other outer joins are a known concern. UDFs, window functions and dynamic SQL are out. Unsupported cases are excluded from the main benchmark and listed openly, never silently included. If a construct cannot be evaluated independently, either exclude it or add a reference interpreter that handles it.

**Supported categories to test** (none verified): projection, WHERE, CASE, INNER JOIN, GROUP BY and aggregation, CTEs and subqueries, NULL-sensitive expressions.

## 14. Execution-Conditioned Reasoning

The reasoning engine consumes static evidence, runtime evidence, coverage, operator semantics and temporal context, and produces a derived state per prediction unit. It is provisional until experimentally validated.

**Forbidden inputs** (LOCKED): `ground_truth`, `PROPAGATED`, `NOT_PROPAGATED`, ProvSQL output.

**Four enforcement layers against leakage:**

1. **Type level.** `PredictorInput` (Section 16) has no ground-truth fields.
2. **Database level.** Ground truth lives in the `evaluation` schema. The predictor's database role has no access to it.
3. **Import boundary.** A CI check fails if `research/reasoning/` or `research/baselines/` imports `research/ground_truth/`.
4. **Automated test.** `test_predictor_cannot_access_ground_truth()` fails if any ground-truth value is passed into predictor inputs.

**Coverage vector** (LOCKED; structured, not a probability):

```json
{
  "run_covered": true,
  "operator_covered": true,
  "source_dataset_covered": true,
  "target_dataset_covered": true,
  "source_columns_covered": [],
  "target_columns_covered": [],
  "branches_covered": true,
  "coverage_mode": "structural|runtime|ground_truth",
  "parser_status": "SUPPORTED|PARTIAL|UNSUPPORTED"
}
```

Coverage means whether the evidence required for the declared conclusion was evaluated. It is not a row percentage and not a confidence. Parser status and evidence reliability are separate fields. Do not introduce an undefined numeric confidence field in v1.

**Complete negative evaluation contract.** REFUTED_FOR_RUN requires all of: a static candidate exists; all relevant operators and branches were evaluated; source and target identities are resolved; no unsupported construct affects the dependency; the evidence for the declared scope is complete. Ordinary absence of an event is never sufficient.

**Open design question (PENDING TEAM DECISION, D-09): how coverage is derived.** The engine must learn what was and was not observed without being told what the loss simulator removed beyond what a real system could know. Two candidate approaches: (a) an instrumentation manifest recording which operators, datasets and branches the capture layer covered; (b) event-integrity signals such as per-run sequence numbers and expected event counts that reveal gaps. Random single-event loss may be undetectable under (a). This is exactly the "coverage cannot be reliably estimated" kill criterion. M2 and M4 decide this together before the pilot.

**Open design question (PENDING TEAM DECISION, D-10): what counts as "positive runtime evidence".** OpenLineage events are typically dataset-level, with optional column-lineage facets. OBSERVED at column level needs runtime evidence at column or cell level. M2 must state which provider or instrumentation produces it in the benchmark and argue that it is independent of the ground-truth mechanism.

**Binding algorithm** (LOCKED, from the contract). Rules are applied in this order and the first match wins.

| Rule | Condition | Result | Reason code |
|---|---|---|---|
| R0 | Apply temporal context: drop evidence and edges outside `as_of` and `recorded_as_of` | (filtering step) | |
| R1 | Static semantics unsupported or ambiguous, identity unresolved, or schema missing, for this dependency | UNKNOWN | `UNSUPPORTED_OR_AMBIGUOUS` |
| R2 | Positive runtime or provider evidence establishes propagation, with resolved identity and matching run | OBSERVED | `POSITIVE_EVIDENCE` |
| R3 | Static candidate exists and the complete negative evaluation contract holds | REFUTED_FOR_RUN | `COMPLETE_NEGATIVE_EVALUATION` |
| R4 | Static candidate exists but neither R2 nor R3 holds | POSSIBLE | `INSUFFICIENT_EVIDENCE` |
| R5 | Otherwise (no static candidate, no positive evidence) | UNKNOWN | `NOT_A_STATIC_CANDIDATE` |

Edge case (**PROVISIONAL**): positive runtime evidence with no matching static candidate under a SUPPORTED parse gives OBSERVED with a conflict flag and a diagnostic. Evidence is never discarded.

**Expanded view of the rules** (this is a description of the algorithm, not a table of ground truth):

| Static candidate? | Parser status | Positive runtime evidence? | Complete negative evaluation? | State |
|---|---|---|---|---|
| Any | UNSUPPORTED or ambiguous | Any | Any | UNKNOWN |
| Yes | SUPPORTED or PARTIAL (dependency itself resolved) | Yes | Any | OBSERVED |
| Yes | SUPPORTED | No | Yes | REFUTED_FOR_RUN |
| Yes | SUPPORTED | No | No (missing, partial or unknown coverage) | POSSIBLE |
| Yes | PARTIAL, affected part unresolved | No | Any | POSSIBLE or UNKNOWN per R1 |
| No | SUPPORTED | No | Any | UNKNOWN (`NOT_A_STATIC_CANDIDATE`) |
| No | SUPPORTED | Yes | Any | OBSERVED with conflict flag |

**Prediction unit enumeration (PENDING TEAM DECISION, D-12).** Recommended default: the universe is static candidates plus pairs with positive runtime evidence. Ground-truth positives outside that universe are reported separately as static misses. Using the full cross product of columns would inflate correct-looking results with trivial non-dependencies.

**Explanation.** Every derived state stores its input evidence IDs, the coverage vector, the temporal context, the engine version, the rule ID and a human-readable explanation, so a user can ask "why is this POSSIBLE". Results must stay reproducible after engine changes, so states are versioned and never overwritten.

## 15. Four-State Semantics

The four states are an **operational representation** built on established incomplete-information and provenance semantics (**KNOWN PRIOR ART**, Section 5). They are not presented as a new logic.

| State | Meaning | Required | Forbidden |
|---|---|---|---|
| **OBSERVED** | At least one source value was observed to contribute to at least one target output in this run. | Positive runtime or provider evidence, resolved identity, matching run. | Static possibility alone. Treating one observed contribution as proof for every row or every run. |
| **REFUTED_FOR_RUN** | No propagation was established for this run, under the declared complete-evaluation conditions. | Static candidate, complete negative evaluation, resolved identity, no unsupported construct. | Treating a missing event as enough. Treating partial coverage as complete. Reading ground truth. |
| **POSSIBLE** | Static analysis permits the dependency, but evidence is insufficient to establish presence or complete absence. | A static candidate and incomplete evidence. | Presenting it as a negative or as confirmed. |
| **UNKNOWN** | Kairos cannot safely evaluate the dependency. | (Reason code recorded) | Guessing. |

Common causes of POSSIBLE: missing runtime events, partial operator or branch coverage, missing column-level evidence, incomplete instrumentation. Common causes of UNKNOWN: unsupported SQL, ambiguous semantics, unresolved identity, missing schema, unavailable instrumentation, unresolved conflicting evidence.

**Scoring outcome table** (used only by the metrics step, after prediction). This is separate from the transition rules above.

| Ground truth | Prediction | Interpretation |
|---|---|---|
| PROPAGATED | OBSERVED | Correct positive conclusion |
| PROPAGATED | POSSIBLE | Conservative, incomplete |
| PROPAGATED | UNKNOWN | No useful conclusion |
| PROPAGATED | REFUTED_FOR_RUN | **False refutation** (the error the project exists to prevent) |
| NOT_PROPAGATED | REFUTED_FOR_RUN | Correct commitment, valid only if the complete negative evaluation contract held |
| NOT_PROPAGATED | POSSIBLE | Conservative |
| NOT_PROPAGATED | OBSERVED | **False observation** |
| NOT_PROPAGATED | UNKNOWN | No useful conclusion |
## 16. Interface Contracts

These are the seams that let five people work independently. Sketches below are **PROVISIONAL** and become **LOCKED** at the architecture freeze (end of Week 1). They live in the shared `contracts/` package (Section 18). Any change needs a pull request approved by every member whose module touches it.

```python
# contracts/types.py  (sketch, field names frozen at architecture freeze)
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Sequence

class Granularity(str, Enum):
    DATASET = "DATASET"
    COLUMN = "COLUMN"
    TUPLE_CELL = "TUPLE_CELL"

class ParserStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"

class PredictedState(str, Enum):
    OBSERVED = "OBSERVED"
    REFUTED_FOR_RUN = "REFUTED_FOR_RUN"
    POSSIBLE = "POSSIBLE"
    UNKNOWN = "UNKNOWN"

class TruthLabel(str, Enum):        # ground truth ONLY. Never a predictor input.
    PROPAGATED = "PROPAGATED"
    NOT_PROPAGATED = "NOT_PROPAGATED"

@dataclass(frozen=True)
class TemporalContext:
    valid_at: Optional[str]         # ISO-8601, UI label "Valid at"
    known_as_of: Optional[str]      # ISO-8601, UI label "Known as of"

@dataclass(frozen=True)
class DependencyKey:                # the prediction unit
    run_id: str
    source_column_id: str
    target_column_id: str
    granularity: Granularity
    temporal_context: TemporalContext

@dataclass(frozen=True)
class CoverageVector:               # structured coverage, not a probability
    run_covered: bool
    operator_covered: bool
    source_dataset_covered: bool
    target_dataset_covered: bool
    source_columns_covered: Sequence[str]
    target_columns_covered: Sequence[str]
    branches_covered: bool
    coverage_mode: str              # "structural" / "runtime" / "ground_truth"
    parser_status: ParserStatus
```

```python
# contracts/evidence.py  (sketch)
@dataclass(frozen=True)
class StaticEvidence:
    evidence_id: str
    source_dataset_id: str
    target_dataset_id: str
    source_column_id: Optional[str]
    target_column_id: Optional[str]
    granularity: Granularity
    operator: str
    expression_fingerprint: str
    query_fingerprint: str
    schema_fingerprint: str
    parser_status: ParserStatus
    unsupported_constructs: Sequence[str]
    diagnostics: Sequence[str]

@dataclass(frozen=True)
class RuntimeEvidence:
    evidence_id: str
    evidence_type: str              # RUNTIME_POSITIVE or RUNTIME_NEGATIVE_EVALUATION
    run_id: str
    key: DependencyKey
    source_system: str
    event_time: str
    coverage: CoverageVector
    raw_payload_hash: str
    is_mock: bool = False           # mocks must be labelled

@dataclass(frozen=True)
class GroundTruthRecord:            # lives in the evaluation area only
    key: DependencyKey
    label: TruthLabel
    mechanism: str                  # "provsql" / "reference_interpreter"
    provider_version: str
    provenance_ref: str
```

```python
# contracts/interfaces.py  (sketch)
class StaticLineageProvider(Protocol):          # owner: M1
    def extract(self, sql: str, schema: "SchemaSnapshot",
                dialect: str = "postgres") -> "StaticExtraction": ...
    # StaticExtraction: evidence list, diagnostics, parser_status

class RuntimeEvidenceProvider(Protocol):        # owner: M2
    def normalize(self, run_id: str,
                  raw_events: Sequence["RawEvent"]) -> "RuntimeExtraction": ...
    # RuntimeExtraction: positive observations, negative evaluations,
    # coverage information, diagnostics. Absence never becomes a record.

class GroundTruthProvider(Protocol):            # owner: M2
    name: str
    version: str
    def supports(self, case: "BenchmarkCase") -> "SupportReport": ...
    def compute(self, case: "BenchmarkCase",
                run_id: str) -> "GroundTruthResult": ...
    # GroundTruthResult: records, status SUPPORTED/UNSUPPORTED,
    # unsupported reasons, provenance info, artifact hash

@dataclass(frozen=True)
class PredictorInput:                           # deliberately NO ground-truth fields
    keys: Sequence[DependencyKey]
    static_evidence: Sequence[StaticEvidence]
    runtime_evidence: Sequence[RuntimeEvidence]
    coverage: Sequence[CoverageVector]
    temporal_context: TemporalContext

@dataclass(frozen=True)
class Prediction:
    key: DependencyKey
    state: PredictedState
    evidence_ids: Sequence[str]
    coverage: CoverageVector
    reasoning_version: str
    rule_id: str                    # R1 to R5
    explanation: str

class ReasoningEngine(Protocol):                # owner: M4
    version: str
    def infer(self, inp: PredictorInput) -> Sequence[Prediction]: ...

class StorageRepository(Protocol):              # owner: M3
    def put_raw_event(self, event: "RawEvent") -> "PutResult": ...
    def put_evidence(self, ev: object) -> "PutResult": ...
    def get_lineage(self, entity_id: str, tc: TemporalContext,
                    direction: str, depth: int,
                    granularity: Granularity) -> "LineageResult": ...
    def get_run(self, run_id: str) -> "RunRecord": ...
    def get_evidence_for(self, key: DependencyKey) -> Sequence[object]: ...
    def put_state(self, p: Prediction) -> None: ...
    def projection_status(self) -> "ProjectionStatus": ...
```

**Interface rules.**

- Business and research logic depends on `StorageRepository`, never on a specific database. PostgreSQL stays authoritative and Neo4j stays replaceable.
- Every provider has an in-memory mock in `contracts/mocks/`. Mock outputs carry `is_mock: true`, and any result derived from mocks is labelled PLUMBING and is never reported as evidence.
- The `ReasoningEngine` never receives a `GroundTruthRecord`. Type checks and the CI import check enforce this.
- The `StaticLineageProvider` output records confidence-like metadata only through `parser_status`, diagnostics and the coverage vector. No numeric confidence in v1.

## 17. API Contract

All public routes use the `/api/v1` prefix (**LOCKED**). Every endpoint needs a Pydantic request schema, a response schema, status codes, validation rules, pagination, filter and sort behaviour, OpenAPI examples and at least one contract test. Owner of the whole table: M5, with M3 (temporal semantics) and M4 (state semantics) as reviewers.

Historical parameters (**LOCKED** semantics, names from the contract):

- `as_of`: valid time, shown in the UI as "Valid at".
- `recorded_as_of`: transaction time, shown in the UI as "Known as of".

**Entity identifiers in routes (PENDING TEAM DECISION, D-13).** The contract says no string name is a universal identity. Recommended default: routes take canonical IDs (UUIDs), and `GET /search` resolves names to IDs.

| Method and route | Purpose | Key parameters | Response (schema name) | Errors | Owner | Status |
|---|---|---|---|---|---|---|
| GET `/api/v1/health` | Liveness and readiness | none | `HealthResponse` (status, db, projection) | 503 | M5 | NOT IMPLEMENTED |
| GET `/api/v1/search` | Find entities by name | `q`, `type`, `limit`, `cursor` | `SearchResponse` | 400 | M5 (uses M3) | NOT IMPLEMENTED, PROVISIONAL |
| GET `/api/v1/lineage/{entity}` | Lineage of an entity | `as_of`, `recorded_as_of`, `granularity` | `LineageResponse` (nodes, edges, temporal_context, truncated) | 404, 400, 422 | M5 (M3) | NOT IMPLEMENTED |
| GET `/api/v1/lineage/{entity}/upstream` | Upstream traversal | `depth`, `as_of`, `recorded_as_of`, `granularity`, `limit` | `LineageResponse` | 404, 400 | M5 (M3) | NOT IMPLEMENTED |
| GET `/api/v1/lineage/{entity}/downstream` | Downstream traversal | same as upstream | `LineageResponse` | 404, 400 | M5 (M3) | NOT IMPLEMENTED |
| GET `/api/v1/runs/{run_id}` | Run metadata | none | `RunResponse` | 404 | M5 (M3) | NOT IMPLEMENTED |
| GET `/api/v1/runs/{run_id}/lineage` | Dependencies with evidence for a run | `granularity`, `state`, `limit`, `cursor` | `RunLineageResponse` | 404 | M5 (M3, M4) | NOT IMPLEMENTED |
| GET `/api/v1/runs/{run_id}/dependency/{source}/{target}` | State and explanation for one dependency in one run | `granularity`, `as_of`, `recorded_as_of` | `DependencyResponse` | 404, 400 | M5 (M4) | NOT IMPLEMENTED |
| GET `/api/v1/evidence/{dependency}` | Raw and normalized evidence behind a dependency | `source_system`, `limit`, `cursor` | `EvidenceListResponse` | 404 | M5 (M3) | NOT IMPLEMENTED |
| POST `/api/v1/ingest/openlineage` | Accept an OpenLineage RunEvent | JSON body | `IngestResponse` (accepted, duplicate flag) | 400, 409, 413, 422 | M5 (M2) | NOT IMPLEMENTED |
| POST `/api/v1/ingest/sql` | Accept SQL text plus schema reference | JSON body | `IngestResponse` with diagnostics | 400, 413, 422 | M5 (M1) | NOT IMPLEMENTED, PROVISIONAL |
| GET `/api/v1/projection/status` | Neo4j projection status | none | `ProjectionStatusResponse` | 503 | M5 (M3) | Only if Neo4j is adopted |
| GET `/api/v1/experiments/results` | Research results for the UI | `protocol_version`, `split` | `ExperimentResultsResponse` | 404 | M5 (M4) | Later UI stage, PROVISIONAL |

**Rules for all routes.**

- Stable error shape (**LOCKED**):

```json
{"error": {"code": "ENTITY_NOT_FOUND", "message": "...", "details": {}, "request_id": "uuid"}}
```

- Standard codes: `ENTITY_NOT_FOUND`, `RUN_NOT_FOUND`, `VALIDATION_ERROR`, `CONFLICT`, `UNSUPPORTED_INPUT`, `PROJECTION_UNAVAILABLE`, `INTERNAL_ERROR`.
- Depth: default and maximum are **PROVISIONAL** (earlier spec proposed default 3, maximum 10). Responses report `truncated: true` when limits cut the graph.
- Ingestion is idempotent. A duplicate event returns success with `duplicate: true` and creates no new evidence (**PROVISIONAL** status codes).
- The API layer coordinates storage, reasoning and providers. It contains no parsing, temporal or reasoning logic of its own.
- Payload size, depth, node and edge limits are enforced. SQL is always parameterized. Raw sensitive payloads are not logged.
- Ground truth is never returned by the product routes. It appears only in the clearly labelled evaluation route.

**Example: `GET /api/v1/runs/{run_id}/dependency/{source}/{target}`** (illustrative values; the `interpretation` text is shortened here, and the real API returns the fixed wording from Section 19):

```json
{
  "run_id": "uuid",
  "source": {"column_id": "uuid", "display": "orders_raw.amount"},
  "target": {"column_id": "uuid", "display": "monthly_revenue.total"},
  "granularity": "COLUMN",
  "state": "POSSIBLE",
  "interpretation": "Statically possible; evidence insufficient to confirm or refute for this run.",
  "temporal_context": {"as_of": null, "recorded_as_of": null},
  "coverage": {"run_covered": true, "operator_covered": false, "branches_covered": false,
               "coverage_mode": "runtime", "parser_status": "SUPPORTED"},
  "evidence": [{"evidence_id": "uuid", "type": "STATIC_DEPENDENCY", "source_system": "sqlglot"}],
  "reasoning": {"engine_version": "TBD", "rule_id": "R4"},
  "warnings": ["NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE"]
}
```

## 18. Repository Structure

One shared Git repository (**LOCKED**). Refined from the locked direction. The added parts, `contracts/`, the extra `research/` folders and `backend/migrations/`, are technically necessary to keep the modules independent, and are **PROVISIONAL**.

```
data-lineage-engine/
|-- README.md
|-- pyproject.toml            # pinned at first working build (NOT YET FROZEN)
|-- .env.example
|-- .gitignore
|-- CODEOWNERS
|-- docs/                     # this pack, DATA_MODEL, API, RESEARCH_LOG, DECISION_LOG,
|                             # IMPLEMENTATION_LOG, REPRODUCIBILITY, PRIOR_ART
|-- configs/                  # non-secret configuration, experiment configs
|-- contracts/                # shared types, Protocols, JSON schemas, mocks, fixtures
|-- backend/
|   |-- app/
|   |   |-- api/              # FastAPI routers                          (M5)
|   |   |-- schemas/          # Pydantic request and response models     (M5)
|   |   |-- services/         # orchestration only                       (M5)
|   |   |-- repositories/     # StorageRepository implementations        (M3)
|   |   |-- temporal/         # valid and transaction time logic         (M3)
|   |   |-- identity/         # canonical IDs, fingerprints              (M3)
|   |   `-- main.py
|   `-- migrations/           # numbered SQL migrations only             (M3)
|-- ingestion/
|   |-- sql/                  # SQLGlot adapter, static corpus           (M1)
|   |-- dbt/                  # manifest adapter                         (M1)
|   `-- openlineage/          # ETL script, event normalizer             (M2)
|-- research/                 # runs with no API, UI or Neo4j
|   |-- protocol/             # v1.yaml and later versions               (M4)
|   |-- benchmarks/           # cases, data manifests, splits            (M4, M1, M2)
|   |-- ground_truth/         # providers, spike report                  (M2)
|   |-- baselines/            # B1 (M1 adapter), B2 to B5                (M4)
|   |-- reasoning/            # proposed engine                          (M4)
|   |-- missingness/          # seeded loss simulator                    (M4)
|   |-- metrics/              # pure functions                           (M4)
|   |-- experiments/          # run.py and runners                       (M4)
|   `-- results/              # generated artifacts                      (M4)
|-- frontend/                 # Stage 1 UI                               (M5)
|-- tests/                    # unit, integration, temporal, negative, api, e2e,
|                             # research_regression
|-- scripts/                  # setup, seed, demo, reproduction scripts
`-- data/                     # gitignored raw data and dataset manifests
```

**Dependency rules** (enforced in CI):

- `research/` must not import `backend/` or `frontend/`.
- `backend/` may import `research/reasoning/` and `contracts/`.
- `research/reasoning/` and `research/baselines/` must not import `research/ground_truth/`.
- `research/ground_truth/` must not import `ingestion/` or SQLGlot.
- `frontend/` talks to `/api/v1` only.

**Ownership table** (also written into `CODEOWNERS`).

| Path | Owner | Reviewer |
|---|---|---|
| `ingestion/sql/`, `ingestion/dbt/` | M1 | M4 |
| `ingestion/openlineage/`, `research/ground_truth/` | M2 | M4 |
| `backend/migrations/`, `backend/app/temporal/`, `backend/app/identity/`, `backend/app/repositories/` | M3 | M1 |
| `research/protocol/`, `baselines/`, `reasoning/`, `missingness/`, `metrics/`, `experiments/`, `results/` | M4 | M2 |
| `backend/app/api/`, `schemas/`, `services/`, `frontend/` | M5 | M3 |
| `contracts/` | M4 (custodian) | All members |
| `docs/` | Pack owner (TBD) | All members |

## 19. UI Architecture

The UI is a system and demo layer. It is not the research contribution. No visualization is claimed as novel. Node-link graphs, search, upstream and downstream views and side panels are standard in existing lineage products. The UI-specific value is making time, evidence and uncertainty inspectable.

**Stack.** Web frontend by M5. The React and graph-library choice is **PENDING TEAM DECISION** (D-17). Candidates to compare in a short spike: React Flow and Cytoscape.js. The comparison covers directed-graph support, custom nodes and edges, zoom and pan, behaviour on a graph size the team agrees on, licence and learning cost. No performance number is assumed. The frontend calls `/api/v1` only and never reimplements storage, parsing or reasoning.

**Stage 1 (MUST BUILD).** Status: **LOCKED**.

| Element | Requirement |
|---|---|
| Entity search | Search box calling `/search`. Selecting a result loads its lineage. |
| Lineage graph | Directed graph, upstream and downstream, depth control, granularity toggle (dataset or column). Truncation is visible. |
| Historical controls | Two separate controls: **Valid at** and **Known as of**. They are never merged into one date picker. Defaults mean "latest". |
| Node details | Click a node for name, type, canonical ID and schema. |
| Edge and dependency details | Click an edge to open the evidence panel. |
| Evidence panel | For a selected dependency: state, plain-language interpretation, source and target, granularity, run ID, static evidence, runtime evidence, coverage vector, evidence source system and type, timestamps, reasoning version, explanation, conflict flag, and temporal context. Ground truth appears only in a clearly labelled evaluation mode. |
| Always-on banner | Whenever `as_of` or `recorded_as_of` is set: "Showing historical lineage. Valid at X. Known as of Y." |
| Status handling | Loading, empty, error and projection pending or failed states are visible. |

**Required state wording** (the four sentences are fixed, so no user reads absence of evidence as absence of dependency):

| State | UI text |
|---|---|
| OBSERVED | At least one source value was observed to contribute to at least one target output in this run. This does not imply contribution to every row or every run. |
| REFUTED_FOR_RUN | No propagation was established for this run under the declared complete-evaluation conditions. This is not a universal claim that the dependency can never occur. |
| POSSIBLE | Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run. |
| UNKNOWN | Kairos cannot safely evaluate this dependency because relevant semantics, identity, schema or instrumentation is unsupported or ambiguous. |

**Uncertainty rules.**

- Never render "no runtime event" as a negative. The UI must not show a POSSIBLE dependency as a faded or crossed-out edge that looks like absence.
- Never show a numeric confidence. Show the coverage vector and the state.
- Do not rely on colour alone. Every state has a text label and an icon or pattern. It must work in light mode, dark mode and for colour-blind users. Keyboard navigation must work. Specific colours are not fixed here (design decision for M5).
- Use "evidence status", not "confidence", in labels.

**Why the two time controls differ (examples for the team).** A pipeline change happened on 2026-03-01 and Kairos learned about it on 2026-03-10. The four-row table in Section 11 shows the different answers. The UI must let the user set both dates, and must state both in the banner.

**Later stages** (all **PROVISIONAL**, and none may delay the research core): run-specific lineage page, dependency state filtering, impact analysis, historical comparison, evidence timeline, metadata panels, column-level lineage drill-down, experiment dashboard, lineage quality indicators, advanced graph interactions. A broader product UI (home page, browse, tags, ownership, source management) was suggested by external research. It exceeds the contract's "small research UI" and needs a decision record to adopt.
## 20. Research Experiment Design

The experiment runs from `research/experiments/run.py` using only Python and a local PostgreSQL (plus ProvSQL if it passes the gate). It must not need FastAPI, the frontend or Neo4j (**LOCKED**). If the UI breaks, the research must still run.

```
benchmark case -> reference execution -> ground truth (provider)
              \-> runtime evidence -> loss simulator -> ReasoningEngine / baselines
                                                        -> predictions
ground truth + predictions -> metrics -> results artifact
```

**First research milestone (from the contract).** SQL fixture, then independent ground truth, then evidence-loss simulator, then B1, B2, B3, B4, B5, then the proposed four-state method, then metrics.

**Experiment matrix** (full experiment, after the pilot passes):

| Factor | Levels |
|---|---|
| Benchmark cases | 10 to 15 target (final list PENDING, D-07) |
| Loss mechanisms | Six from the contract (Section 22) |
| Loss levels | 0, 10, 30, 50, 70, 90 percent (**LOCKED**) |
| Methods | B1 to B5 and the proposed method, plus ablations |
| Replicates (seeds) | PENDING TEAM DECISION (D-04) |
| Data variants per case | At least two input distributions per case where the construct depends on data |

**Case separation.** Cases are split into development, validation and held-out evaluation sets. Do not tune on held-out cases. Demonstration cases, regression cases and research evaluation cases are different artifacts even when they share constructs. Split assignment: **PENDING** (M4, with M1 and M2).

**Protocol.** The full configuration is committed before the full experiment at `research/protocol/v1.yaml`. Changes create a new protocol version. Contents are listed in Section 42.

## 21. Benchmark Design

The benchmark is a set of controlled, deterministic SQL workloads for which independent ground truth can be established. Target size: 10 to 15. Final workload list: **PENDING TEAM DECISION** (D-07). LEFT JOIN and other outer joins are included only if an independent ground-truth method supports them, and never silently.

**Case definition.** Every case carries the following fields (a YAML file in `research/benchmarks/`):

| Field | Meaning |
|---|---|
| `case_id` | Unique ID |
| `sql_construct` | The construct(s) exercised |
| `input_dataset` | Data or generator reference, with hash or manifest ID |
| `expected_static_dependencies` | Hand-authored by M1 and reviewed by M4. SQLGlot output is not ground truth. |
| `ground_truth_mechanism` | `provsql` or `reference_interpreter`, plus version |
| `execution_specific_dependencies` | Produced by the ground-truth provider, checked against a hand-derived expectation on tiny fixtures |
| `why_this_case_exists` | The behaviour it tests |
| `split` | development, validation or held-out |

**Candidate workload categories.** These are categories, not a frozen list.

| ID | Category |
|---|---|
| W01 | Projection and aliases |
| W02 | WHERE filtering |
| W03 | CASE WHEN (data-dependent branching) |
| W04 | INNER JOIN |
| W05 | GROUP BY with aggregation (`SUM`, `AVG`, `MIN`, `MAX`, `COUNT(x)`) |
| W06 | `COUNT(*)` (dataset-level, per the static policy) |
| W07 | Multiple chained transformations |
| W08 | NULL-sensitive expressions (`COALESCE`, NULL in conditions) |
| W09 | Subqueries and CTEs |
| W10 | Same query on different input distributions |
| W11 | Data-dependent branching in aggregates |
| W12 | Multi-hop pipeline (staged, closer to the demo) |

**Motif case for W03 (illustrative; to be confirmed by the provider, not assumed).**

```
Query:  SELECT country,
               CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary
        FROM employees

Data A: ('US', 100), ('IN', 80)      -> the US row makes salary contribute
Data B: ('IN', 80),  ('DE', 90)      -> no US row, salary reaches no output value

Static analysis (both runs): country -> adjusted_salary, salary -> adjusted_salary
Hand-derived expectation:    salary -> adjusted_salary is PROPAGATED on A, NOT_PROPAGATED on B
```

This shows why static possibility is not execution-specific occurrence.

**Contribution semantics must be fixed in the protocol (PENDING, part of D-11).** "Contributes" can mean the source value was copied into the output (where-provenance) or that it influenced the output value (why-provenance). Under influence semantics `country` contributes to `adjusted_salary` in the motif case. Under copy semantics it does not. The protocol must state which is used, and the ground-truth provider must implement the same one.

**Data.** Synthetic fixtures isolate SQL semantics. Olist is a demonstration and integration dataset, not the only benchmark and not proof of generality. Its license check is pending (Section 43).

## 22. Observation-Loss Model

**Loss levels (LOCKED):** 0%, 10%, 30%, 50%, 70%, 90%.

**Rules (LOCKED).** Ground truth is never altered. Only the evidence available to the predictor changes. Loss must be reproducible from a fixed seed. Every result records the removed event IDs, the remaining event IDs, the mechanism, the level, the seed and the loss-mask hash.

**Mechanisms.** The six mechanisms come from the contract. The pack brief's terms are mapped to them here. The mapping is **PROVISIONAL**; the team confirms it.

| Contract mechanism | Brief's term | What is removed | "Level p" means |
|---|---|---|---|
| MCAR event loss | Random loss | Individual runtime events chosen uniformly at random | p percent of eligible events |
| Operator loss | Operator-specific loss | All events attributable to chosen operators | p percent of operators |
| Dataset loss | Source-specific loss | All events touching chosen datasets | p percent of datasets |
| Branch loss | Structured loss | Events of chosen conditional branches | p percent of branches |
| Complete run loss | (whole-run loss) | Every event of chosen runs | p percent of runs |
| Correlated loss | Burst loss | Events in contiguous or correlated groups | p percent of events, in bursts |

Rounding rules and eligibility definitions per mechanism: **PENDING** (M4).

**Seeds.** Each `(case, mechanism, level, replicate)` gets a seed derived from one master seed by a documented function. The master seed, the derivation and the number of replicates are set in `research/protocol/v1.yaml` and are **PENDING TEAM DECISION**. Do not adopt a seed value from older notes as if it were locked.

**Coverage after loss.** How the reasoning engine learns what was lost is an open design decision (D-09, Section 14). The simulator must produce only information a real capture layer could plausibly know. It must never leak the loss mask itself to the predictor beyond that.

**Loss level 0%.** Used as a control. With complete evidence, methods that differ only in how they treat missing evidence are expected to agree. This expectation is **TO BE VALIDATED**.

## 23. Baselines

Every baseline has a defensible purpose. None exists to make the proposed method look better. Definitions follow the contract (B1 to B5). The brief's "simpler coverage-aware baseline" corresponds to B4 and B5.

| ID | Name | Rule | Purpose |
|---|---|---|---|
| B1 | Static-only | Static candidates are the result. No runtime evidence. | The floor: what static analysis alone gives. |
| B2 | Negative-assumption runtime-only | Positive runtime evidence gives OBSERVED. No positive evidence gives REFUTED_FOR_RUN. | Deliberately defined baseline for tools that treat "not seen" as "not happened". Do not claim it represents every real platform. |
| B3 | Deterministic union | Runtime positive gives OBSERVED. Else static candidate gives POSSIBLE. Else UNKNOWN. | The likely alternative a competent engineer would build without coverage reasoning. |
| B4 | Three-state | Same as the proposed method but without the active REFUTED_FOR_RUN state. | Tests whether active refutation matters. |
| B5 | Coverage-gated runtime | Positive gives OBSERVED. Complete negative evaluation gives REFUTED_FOR_RUN. Otherwise UNKNOWN. | Tests whether static semantics add value beyond a coverage gate. |
| P | Proposed four-state | Section 14 algorithm: static semantics, runtime evidence, coverage, temporal context, negative evaluation contract. | The hypothesis under test. |

No existing lineage platform is included as a baseline, because none exposes this reasoning. This is stated openly rather than skipped. If a stronger established method is later found and is feasible to run, add it through a decision record.

## 24. Metrics

All metrics are pure functions in `research/metrics/` with no database dependency. A zero denominator yields `NA`, never zero (**LOCKED**). Definitions are **PROVISIONAL** until the team confirms them.

Notation. For each unit, let T be the ground-truth label (P = PROPAGATED, N = NOT_PROPAGATED) and S the predicted state. Let `n(S, T)` count units with that pair. `N_P` and `N_N` are the numbers of P and N units, and `N` is the total. Two ways of reading a prediction as "positive" are reported:

- strict: positive means OBSERVED.
- lenient: positive means OBSERVED or POSSIBLE (the dependency is retained, not refuted).

```
precision(mode)   = TP / (TP + FP)       TP = n(pos, P), FP = n(pos, N)
recall(mode)      = TP / N_P
FPR(mode)         = n(pos, N) / N_N
FNR(mode)         = 1 - recall(mode)
false_refutation  = n(REFUTED_FOR_RUN, P) / N_P     # the headline safety metric
false_observation = n(OBSERVED, N) / N_N
correct_refutation= n(REFUTED_FOR_RUN, N) / N_N
UNKNOWN_rate      = n(UNKNOWN, *) / N
POSSIBLE_rate     = n(POSSIBLE, *) / N
POSSIBLE_precision= n(POSSIBLE, P) / (n(POSSIBLE, P) + n(POSSIBLE, N))
```

**State classification accuracy (redefined).** The earlier spec defined it as "predicted state equals the ground-truth-derived correct state". The contract forbids an automatic four-state label, so this is **REJECTED**. Report three rates that sum to 1:

```
correct_commitment   = (n(OBSERVED, P) + n(REFUTED_FOR_RUN, N)) / N
wrong_commitment     = (n(OBSERVED, N) + n(REFUTED_FOR_RUN, P)) / N
non_committal        = (n(POSSIBLE, *) + n(UNKNOWN, *)) / N
committed_accuracy   = correct_commitment / (correct_commitment + wrong_commitment)
```

**Query-answer accuracy.** A query is "for run R and target column C, which source columns contributed?". Predicted set = sources whose state is positive (per mode). True set = sources labelled P. Report exact-match rate and mean Jaccard overlap across queries.

**Overhead.**

```
runtime_overhead  = mean(latency of method) - mean(latency of B2), same hardware, same queries
storage_overhead  = bytes(evidence + execution_state) / bytes(runtime-only evidence equivalent)
instrumentation   = ETL wall time with capture minus without, where measurable
```

All overhead values: **NOT YET MEASURED**.

**Aggregation and uncertainty.** Every result reports per-state confusion matrices, precision, recall, F1, error rates, UNKNOWN rate, coverage, latency, effect sizes and predeclared confidence intervals. The interval method is **PENDING TEAM DECISION** (D-08). Recommendation for the team to consider: units within one case are correlated, so resample at the case and replicate level instead of treating units as independent.

## 25. Ablations

The framework supports these variants. Each answers one question. Some are expected to coincide with a baseline. Report that, but do not count it as independent evidence. Expected relationships are **TO BE VALIDATED**.

| Variant | What is removed | Question answered | Expected relation |
|---|---|---|---|
| FULL | nothing | Reference for comparison | |
| FULL minus coverage | Coverage always treated as complete | Does coverage-awareness itself matter? | Behaves like B2 on the runtime side |
| FULL minus static semantics | Runtime only, keep the four-state machinery | Does static analysis add value? | Close to B5 |
| FULL minus runtime evidence | Static only, keep four states | Degenerate case | Collapses toward B1 |
| FULL minus four-state distinction | Merge REFUTED_FOR_RUN into UNKNOWN | Does active refutation matter? | Close to B4 |
| FULL minus bitemporal context | Ignore valid and transaction intervals when reasoning | Does temporal context change execution-conditioned results? | Minimal effect expected. A null result would show the two layers are separable. |

## 26. KILL CRITERIA: PENDING TEAM DECISION

This section is intentionally unresolved. **Do not invent thresholds.** The team fills in the table before the pilot starts. The completed table is committed to Git (with its timestamp) and cannot be edited after pilot results are seen. A change requires a new version and a decision record.

Guidance for choosing a threshold (no numbers implied):

- Practical basis: what error rate would make the method unusable, judged by the cost of a false refutation to a user.
- Statistical basis: a predeclared minimum meaningful effect and a confidence-interval rule, chosen so that noise across seeds cannot pass or fail the criterion by accident.

| ID | Condition to detect | Metric and comparison | Threshold | Justification | If triggered |
|---|---|---|---|---|---|
| K1 | No meaningful improvement over simpler baselines | Primary metric versus B3, B4, B5 | [TEAM TO FILL] | [TEAM TO FILL] | [KILL / NARROW / CONTINUE] |
| K2 | Benefit only on trivial queries | Effect stratified by case complexity | [TEAM TO FILL] | [TEAM TO FILL] | [ ] |
| K3 | Benefit disappears under realistic missingness | Effect under correlated, operator and dataset loss | [TEAM TO FILL] | [TEAM TO FILL] | [ ] |
| K4 | High false-refutation rate | `false_refutation` for the proposed method | [TEAM TO FILL] | [TEAM TO FILL] | [ ] |
| K5 | Ground truth not independent or invalid | Independence audit and leakage tests | Pass or fail | [TEAM TO FILL] | [ ] |
| K6 | Coverage cannot be reliably estimated | Agreement between derived coverage and true loss | [TEAM TO FILL] | [TEAM TO FILL] | [ ] |
| K7 | Excessive computational, storage or instrumentation overhead | Overhead metrics (Section 24) | [TEAM TO FILL] | [TEAM TO FILL] | [ ] |
| K8 | Result is merely a repackaging of existing provenance | Written review against prior art | Reviewer sign-off | [TEAM TO FILL] | [ ] |

If the hypothesis fails: KEEP the lineage infrastructure, ingestion, evidence, API and UI if their tests pass. REMOVE superiority and novelty claims about the reasoning method. REPORT the negative result and failure analysis. Do not alter the experiment after seeing results to rescue the hypothesis.

## 27. Pilot

The first experiment is small on purpose. Purpose: decide whether the research direction is worth continuing.

```
5 representative SQL workloads  x  3 loss levels  x  all required baselines
```

- Workload choice: **PENDING** (M4 proposes, team confirms). A reasonable spread covers CASE, INNER JOIN, GROUP BY, NULL-sensitive logic and one multi-step case.
- The three loss levels come from the locked six. **PENDING TEAM DECISION** (D-04). Suggestion: one low, one middle, one high (for example 10, 50 and 90), plus 0% as a control.
- Seeds and replicates: **PENDING** (D-04).
- Methods: B1 to B5 and the proposed method. Ablations are for the full experiment.

**Preconditions.** The kill criteria (Section 26) are committed, the ProvSQL gate has a recorded outcome (or the fallback provider is chosen), and the coverage-derivation and runtime-evidence questions (D-09, D-10) are decided.

**Plumbing runs.** Before real ground truth exists, M4 may run the whole pipeline on synthetic ground truth and mock evidence to test the code. Such outputs are labelled PLUMBING and are never treated as results.

**Pilot output.** A results artifact (Section 42), the per-state confusion matrices, an explicit comparison against each kill criterion, and a written go, narrow or stop recommendation. The pilot passing does not validate the hypothesis. It only permits the full experiment. If the pilot fails badly, stop and reassess.

## 28. Research Integrity Rules

1. Never reuse self-reported historical numbers as experimental evidence.
2. Never claim novelty from the absence of search results. "We could not find it" is not evidence of novelty.
3. Never claim the four-state model is theoretically novel.
4. Never use the reasoning input as ground truth, and never use ground truth as a reasoning input.
5. Never treat missing runtime evidence as proof that a dependency did not occur.
6. Never hide unsupported SQL cases. List them.
7. Never invent experiment results, performance numbers or statistical thresholds.
8. Never silently change the research question.
9. Keep prior art, architecture, implementation, hypothesis, experiment, validated result and limitation clearly separate in every document.
10. Every final research claim must point to an actual experiment or to cited prior work.
11. If an experiment disproves the hypothesis, report it. Do not modify the claim or the protocol after seeing the data.
12. Do not tune on held-out cases. Freeze the protocol before the full run.
13. Rejected directions and failed experiments stay in `docs/RESEARCH_LOG.md`. Do not delete them.
14. AI tools (code assistants and chat models) may help with code, tests, refactoring, documentation, SQL examples, literature discovery and debugging. They must not be trusted for novelty claims, citations that were not checked, experimental results, ground truth or benchmark numbers. Every AI-generated research claim needs human verification.
15. "It works" is reported only after it was actually run, with the environment, evidence and commit recorded.
## 29. Team Structure

The five workstreams are **LOCKED**. An earlier summary used a different split (ground truth as its own person, and an API-plus-integration role). It is **REJECTED** and superseded by this one.

| Member | Workstream | Owns |
|---|---|---|
| M1 | Static lineage | SQLGlot adapter, static evidence, dbt manifest adapter, static test corpus, parser limitation notes, B1 adapter |
| M2 | Runtime evidence and ground truth | ETL, OpenLineage evidence, ProvSQL spike, GroundTruthProvider implementations, independence tests |
| M3 | Storage and bitemporal lineage | Identity, PostgreSQL schema and migrations, temporal queries, repository, optional Neo4j projection |
| M4 | Reasoning and experiments | Reasoning engine, baselines, loss simulator, metrics, protocol, runner, pilot, ablations, final evaluation |
| M5 | API and UI | FastAPI, Pydantic schemas, ingestion and query routes, integration tests, Stage 1 UI, reproducibility packaging |

**Responsibility matrix** (from the contract). Status: **LOCKED**.

| Artifact | Responsible | Reviewer | Backup |
|---|---|---|---|
| SQL parser | M1 | M4 | M3 |
| Ground truth | M2 | M4 | M1 |
| Temporal storage | M3 | M1 | M5 |
| Reasoning | M4 | M2 | M1 |
| API and UI | M5 | M3 | M1 |

M2 is not a single point of failure. M4 reviews ground truth, M3 supports infrastructure, and the fallback provider keeps the experiment running.

**Shared duties.** Every member delivers code, tests, documentation, a short research or design note, a reproducible command, a limitation note, a reviewer record, a backup owner and a part of the final demonstration. No one is "just frontend" or "just docs".

**Workload shape.** M2's spike is the critical path early on. M5's integration work grows in the later weeks. Independent-first development (Section 35) lets M5 and M4 start on mocks in Week 1 rather than wait.

## 30. M1 Detailed Plan: Static Lineage

**Mission.** Own everything about what a query could depend on. Produce trustworthy static evidence and never claim that anything executed.

**Exact responsibilities.**

1. Build the `StaticLineageProvider` on SQLGlot for the PostgreSQL dialect. Supported: projection, aliases, WHERE, CASE, COALESCE, casts, arithmetic, INNER JOIN and its predicates, CTEs, supported subqueries, GROUP BY, `SUM`, `AVG`, `MIN`, `MAX`, `COUNT(x)`, `COUNT(*)`, `SELECT *` with a schema, NULL-sensitive conditions.
2. Implement the aggregation policy: `SUM(x)`, `AVG(x)`, `MIN(x)`, `MAX(x)` and `COUNT(x)` depend on `x`. `COUNT(*)` is dataset-level, not a dependency on every column. `GROUP BY g` depends on `g` for grouping identity. `SUM(CASE WHEN status='paid' THEN amount ELSE 0 END)` depends on both `status` and `amount`.
3. Handle conditional expressions: they depend on every column that can affect the result under SQL NULL semantics.
4. Emit `StaticEvidence` with expression, query and schema fingerprints, `parser_status`, unsupported constructs and diagnostics. Dataset lineage and column lineage are separate outputs.
5. Define the `SchemaSnapshot` input format and its fingerprint.
6. Unsupported constructs (window functions, UDFs, dynamic SQL, unresolved aliases, missing schema, unsupported dialect features) produce explicit diagnostics. The engine will turn them into UNKNOWN. Never guess.
7. Build the static test corpus: one SQL file per supported construct, plus unsupported examples per category, each with hand-derived expected dependencies. M4 reviews the expected values, because SQLGlot output is not ground truth.
8. Hand-author `expected_static_dependencies` for every benchmark case.
9. Provide the B1 adapter (static-only baseline) in `research/baselines/`.
10. Build the dbt manifest adapter (MVP-2, after SQL works): models to job plus dataset, sources to datasets, parent-child edges to static evidence, invalid manifests to diagnostics.
11. Write the SQLGlot capability audit and parser limitation notes.

**Inputs.** SQL text, schema snapshots, dbt manifest. Mock schema snapshots from `contracts/`.

**Outputs.** `ingestion/sql/`, `ingestion/dbt/`, `research/baselines/b1_static_only.py`, the static corpus, the limitation note, and sample `StaticEvidence` JSON.

**Independent-first tasks (start tomorrow).**

1. Create branch `feature/static-lineage`.
2. Write the first corpus entries: SQL for projection, alias, WHERE and CASE, each with hand-derived expected dependencies as JSON.
3. Implement `extract()` for projection and aliases, and get its tests passing.
4. Add CASE and INNER JOIN.
5. Publish `static_evidence.sample.json` into `contracts/fixtures/` for M3, M4 and M5.

**Mock interfaces.** Hand-written `SchemaSnapshot` JSON files. No database is needed.

**Must not.** Assign runtime states. Read ground truth. Claim that anything executed. Import from `research/ground_truth/`. Present SQLGlot output as ground truth. Guess unsupported constructs.

**Dependencies (integrate later).** M3 stores the evidence. M4 consumes it in baselines and reasoning. M2's ETL must emit the same SQL text so query fingerprints match.

**Definition of done.** Implementation, unit tests per construct, representative test data, documented parser limits, README, error handling for unparseable SQL, sample outputs for the team, known limitations listed, and review by M4.

**Handoff package.** Sample static evidence JSON, corpus with expected dependencies, a construct support matrix (SUPPORTED, PARTIAL or UNSUPPORTED per construct), the limitation note and the B1 adapter.

## 31. M2 Detailed Plan: Runtime Evidence and Ground Truth

**Mission.** Own what was observed at runtime and what is independently true. Keep those two things isolated.

**Exact responsibilities.**

1. Build a real, deterministic Python ETL against local PostgreSQL that executes SQL and emits OpenLineage events with `openlineage-python`. No Airflow. Use synthetic fixtures first, and Olist only after the license check.
2. Preserve raw events untouched, with event ID and payload hash.
3. Normalize events into `RuntimeEvidence`. Handle START, COMPLETE, failure, duplicate, retry, out-of-order, late and missing events. Idempotency key: event ID, or canonical payload fingerprint.
4. Never present dataset-level events as column-level propagation.
5. Define capture-completeness metadata so coverage can be derived. Decide D-09 and D-10 together with M4.
6. Run the ProvSQL spike (Section 13). Write `research/ground_truth/SPIKE_REPORT.md` with the full evidence list.
7. Implement `ProvSQLProvider` if the gate passes, and `ReferenceInterpreterProvider` as the fallback. Same interface. Outputs are versioned and hashed artifacts.
8. Propose the contribution semantics and the column-level truth approach (D-11) with M4.
9. Write independence tests: the provider imports no SQLGlot, no ingestion code and no reasoning code. Support M4's leakage test.
10. Document which SQL categories the ground truth supports and which are excluded.

**Inputs.** Benchmark SQL and data fixtures. Mock ground truth from `contracts/mocks/`.

**Outputs.** ETL script, sample runtime evidence JSON, provider implementations, spike report, ground-truth artifacts and an unsupported-cases list.

**Independent-first tasks (start tomorrow).**

1. Create branch `feature/runtime-groundtruth`.
2. Install local PostgreSQL. Create one small table and run one SELECT-based ETL step.
3. Emit one OpenLineage event to a local file (not to the API), so nothing depends on M5.
4. Start the ProvSQL attempt on your machine. Log every command and error. Respect the time box.
5. Publish `runtime_evidence.sample.json` and a mock `ground_truth.sample.json` (labelled `is_mock`) for M3, M4 and M5.

**Mock interfaces.** Events written to files instead of an HTTP endpoint. Hand-made ground truth JSON.

**Must not.** Feed ground truth into prediction. Import SQLGlot, `ingestion/sql/` or the reasoning engine in a ground-truth provider. Derive column-level truth from static analysis. Claim ProvSQL works before there is recorded evidence. Store absence of an event as a record.

**Dependencies (integrate later).** M4 consumes evidence and ground truth and reviews ground truth. M3 stores raw events and evidence. M1 supplies SQL text and fingerprints. M5 exposes the ingest route.

**Definition of done.** ETL runs from a clean checkout, raw events preserved and idempotent, normalization tests including duplicates and late events, spike report with recorded evidence, at least one working provider behind the interface, independence tests passing, documented limits, README and integration contract.

**Handoff package.** Spike report, sample runtime and ground-truth JSON, provider interface documentation, unsupported-cases list and the ground-truth artifact format.

## 32. M3 Detailed Plan: Storage and Bitemporal Lineage

**Mission.** Be the authority. Own identity, storage and temporal correctness.

**Exact responsibilities.**

1. Implement canonical identity functions and fingerprints in `backend/app/identity/`, with the identity tests from Section 10.
2. Write numbered migrations for the logical tables, with foreign keys, uniqueness constraints, half-open interval checks, unique event IDs and query indexes. Create the separate `evaluation` schema and the restricted predictor role.
3. Make raw evidence immutable (permissions or triggers), and prove it with tests.
4. Implement the temporal model: `edge_temporal_version`, queries for `as_of`, `recorded_as_of` and both, late corrections, deletion, reopening and timezone normalization.
5. Implement `PostgresRepository` for `StorageRepository`, including upstream and downstream traversal with depth and node limits and a `truncated` flag.
6. Make ingestion writes idempotent. Retries and duplicates create no new evidence.
7. Store derived states as versioned records with evidence references, coverage, temporal context and engine version.
8. Neo4j gate: measure PostgreSQL-only traversal, and report to the team (D-06). If approved, build the outbox-based projection with PENDING, APPLIED, FAILED and STALE status, and a tested rebuild.
9. Record storage and query performance measurements. All values are **NOT YET MEASURED** until taken.
10. Write `docs/DATA_MODEL.md` justifying the final schema. Resolve D-14 with M1 as reviewer.

**Inputs.** Sample evidence JSON from M1 and M2, or hand-made lineage records.

**Outputs.** Migrations, repository, temporal queries, `DATA_MODEL.md`, seed script, the temporal test suite and performance notes.

**Independent-first tasks (start tomorrow).**

1. Create branch `feature/bitemporal-storage`.
2. Set up local PostgreSQL. Write migration 0001 for dataset, job, run, raw_event and evidence.
3. Hand-write JSON lineage records for the worked example in Section 11.
4. Write the first five temporal tests: before the interval, at its start, inside, at its end, after.
5. Publish sample temporal fixtures in `contracts/fixtures/`.

**Mock interfaces.** Hand-authored lineage records. No other member's code is needed.

**Must not.** Redefine SQL semantics or the meaning of the four states. Store four-state results as raw facts in `evidence`. Edit the schema outside numbered migrations. Let Neo4j become authoritative. Overwrite or delete evidence.

**Dependencies (integrate later).** M1 and M2 provide evidence. M4 writes states. M5 serves the API.

**Definition of done.** Migrations apply cleanly from empty. All temporal tests pass (Section 11 list). Identity tests pass. Immutability and idempotency are tested. Repository passes the shared contract tests. Documentation, README, error handling, logging of conflicts and failures, and known limitations are in place.

**Handoff package.** Migrations, seed script, repository, `DATA_MODEL.md` and temporal fixtures.

## 33. M4 Detailed Plan: Reasoning and Experiments

**Mission.** Turn evidence into states, and test honestly whether that is useful.

**Exact responsibilities.**

1. Be custodian of `contracts/`. Open the PR that freezes it in Week 1.
2. Implement the coverage vector logic and the complete negative evaluation contract check.
3. Implement the `ReasoningEngine` with rules R0 to R5, reason codes, explanations and versioning. States are versioned, never overwritten.
4. Implement the baselines framework and B2 to B5, and switches for the ablations (B1 adapter is M1's).
5. Implement the seeded loss simulator for the six mechanisms. Record masks and hashes. Never touch ground truth.
6. Implement the metrics as pure functions (Section 24), with the NA rule and confidence intervals per D-08.
7. Write `research/protocol/v1.yaml`, `research/experiments/run.py` and the results artifact.
8. Build the synthetic benchmark generator and case files with M1 and M2. Assign splits.
9. Write `test_predictor_cannot_access_ground_truth()` and the import-boundary checks.
10. Facilitate the kill criteria (Section 26), run the pilot, ablations and the final evaluation. Write the failure analysis.

**Inputs.** Static evidence (M1), runtime evidence and ground-truth artifacts (M2), mocks.

**Outputs.** Engine, baselines, simulator, metrics, protocol, runner and results.

**Independent-first tasks (start tomorrow).**

1. Create branch `feature/reasoning-experiments`.
2. Open a PR with `contracts/types.py` from Section 16 for all members to review.
3. Implement rules R1 to R5 as a pure function over hand-built `PredictorInput` cases, with one unit test per row of the expanded rule table (Section 14).
4. Write metric functions and test them with tiny hand-computed confusion matrices.
5. Write a synthetic ground-truth stub. Anything that uses it is labelled PLUMBING.

**Mock interfaces.** Synthetic ground truth and synthetic evidence, both with `is_mock: true`.

**Must not.** Read ground truth during prediction. Change the protocol after seeing final results. Tune on held-out cases. Invent thresholds. Define state meanings that differ from Section 15. Report PLUMBING outputs as findings.

**Dependencies (integrate later).** M2 for real ground truth and runtime evidence. M3 for reading evidence from storage. M1 for static evidence.

**Definition of done.** Engine tests pass for every rule and every negative test. Protocol committed. Runner reproduces a pilot from a clean checkout. Baselines documented with their purpose. Result artifacts recorded. Interpretation and limitations written. Second-person reproduction done.

**Handoff package.** Frozen `contracts/`, engine, baseline definitions, protocol, runner usage guide, results and the failure analysis.

## 34. M5 Detailed Plan: API and UI

**Mission.** Make the system usable and inspectable. Build against mocks first, then integrate.

**Exact responsibilities.**

1. Create the FastAPI application structure under `backend/app/`, with a Pydantic request and response schema for every route in Section 17, OpenAPI examples and the stable error shape with `request_id`.
2. Implement mock repositories from `contracts/mocks/` so the API runs without a database.
3. Implement routes: health, search, lineage, upstream, downstream, runs, run lineage, dependency, evidence. Add pagination, limits and validation.
4. Implement ingestion routes that call the M1 and M2 normalizers and the repository, with idempotent responses.
5. Add structured logging with request IDs, and health and projection status.
6. Write contract tests, API tests and integration tests (mocks first, then real providers).
7. Build UI Stage 1 on fixtures: search, graph, Valid at and Known as of controls, banner, evidence panel, fixed state wording, accessibility.
8. Run the graph-library spike (D-17) and report.
9. Own integration and reproducibility packaging: README, setup and demo scripts, and a second-person reproduction check.
10. Start later UI stages only after Stage 1 acceptance.

**Inputs.** `contracts/`, mocks and fixtures.

**Outputs.** API, schemas, OpenAPI, UI, tests, demo script and `docs/REPRODUCIBILITY.md`.

**Independent-first tasks (start tomorrow).**

1. Create branch `feature/backend-ui`.
2. Scaffold FastAPI with `/api/v1/health` and the error handler.
3. Write the Pydantic models for `DependencyResponse` and `LineageResponse` from Section 17.
4. Wire a mock repository that returns the Section 11 worked example, and write contract tests for it.
5. Sketch the lineage explorer against mock JSON.

**Mock interfaces.** Mock repositories and JSON fixtures.

**Must not.** Reimplement parsing, storage or reasoning in the API or UI. Add authentication. Build past Stage 1 before it is accepted. Show ground truth outside evaluation mode. Use "confidence" wording or numeric confidence. Render a missing event as a negative.

**Dependencies (integrate later).** M3 repository, M4 reasoning, M1 and M2 ingestion.

**Definition of done.** Every route has schemas, examples, error cases and tests. Stage 1 UI acceptance passes: changing `as_of` changes the graph, invalid timestamps show the standard error, an edge shows full evidence context, truncation is visible, pending or failed projection is visible, keyboard navigation works, historical warnings are explicit and states are not shown by colour alone. Documentation and a second-person setup check are complete.

**Handoff package.** OpenAPI file, running demo script, UI build instructions and the acceptance checklist result.

## 35. Independent-First Development

**Rule (LOCKED):** no member is blocked by another member during the initial phase. Use mocks.

| Member | First milestone (no waiting) | Local data | Contract they build against | Mock used |
|---|---|---|---|---|
| M1 | Static extraction for projection, alias, CASE, INNER JOIN with tests | Hand-written SQL and schema JSON | `StaticLineageProvider` | Mock schema snapshots |
| M2 | ETL run plus one OpenLineage event to a file, ProvSQL attempt logged | Small local PostgreSQL table | `RuntimeEvidenceProvider`, `GroundTruthProvider` | Mock ground truth |
| M3 | Migration 0001 and five temporal tests | Hand-made lineage records | `StorageRepository` | Hand-authored evidence |
| M4 | Rules R1 to R5, metrics on hand-computed cases | Synthetic evidence | `ReasoningEngine`, `PredictorInput` | Synthetic ground truth |
| M5 | Health route, error handler, schemas, mock repository | Fixture JSON | `/api/v1` and `StorageRepository` | Mock repositories |

**Mock rules.**

- Mocks live in `contracts/mocks/` and `contracts/fixtures/`, and carry `is_mock: true`.
- Anything computed from mocks is labelled PLUMBING and is never reported as a finding.
- A mock is replaced by the real component only through a contract test that passes for both.

**Integration trigger.** When a member's real component passes its contract tests, it replaces its mock on `main` through a normal pull request. Integration order is in Section 40.

## 36. Git and GitHub Workflow

- One shared repository (**LOCKED**). No direct pushes to `main` (**LOCKED**). Everything goes through pull requests.
- Branches: `main`, `feature/static-lineage`, `feature/runtime-groundtruth`, `feature/bitemporal-storage`, `feature/reasoning-experiments`, `feature/backend-ui`. Short-lived topic branches off these are fine.
- Every pull request needs one required reviewer (Section 29 matrix), passing tests and passing CI checks (unit tests, lint, import-boundary checks).
- `CODEOWNERS` implements the ownership table in Section 18.
- Database changes are numbered migrations only.
- Structured logs and request IDs for ingestion counts, parse failures, conflicts, reasoning errors, projection failures and latency.

**Pull request template** (also the end-of-session report). Fill in every item:

1. What I tested. 2. Environment and versions. 3. What worked. 4. What failed. 5. Evidence (logs, screenshots, output). 6. Files and code produced. 7. Limitations. 8. Dependencies on others. 9. Recommendation. 10. Branch and commit.

Do not write "it works" without having actually run it. Status tags follow Section 1's legend, and a claim is `[IMPLEMENTED]` only when the code exists in the repository.

## 37. Definition of Done

**Project-wide (every major component).**

- [ ] Implementation exists in the repository.
- [ ] Unit tests, with representative test data.
- [ ] Interface documentation and a README section.
- [ ] Reproducible setup (documented commands, from a clean checkout).
- [ ] Error handling, and logging where appropriate.
- [ ] Example usage.
- [ ] Integration contract satisfied (contract tests pass).
- [ ] Known limitations written down.
- [ ] Reviewed by the assigned reviewer and merged by pull request.
- [ ] Handoff notes delivered to the members who depend on it.

**Additional for research components.**

- [ ] Experiment protocol committed before the run.
- [ ] Reproducible with recorded seeds, versions and hashes.
- [ ] Baseline comparison included.
- [ ] Result artifact saved.
- [ ] Interpretation written, separate from the raw result.
- [ ] Limitations and threats to validity written.
## 38. Week-by-Week Roadmap

Total horizon is about two months (from the directive). Calendar dates are **TBD** until the team sets a start date. The four-day checkpoint (Section 39) is a review, not the project deadline. Governing principle: **pilot first, then commit to the full research claim.**

**Week 1: foundations and freeze.**

- All: repository setup, CI, `CODEOWNERS`, branches. Architecture freeze: `contracts/` merged and this pack approved.
- M1: SQLGlot spike and first corpus entries.
- M2: ProvSQL spike and ETL skeleton. Gate outcome recorded.
- M3: identity functions, migration 0001, first temporal tests, bitemporal schema draft.
- M4: contracts PR, rules R1 to R5 on mocks, protocol skeleton.
- M5: API skeleton on mocks, graph-library spike.
- Exit gate: ProvSQL gate has a recorded outcome or the fallback is chosen. Contracts frozen. Environment matrix filled (Section 44).

**Week 2: components on their own.**

- M1: static lineage for the full supported subset, dbt adapter started.
- M2: runtime evidence normalization, ground-truth abstraction with at least one working provider.
- M3: storage implementation, temporal queries, late corrections.
- M4: loss simulator, benchmark v1 case files with M1 and M2, metrics.
- M5: initial API routes on mock repositories, ingestion routes.
- Exit gate: every component passes its own tests against its contract. Benchmark v1 case format agreed.

**Week 3: reasoning and first integration.**

- M4: proposed engine, baselines B1 to B5, first end-to-end research run on real ground truth (if available).
- M1, M2, M3: first integrated workflows: ingest real static and runtime evidence into PostgreSQL.
- M5: Stage 1 UI on fixtures, then on the real API.
- Exit gate: kill criteria (Section 26) committed. D-09 and D-10 decided.

**Week 4: pilot and review.**

- Run the pilot (Section 27). Kill-criteria review meeting. Ablation setup. Architecture corrections recorded in the decision log.
- Exit gate: written go, narrow or stop decision. If stop or narrow, the roadmap is rewritten before continuing.

**Weeks 5 and later (only if the pilot passes).**

- Full experiment with the held-out set. Ablations. Performance measurements.
- Neo4j evaluation only if the measured need exists (D-06).
- UI expansion beyond Stage 1 only if time allows and the research core is stable.
- Integration, failure analysis and case studies, documentation, second-person reproduction, final validation, final report and presentation.

## 39. Four-Day Checkpoint

A formal review at about day four. It is **not** evidence that the hypothesis is true. It checks whether the team can proceed.

| # | Question | Evidence required | Owner |
|---|---|---|---|
| 1 | Is ProvSQL feasible, or which fallback applies? | Spike report with recorded commands and output | M2 |
| 2 | Does static extraction work on the intended SQL subset? | Corpus tests passing, construct support matrix | M1 |
| 3 | Can runtime evidence be captured? | ETL run and events preserved, sample JSON | M2 |
| 4 | Is the evidence schema sufficient? | Sample evidence stored via migration 0001 | M3 |
| 5 | Does the bitemporal model work? | The four-row example in Section 11 reproduced by tests | M3 |
| 6 | Can the reasoning engine operate on mocks? | One unit test per rule row passing | M4 |
| 7 | Is the experiment protocol executable? | `run.py` runs on PLUMBING data end to end | M4 |
| 8 | Can the benchmark be generated? | At least the case format and one case file | M4 with M1, M2 |
| 9 | Does the architecture need changes? | Written list, each with a decision record | All |

A suggested four-day shape (**PROVISIONAL**): Day 1, repository, branches, contracts PR, spikes start. Day 2, mocks and skeletons. Day 3, first tests against contracts. Day 4, checkpoint review and decision log update.

The checkpoint report must state explicitly: execution-conditioned results are not yet validated.

## 40. Integration Plan

Integration happens component by component. Each swap of a mock for a real component needs passing contract tests.

| Step | Integration | Precondition | MVP step |
|---|---|---|---|
| 1 | Freeze `contracts/` and fixtures | All members reviewed | Week 1 |
| 2 | M1 static evidence into M3 storage | M1 and M3 contract tests | MVP-1, MVP-2 |
| 3 | M2 runtime evidence and raw events into M3 storage | Idempotency and immutability tests | MVP-2 |
| 4 | M4 reasoning reads evidence from storage and writes versioned states | Engine tests, negative tests | MVP-2 |
| 5 | M5 API replaces mock repositories with real ones | API contract tests on both | MVP-3 |
| 6 | UI Stage 1 on the real API | Acceptance checklist (Section 34) | MVP-4 |
| 7 | Research runner uses real ground-truth artifacts | Gate outcome and independence tests | MVP-0 completion |
| 8 | Full demo: ETL, evidence, storage, reasoning, API, UI | Clean-checkout smoke test | MVP-5 |

Research (MVP-0) proceeds in parallel and does not wait for steps 5 to 8.

## 41. Testing Strategy

**Layers** (from the contract): unit, integration, temporal, consistency and fault injection, API, UI, end-to-end and research regression. Every test layer lives under `tests/`.

| Layer | Owner | Examples |
|---|---|---|
| Unit | Each member | Identity, parser constructs, normalization, temporal predicates, coverage, state rules, fingerprints, error mapping |
| Integration | M3 with each provider owner | PostgreSQL with OpenLineage, SQLGlot, dbt, reasoning, API, optional Neo4j |
| Temporal | M3 | Before, at start, inside, at end, after; late event; correction; deletion; reopen; overlap; combined query; timezone |
| Fault injection | M3, M2 | Duplicate event, out-of-order event, partial failure, projection failure |
| API | M5 | Schema, status codes, pagination, limits, error shape |
| UI | M5 | Stage 1 acceptance checklist |
| End to end | M5 | ETL to evidence to PostgreSQL to reasoning to API to UI |
| Research regression | M4 | Benchmark, ground truth, loss mask, predictions, metrics reproduce a checked-in reference output |

**Required negative tests** (**LOCKED**):

- [ ] Missing runtime evidence does not become REFUTED_FOR_RUN.
- [ ] Unsupported SQL does not become OBSERVED.
- [ ] Ground truth is unavailable to the predictor (`test_predictor_cannot_access_ground_truth()`, database role check and import-boundary check).
- [ ] Neo4j absence does not break the research runner.
- [ ] Duplicate events do not duplicate evidence.
- [ ] Late corrections do not erase history.
- [ ] Unknown entities do not produce fabricated lineage.
- [ ] Zero metric denominators return NA.
- [ ] Dataset-level evidence is not accepted as column-level propagation.

## 42. Reproducibility

**Configuration.**

- `.env.example` lists every setting (database URL, ports, paths). Secrets live in environment variables only.
- `pyproject.toml` pins dependencies. Exact versions are frozen at the first working build. They are **NOT YET FROZEN** and must not be invented now.
- Database setup by numbered migrations plus a seed script. Benchmark and experiment configuration in `configs/` and `research/protocol/`.
- Random seeds and the protocol version are recorded in every result.

**Result artifact.** Every result records: benchmark version, protocol version, loss mechanism and level, seed, removed-event hash, ground-truth hash, prediction hash, Git SHA, environment, and database and provider versions.

**Protocol file.** `research/protocol/v1.yaml` must exist and be committed before the full experiment. Skeleton (all values are placeholders for the team to fill in):

```yaml
protocol_version: TBD
benchmark_version: TBD
sql_subset: TBD                  # list of supported constructs
splits: {development: TBD, validation: TBD, held_out: TBD}
contribution_semantics: TBD      # where-provenance or why-provenance (D-11)
prediction_unit_universe: TBD    # D-12
loss:
  mechanisms: [mcar, operator, dataset, branch, complete_run, correlated]
  levels: [0, 10, 30, 50, 70, 90]      # LOCKED
  master_seed: TBD
  replicates: TBD
baselines: [B1, B2, B3, B4, B5, proposed]
metrics: {primary: TBD, secondary: [precision, recall, false_refutation, unknown_rate]}
confidence_interval: TBD         # method chosen in D-08
aggregation: TBD
exclusion_rules: TBD
stopping_rule: TBD
environment: TBD
output_format: TBD
```

**Commands.** The target entry point is `python research/experiments/run.py --protocol research/protocol/v1.yaml`. It must run against a local PostgreSQL only.

**Independent reproduction.** A second person must reproduce the smoke test and the pilot from a clean checkout before any result is reported.

**Datasets.** Raw data is not committed. It is downloaded once, checksummed and loaded by a documented script.

## 43. DATASET / LICENSE CHECK: PENDING

Olist (Brazilian e-commerce public dataset) is intended as the live relational and demo dataset. **The license check is pending. Do not claim it is cleared.**

The team verifies and records:

- [ ] Dataset source and version.
- [ ] License text.
- [ ] Permitted use, including academic use.
- [ ] Redistribution constraints.
- [ ] Whether the raw data may be included in the repository or demo.
- [ ] Whether derived artifacts may be distributed.

Dataset manifest fields (to be created in `data/`): dataset ID, source and version, acquisition date, license-verification status, SHA-256 per file, schema fingerprint, loader version, raw and derived table list, split assignment.

If the license is unsuitable, the architecture supports replacing Olist with another dataset or a synthetic generator. Synthetic fixtures are used for the research benchmark regardless. The demonstration chain from raw tables to a dashboard-style table is a demo design and is **PROVISIONAL**.

## 44. Environment Matrix: PENDING TEAM INPUT

Do not assume that every member uses Windows. Each member fills in their own row.

| Member | OS | CPU | RAM | Docker available? | WSL2 available? | GPU | PostgreSQL setup | Python version | Neo4j available? | ProvSQL feasibility |
|---|---|---|---|---|---|---|---|---|---|---|
| M1 | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| M2 | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| M3 | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| M4 | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| M5 | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |

Guidance. Native local development is preferred where possible. No GPU is required by any component. ProvSQL may need Linux, WSL2 or Docker depending on the spike. The final environment is not declared until this table is complete. The earlier "no Docker in the primary path" rule was tied to a Windows-only assumption. It is now **PENDING** until the table is filled (D-16).

## 45. Risks and Mitigations

Likelihood labels below are qualitative judgments made without measurement. They are not probabilities.

| Risk | Likelihood | Impact | Mitigation | Trigger |
|---|---|---|---|---|
| ProvSQL cannot be installed or is unusable | Medium | High | Time-boxed spike, WSL2 path, `ReferenceInterpreterProvider` fallback behind the same interface | Spike time box ends without a working query |
| Provider gives only tuple-level provenance, not column-level | Medium | High | Decide D-11 early. Use the reference interpreter for column truth. Do not derive it from static analysis. | Spike shows no cell-level output |
| Unsupported SQL in the benchmark | Medium | Medium | Explicit exclusion list. Diagnostics and UNKNOWN. No silent inclusion. | Case fails `supports()` |
| Runtime evidence too coarse (dataset-level only) | Medium | High | Decide D-10. Column-level provider or narrower prediction unit. | OpenLineage sample has no column facets |
| Coverage cannot be reliably derived | Medium | High | Decide D-09 before the pilot. Kill criterion K6. | Derived coverage disagrees with the true loss mask |
| Ground truth not independent of the predictor | Low | Critical | Four-layer leakage protection, import checks, review by M4 | Any import or role check fails |
| Parser errors on real SQL | Medium | Medium | Corpus with hand-derived expectations, PARTIAL and UNSUPPORTED statuses | Corpus test failure |
| Incorrect state classification | Medium | High | One test per rule row, negative tests, review by M2 | Test or review finding |
| Graph or query overhead too high | Unassessed | Medium | Measure PostgreSQL traversal first. Depth and node limits. | Measured latency crosses the team's threshold (D-06) |
| Neo4j adds complexity without need | Medium | Medium | Optional projection only, measured-need gate | Gate not met |
| UI scope creep | High | Medium | Stage 1 lock, later stages only after acceptance | Work started outside Stage 1 |
| Integration conflicts between members | Medium | Medium | Contracts, mocks, CODEOWNERS, small PRs | Contract test failure at integration |
| Insufficient experiment size | Medium | High | Protocol fixed before running. Report intervals honestly. | Intervals too wide to decide |
| No meaningful improvement shown | Unassessed | High | Kill criteria decided in advance. Negative result is reported. | Pilot fails K1 to K4 |
| Dataset license problem | Unassessed | Medium | Synthetic fixtures for research, replaceable demo data | License unsuitable |
| Lost prior code cannot be recovered | Certain (already happened) | Medium | Rebuild from the contract, keep the decision log, commit early and often | (n/a) |

## 46. Open Decisions

Nothing here may be resolved by guessing. Each item needs a named decider and a date.

| ID | Decision | Why it matters | Who decides | Decide by | If unresolved |
|---|---|---|---|---|---|
| D-01 | Kill-criteria thresholds (Section 26) | Prevents rescuing a failed hypothesis after seeing data | Whole team, facilitated by M4 | Before the pilot | Pilot must not start |
| D-02 | Environment matrix | Determines ProvSQL path and setup | Each member for their row, M5 collates | Week 1 | Setup and reproduction fail |
| D-03 | Olist license verification | Legal use of the dataset in the repo and demo | M2 with M5 | Before any dataset is committed or shown | Use synthetic data only |
| D-04 | Pilot composition: loss levels, seeds, replicates, full-experiment replicates | Defines the experiment size | M4 with the team | Before the pilot | Pilot cannot run |
| D-05 | Result classification rule for Supported, Inconclusive, Rejected (six loss levels) | The old "3 of 4 levels" rule no longer fits | M4 with the team | Before the pilot | Post-hoc interpretation risk |
| D-06 | Is Neo4j needed after measurement? | Avoids unnecessary complexity | M3 measures, team decides | After MVP-1 traversal measurements | Stay PostgreSQL-only |
| D-07 | Exact supported SQL subset and final benchmark workloads | Fixes what the claims cover | M1, M2 and M4 | Week 2 | Benchmark cannot be frozen |
| D-08 | Statistical method and confidence-interval procedure | Needed to interpret results | M4 with the team | Before the pilot | Results cannot be judged |
| D-09 | How coverage is derived (manifest versus event-integrity signals) | Core to REFUTED_FOR_RUN and to kill criterion K6 | M2 and M4 | Before the pilot | REFUTED_FOR_RUN cannot be justified |
| D-10 | What counts as positive runtime evidence, and at what granularity | OBSERVED at column level needs column-level evidence | M2 with M4 | Week 2 | Primary unit must be narrowed |
| D-11 | Ground-truth semantics: where- or why-provenance, and how column-level truth is obtained | Independence and comparability of truth and prediction | M2 and M4, reviewed by M1 | After the spike | Column-level claims unsupported |
| D-12 | Which prediction units are enumerated (candidates plus observed, or full cross product) | Changes every metric denominator | M4 with M1 | Before the pilot | Metrics not comparable |
| D-13 | Entity identifiers in API routes (canonical IDs versus names) | Affects every route and the UI | M5 with M3 | Architecture freeze | Route churn later |
| D-14 | Handling of unknown effective time in `as_of` results | Contract requires explicit representation | M3 with M1 as reviewer | Week 2 | Ambiguous historical answers |
| D-15 | ProvSQL feasibility outcome and spike time box | Chooses the ground-truth provider | M2 records, team decides | Week 1 | Fallback provider becomes default |
| D-16 | Docker policy for the primary path | Depends on the environment matrix and the spike | Whole team | After D-02 and D-15 | Default to native or WSL2 |
| D-17 | Graph library for the UI | Affects UI effort and usability | M5 | Week 2 | Default candidate by spike result |
| D-18 | Confirm the mapping of loss mechanisms and rounding and eligibility rules | Needed for the protocol | M4 | Before the protocol commit | Protocol cannot be written |
| D-19 | Confirm evidence precedence tiers for display | Affects conflict presentation | M3, M1, M2 | Week 2 | Conflicts shown without ordering |
| D-20 | Pack owner and CI host | Keeps this document and checks maintained | Team | Week 1 | Pack drifts from the code |

## 47. Conflict-Resolution Table

Where source documents disagreed, this table records the resolution. Rule used: the locked decisions and the contract's non-negotiable invariants win over earlier ideas, experiments, architectures, conversations and team assignments.

| ID | Topic | Previous or alternative position | Final decision | Reason | Status |
|---|---|---|---|---|---|
| CR-01 | Definition of REFUTED_FOR_RUN and use of ground truth | The pack brief, an earlier summary and the old spec define it using ground truth ("independent ground truth shows no contribution"), and the brief's example table has a ground-truth column in the transition rules. | The predictor derives REFUTED_FOR_RUN only from a declared complete negative evaluation (Section 14). Ground truth is used only for scoring (Section 15, second table). | The contract's invariant says ground truth must never enter predictor inputs. Using it in the transition would leak the answer key. | LOCKED |
| CR-02 | PostgreSQL versus Neo4j authority | Old spec: Neo4j is the source of truth for graph structure, temporal fields on Neo4j edges. | PostgreSQL only. Neo4j is a projection. | Contract invariant, and the brief. | LOCKED |
| CR-03 | Is Neo4j mandatory? | Old architecture assumed both stores. | Optional. Added only after a measured need. | Complexity control (student project). | LOCKED |
| CR-04 | Team split | An earlier summary: separate ground-truth person, and an API plus integration person. | M1 to M5 as in Section 29. | Contract and brief. | LOCKED |
| CR-05 | Repository structure | A flat layout in an earlier summary. A larger tree in the original directive. | The brief's tree, refined with `contracts/`, extra `research/` folders and `backend/migrations/` (Section 18). | Keeps modules independent and the research runner standalone. | PROVISIONAL |
| CR-06 | API organization | Old spec: routes without version prefix. External context added more routes. | One `/api/v1` table (Section 17). Extra routes marked PROVISIONAL. | Contract requires `/api/v1`. | LOCKED (prefix), PROVISIONAL (extra routes) |
| CR-07 | UI sequencing and scope | External research suggested about eight screens and a product-style UI. | Stage 1 first (explorer, two time controls, evidence panel). Later stages optional. | Contract: small research UI. UI is not the contribution. | LOCKED (Stage 1) |
| CR-08 | Loss levels and result rule | Old spec used a rule over 4 loss levels. | Six levels are locked. The consistency rule needs redefinition (D-05). | Brief locks 0, 10, 30, 50, 70, 90. | LOCKED (levels), PENDING (rule) |
| CR-09 | Loss mechanisms | Brief lists random, burst, operator, source and structured. Contract lists six named mechanisms. | Contract's six are canonical. The brief's terms are mapped (Section 22). | Contract is the normative source. | PROVISIONAL |
| CR-10 | Ground-truth mechanism | ProvSQL assumed. | ProvSQL is the primary candidate behind `GroundTruthProvider`. A fallback exists. Feasibility not yet known. | Spike not run. | PROVISIONAL |
| CR-11 | Four-state semantics | Old spec defined OBSERVED and others directly from ground truth. | Two vocabularies: PROPAGATED and NOT_PROPAGATED for truth, four states for the predictor. | Contract. | LOCKED |
| CR-12 | Bitemporal role | Early framing implied novelty. | Infrastructure only, not novelty. | Prior art found. | LOCKED |
| CR-13 | Conflict handling between sources | Old spec: latest `recorded_at` wins. | Retain all versions, flag conflicts, no silent overwrite. Display precedence is PROVISIONAL. | Contract forbids silent overwrite. | LOCKED (no overwrite), PROVISIONAL (precedence) |
| CR-14 | Novelty position | Early drafts used stronger wording. | The conservative contribution statement in Section 6. | No experimental validation. | LOCKED |
| CR-15 | Pilot-first strategy | Some early plans went straight to full experiments. | Pilot first, decision, then full experiment. | Limits wasted effort. | LOCKED |
| CR-16 | Baselines | Old spec: B1 to B4. Brief: four baselines plus the proposed one. | Contract's B1 to B5 plus proposed. | Contract. The brief's simpler baseline maps to B4 and B5. | LOCKED |
| CR-17 | Coverage representation | Old spec: numeric `coverage` column and "sufficient confidence". | Structured vector, no numeric confidence in v1. | Contract. | LOCKED |
| CR-18 | State classification accuracy | Old spec: predicted state equals the ground-truth-derived correct state. | Replaced by commitment rates (Section 24). | Contract forbids an automatic four-state label. | LOCKED |
| CR-19 | Identity | Old DDL: unique on namespace and name. | Contract's identity tuples. | Names are not universal identities. | LOCKED |
| CR-20 | Old prototype numbers | Self-reported AUC and speed results. | Excluded as evidence. | Code lost, evaluation not independent. | LOCKED |
| CR-21 | Docker | Earlier rule: no Docker with one flagged exception. | Pending environment matrix and spike (D-16). | The old rule assumed Windows only. | PENDING |
| CR-22 | Perplexity competitor and UI audit | Treated as a finding in earlier discussion. | Context only. Only a fraction of the products were checked against primary sources, and its citations did not survive. | Not verified. | KNOWN LIMITATION |

## 48. Decision Log

Owners and dates are **TBD** where unknown. Machine-readable in the sense of stable IDs and one row per decision.

| ID | Decision | Status | Owner | Date or phase | Evidence required |
|---|---|---|---|---|---|
| DL-01 | Bitemporal lineage is infrastructure, not a novelty claim | LOCKED | TBD | Pack v1.0 freeze | Prior-art notes (Section 5), re-verified |
| DL-02 | Execution-conditioned reasoning is the provisional research layer | PROVISIONAL | M4 | Until pilot decision | Pilot and full experiment |
| DL-03 | PostgreSQL is the only authority. Neo4j is an optional projection. | LOCKED | M3 | Pack v1.0 freeze | Rebuild test, measured need if adopted |
| DL-04 | Raw evidence immutable and separate from derived states | LOCKED | M3 | Pack v1.0 freeze | Immutability tests |
| DL-05 | Valid time and transaction time kept separate (`as_of`, `recorded_as_of`) | LOCKED | M3 | Pack v1.0 freeze | Temporal test suite |
| DL-06 | Two label vocabularies: truth and predictor | LOCKED | M4 | Pack v1.0 freeze | Leakage tests |
| DL-07 | Missing runtime evidence never produces REFUTED_FOR_RUN | LOCKED | M4 | Pack v1.0 freeze | Negative tests |
| DL-08 | Ground truth never enters predictor inputs | LOCKED | M2 and M4 | Pack v1.0 freeze | Four-layer leakage protection |
| DL-09 | ProvSQL is the primary ground-truth candidate | PROVISIONAL | M2 | After spike | Spike report |
| DL-10 | Fallback `ReferenceInterpreterProvider` behind the same interface | PROVISIONAL | M2 | Week 1 | Provider contract tests |
| DL-11 | Loss levels 0, 10, 30, 50, 70, 90 | LOCKED | M4 | Pack v1.0 freeze | Protocol file |
| DL-12 | Baselines B1 to B5 plus proposed | LOCKED | M4 | Pack v1.0 freeze | Baseline tests |
| DL-13 | Five-member split M1 to M5 | LOCKED | Team | Pack v1.0 freeze | Ownership table |
| DL-14 | Independent-first development with labelled mocks | LOCKED | Team | Pack v1.0 freeze | Contract tests |
| DL-15 | `/api/v1` prefix and stable error shape | LOCKED | M5 | Pack v1.0 freeze | Contract tests |
| DL-16 | UI Stage 1 with separate Valid at and Known as of | LOCKED | M5 | Pack v1.0 freeze | UI acceptance checklist |
| DL-17 | Kill criteria thresholds set before the pilot | LOCKED (rule), thresholds PENDING | Team | Before pilot | Committed table |
| DL-18 | Pilot before full experiment | LOCKED | M4 | Pack v1.0 freeze | Pilot decision record |
| DL-19 | No Airflow, Kubernetes, cloud, enterprise IAM, GNN or LLM features in the MVP | LOCKED | Team | Pack v1.0 freeze | (none) |
| DL-20 | Shared `contracts/` package and dependency rules (Section 18) | PROVISIONAL | M4 | Architecture freeze | CI import checks |

## 49. Research Validation Checklist

Tick each item only with evidence in the repository.

- [ ] Research question and hypotheses are unchanged from Section 3 and 4, or the change has a decision record.
- [ ] Ground truth provider chosen with recorded spike evidence.
- [ ] Ground truth is independent (import checks, role checks and review by M4 passed).
- [ ] Contribution semantics and column-level truth approach fixed (D-11).
- [ ] Coverage derivation fixed and tested (D-09), runtime evidence level fixed (D-10).
- [ ] Prediction-unit universe fixed (D-12).
- [ ] Benchmark frozen with splits, and unsupported cases listed.
- [ ] Protocol `v1.yaml` committed before the full run.
- [ ] Kill criteria committed before the pilot.
- [ ] Pilot run, compared against every kill criterion, decision recorded.
- [ ] Held-out set used only once for final evaluation.
- [ ] Every metric reports NA for zero denominators and includes intervals per D-08.
- [ ] Ablations run, and expected coincidences with baselines reported as such.
- [ ] Every result has hashes, seeds, versions and Git SHA.
- [ ] A second person reproduced the pilot from a clean checkout.
- [ ] Prior-art citations re-verified. Nothing claimed as novel without support.
- [ ] Failure analysis and limitations written, including negative results.

## 50. Final Project Checklist

- [ ] MVP-0: standalone research runner works without API, UI and Neo4j.
- [ ] MVP-1: PostgreSQL historical lineage, all temporal tests pass.
- [ ] MVP-2: OpenLineage, SQLGlot and dbt ingestion, idempotent and immutable.
- [ ] MVP-3: `/api/v1` with schemas, examples, error shape and tests.
- [ ] MVP-4: Stage 1 UI acceptance passes.
- [ ] MVP-5: integrated demo from a clean checkout (load data, ETL, ingest, reason, query, view).
- [ ] Duplicate, late, unsupported, unknown and projection-failure cases are handled.
- [ ] Research results are labelled measured, inconclusive, rejected or unavailable.
- [ ] Documentation (`README`, `DATA_MODEL`, `API`, `REPRODUCIBILITY`, logs) is up to date.
- [ ] Final report states what is and is not novel, in line with Section 6.
- [ ] Every member delivered code, tests, docs, a research note, a reproducible command, a limitation note and a demo part.

## Appendix A: Consistency Audit of This Pack

Performed by the author of this pack against the brief. "Pending by design" means the item is deliberately left open and is listed in Section 46.

| Check | Result |
|---|---|
| PostgreSQL clearly authoritative, Neo4j optional and rebuildable | Yes (Sections 7, 10) |
| Bitemporal lineage is infrastructure, not claimed novelty | Yes (Sections 6, 11) |
| Execution-conditioned reasoning is the research layer | Yes |
| Research question explicit, hypothesis provisional | Yes (Sections 3, 4) |
| Ground truth independent | Yes by design. Column-level truth still open (D-11). |
| Four states framed as established semantic ideas | Yes (Sections 6, 15) |
| Old numbers excluded | Yes (Sections 5, 47) |
| Kill criteria left pending | Yes (Section 26) |
| M1 to M5 separated, independent, with must-not rules | Yes (Sections 29 to 35) |
| Repository, API and interfaces explicit | Yes (Sections 16 to 18) |
| Loss levels locked, mechanisms, baselines, metrics, pilot defined | Yes (Sections 22 to 27) |
| UI Stage 1 defined, two separate time controls, evidence panel | Yes (Section 19) |
| Missing evidence cannot become refutation | Yes (Sections 12, 14, 41) |
| REFUTED_FOR_RUN tied to complete negative evaluation | Yes. This deviates from the brief's wording, see CR-01. |
| Nothing fabricated (ProvSQL results, experiment numbers, performance, license approval, machine data, thresholds) | Yes. Every such item is marked PENDING, NOT YET MEASURED or TBD. |
| Illustrative values (dates in the Section 11 example, the CASE motif data, the example API response) | Labelled as illustrative. They are not project data. |

## Appendix B: Source Materials

| Source | What it is | How it was used | Caveat |
|---|---|---|---|
| Kairos v1.0 Team Execution Contract (PDF) | Normative contract with the older master specification appended | Primary source for invariants, identity, temporal rules, states, baselines, team matrix | Draft, freeze pending team approval |
| `MASTER_SPECIFICATION.md` | Older specification, identical to the contract's appendix | Background: data model ideas, API draft, hypotheses, prior-art table | Superseded where it conflicts with the contract |
| Master Execution Directive | Original build instructions | Repository layout, spike plan, logs, pilot design | Some items superseded by the contract |
| Reconstructed project context (ChatGPT export) | Summary of earlier conversations | Decision history, rejected directions, working rules | Secondary. Its team split and ground-truth definition are superseded. The file was cut off. |
| Recovery context (Perplexity export) | Restatement of the contract with UI detail | UI wording, Olist manifest idea, acceptance checks | Secondary |
| Competitor and UI research (Perplexity exports) | Market and UI audits | Context for Stage 1 scope | Citations did not survive. Only some products were checked against primary sources. Not evidence. |
| `ARCHITECTURE_DECISIONS.pdf`, `KAIROS_MASTER_DOCUMENT.pdf` and `.docx` | Title pages only | Not used | Contain no content beyond a title and a status line |
| The pack brief (task prompt) | The locked decisions and requested structure | Structure and locked decisions | Where it conflicts with a contract invariant, see CR-01 |
