# Kairos Team Guide: What Is in the Zip, How to Start, and What Each Member Does Next

## 1. The 60-Second Summary

You have two things: a **design** (the Final Architecture & Research Execution Pack, in `docs/`) and a **foundation codebase** (the zip). The foundation is small on purpose. It contains the shared contracts every member codes against, a first version of the four-state reasoning engine, the five baselines, the metrics, and the safety checks that stop ground truth from leaking into predictions. Everything else (database, ingestion, API, UI, ground truth, experiments) is **not built yet** and is split across the five of you.

The order of work for everyone:

1. **One person (the team lead) sets up the GitHub repository** (Section 3). About 30 minutes.
2. **Everyone sets up their machine** and runs the tests (Section 4). About 15 minutes.
3. **Hold a first team meeting** to settle a few decisions (Section 7).
4. **Each member follows their own guide** (Sections 8 to 12): first-day steps, a starter snippet, the tests to write and what to hand over.
5. **Meet at the four-day checkpoint** (Section 13). It checks whether the design works. It does not prove the research idea.

Two rules matter more than any others:

- Work independently on **mocks**. Nobody waits for anybody. Anything computed from mock data is labelled **PLUMBING** and is never a result.
- **Ground truth never enters a prediction.** The code enforces this. If a test about it fails, fix the code, never the test.

> **About the code snippets in this guide.** Snippets marked **(ran in a sandbox)** were executed before writing this guide, with the library versions named. Snippets marked **(starting point, not run)** need something I did not have (a local PostgreSQL, Node, ProvSQL) and may need adjusting. Library behaviour can change between versions, so freeze versions once your first build works.

## 2. What Is in the Zip

```
data-lineage-engine/
|-- README.md                     what exists today, quick start, CI rules
|-- pyproject.toml                package config (standard library only for now)
|-- .env.example                  placeholder settings (copy to .env, never commit .env)
|-- .gitignore
|-- .github/
|   |-- CODEOWNERS                who must review which folder (edit the handles)
|   `-- workflows/ci.yml          CI: import-boundary check, then tests
|-- docs/
|   |-- FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md / .docx   the full design
|   `-- TEAM_GUIDE.md / .docx     this guide
|-- contracts/                    THE SHARED SEAMS. Everyone imports from here.
|   |-- types.py                  states, granularity, coverage vector, prediction key
|   |-- evidence.py               static evidence, runtime evidence, prediction, predictor input
|   |-- truth.py                  ground-truth-only types (predictors may never import this)
|   |-- interfaces.py             the five module interfaces plus small helper types
|   |-- mocks/loaders.py          JSON <-> Python objects for fixtures
|   |-- mocks/providers.py        labelled mock providers
|   `-- fixtures/w03_case_when*.json   tiny CASE WHEN example (4 runs, mock truth)
|-- research/
|   |-- reasoning/engine.py       four-state engine, rules R1 to R5
|   |-- baselines/baselines.py    B1 to B5
|   |-- metrics/metrics.py        all metrics, NA for zero denominators
|   |-- ground_truth/  protocol/  benchmarks/  missingness/  experiments/  results/
|   |                             empty, each with a README naming its owner and first tasks
|-- backend/app/main.py           tiny FastAPI slice: /health and one dependency route on mock data
|-- ingestion/  frontend/  configs/  data/     empty, with owner READMEs
|-- scripts/
|   |-- check_import_boundaries.py   enforces the leakage and independence rules
|   `-- make_fixtures.py             regenerates the mock fixtures
`-- tests/                        34 tests (3 of them need FastAPI installed)
```

**What the important files do.**

| File | What it does | Who owns it |
|---|---|---|
| `contracts/types.py` | Defines the four states, the prediction unit (`DependencyKey`), and the coverage vector. `CoverageVector.is_complete_for(key)` is the coverage half of the "complete negative evaluation" rule. | M4 (all review changes) |
| `contracts/evidence.py` | `StaticEvidence`, `RuntimeEvidence`, `Prediction`, `PredictorInput`. `RuntimeEvidence` refuses to be built as a negative evaluation unless its coverage is complete, so "we saw nothing" can never be stored as "it did not happen". | M4 (all review) |
| `contracts/truth.py` | `TruthLabel` (PROPAGATED, NOT_PROPAGATED) and `GroundTruthRecord`. Kept in its own module so the import rule can be checked by module name. | M2 |
| `contracts/interfaces.py` | `StaticLineageProvider` (M1), `RuntimeEvidenceProvider` (M2), `GroundTruthProvider` (M2), `ReasoningEngine` (M4), `StorageRepository` (M3). | Each interface's owner |
| `research/reasoning/engine.py` | `FourStateEngine`. Applies rules R1 to R5 and scans every input for ground-truth tokens. | M4 |
| `research/baselines/baselines.py` | B1 static-only, B2 negative assumption, B3 union, B4 three-state, B5 coverage-gated. | M4 (B1 adapter: M1) |
| `research/metrics/metrics.py` | `evaluate(predictions, truth)` returns confusion counts and every rate defined in the pack. | M4 |
| `scripts/check_import_boundaries.py` | Reads every Python file and fails if a forbidden import appears (for example the reasoning code importing ground truth). | M4 |
| `tests/` | `test_engine_rules.py` (one test per rule), `test_baselines.py`, `test_metrics.py` (hand-computed numbers), `test_leakage.py`, `test_fixtures_plumbing.py`. | M4 |

## 3. Set Up the Repository (Team Lead, About 30 Minutes)

1. Create a private GitHub repository named `data-lineage-engine`. Do not add a README or .gitignore on GitHub (the zip has them).
2. Unzip, then push:

```bash
cd data-lineage-engine
git init -b main
git add .
git commit -m "Initial foundation: contracts, engine, baselines, metrics, CI"
git remote add origin https://github.com/<your-org>/data-lineage-engine.git
git push -u origin main
```

3. Invite the other four members as collaborators.
4. Edit `.github/CODEOWNERS`: replace `@M1-handle` to `@M5-handle` with real GitHub usernames. Commit through a pull request.
5. Protect `main` (Settings, Branches, add a rule for `main`): require a pull request, require at least one approval, require review from code owners, and require the `test` status check from CI. This is what makes "no direct pushes to `main`" real.
6. Confirm CI is green on the first push (Actions tab). If it fails, the log shows which step.
7. Each member creates their branch from `main`:

```bash
git switch -c feature/static-lineage        # M1
git switch -c feature/runtime-groundtruth   # M2
git switch -c feature/bitemporal-storage    # M3
git switch -c feature/reasoning-experiments # M4
git switch -c feature/backend-ui            # M5
```

## 4. Set Up Your Machine (Everyone, About 15 Minutes)

Python 3.11 or newer is required (the foundation was tested on 3.12).

```bash
git clone https://github.com/<your-org>/data-lineage-engine.git
cd data-lineage-engine
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install pytest
python scripts/check_import_boundaries.py     # expect: import boundaries: ok
python -m pytest -q                            # expect: 31 passed, 1 skipped
```

If something goes wrong:

- `ModuleNotFoundError: contracts`: run commands from the repository root, and use `python -m pytest`, not bare `pytest`.
- `31 passed, 1 skipped` is the baseline (the skipped file is the API test, which needs `pip install fastapi httpx`; with those installed you get `34 passed`). If you change shared code and a test you did not write fails, stop and ask the owner.
- Windows and ProvSQL: the ProvSQL spike may need WSL2 (Windows Subsystem for Linux). M2 records what works. Everyone else can develop natively.

## 5. How the Code Fits Together

The pack's central idea, in code terms:

```
static evidence   \
runtime evidence   >-- PredictorInput --> engine or baseline --> predictions -----+
temporal context  /                                                               |
                                                                                  v
ground truth (PROPAGATED / NOT_PROPAGATED) ----------------------------------> metrics
```

Ground truth only meets the predictions at the metrics step. It is never inside `PredictorInput`.

**The five rules of the engine, in plain language.** The first one that matches wins.

| Rule | If this is true | The engine says | Why |
|---|---|---|---|
| R1 | The column identity is missing, or the static analysis of this dependency is unsupported | UNKNOWN | We cannot safely judge it. |
| R2 | There is positive runtime evidence | OBSERVED | Something was actually seen contributing. |
| R3 | Static analysis says it is possible, it is fully supported, and there is a complete negative evaluation | REFUTED_FOR_RUN | Only now can we say "not in this run". |
| R4 | Static analysis says it is possible, but there is neither positive evidence nor a complete negative evaluation | POSSIBLE | Missing events are not evidence of absence. |
| R5 | Nothing at all points to this dependency | UNKNOWN | No basis for a claim. |

**The example fixture** (`contracts/fixtures/w03_case_when*.json`, mock data) models `CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary`.

| Run | Data | Runtime evidence for `salary` | Mock truth for `salary` |
|---|---|---|---|
| A | has US rows | seen, full evidence | PROPAGATED |
| B | no US rows | complete negative evaluation | NOT_PROPAGATED |
| C | no US rows | evidence lost | NOT_PROPAGATED |
| D | has US rows | evidence lost | PROPAGATED |

Run this in the repository root (**ran in a sandbox**; it prints the two lines shown):

```python
from contracts.evidence import PredictorInput
from contracts.mocks.loaders import load_case, load_truth
from research.reasoning.engine import FourStateEngine
from research.baselines.baselines import B2NegativeAssumption
from research.metrics.metrics import evaluate

keys, static, runtime = load_case("w03_case_when")
truth = {r.key: r.label for r in load_truth("w03_case_when")}
inp = PredictorInput(tuple(keys), tuple(static), tuple(runtime))
for name, eng in [("proposed", FourStateEngine()), ("B2", B2NegativeAssumption())]:
    m = evaluate(eng.infer(inp), truth)
    print(name, "false_refutation =", m["false_refutation"],
          "| committed_accuracy =", m["committed_accuracy"])
```

```
proposed false_refutation = 0.0 | committed_accuracy = 1.0
B2 false_refutation = 0.5 | committed_accuracy = 0.625
```

Read this correctly: it shows the code works and the idea can be expressed. It is **8 made-up units, not a research result**. B2 turns lost evidence into false refutations, and the proposed rules do not, but only real ground truth and the pilot can say anything about whether this holds.

## 6. Team Working Rules

- **Branches.** Work on your `feature/...` branch. Never push to `main`. Open a pull request, get the reviewer named in the pack's responsibility matrix, wait for green CI, then merge.
- **Pull request text.** Fill in the ten items: what I tested, environment and versions, what worked, what failed, evidence, files produced, limitations, dependencies on others, recommendation, branch and commit. Never write "it works" unless you ran it.
- **Changing `contracts/`.** Needs a pull request approved by every member whose code touches that type. M4 is the custodian. Freeze date: end of Week 1.
- **Mocks and PLUMBING.** Mocks carry `is_mock=True`. Any number computed from a mock is labelled PLUMBING and must not appear in a report as a finding.
- **Never commit** `.env`, raw datasets, or ProvSQL build output. `data/` is git-ignored.
- **Import boundaries** (checked in CI): reasoning and baseline code never imports `contracts.truth`, `research.ground_truth`, `contracts.interfaces`, `contracts.mocks` or `ingestion`. Ground-truth code never imports `ingestion`, `sqlglot`, `research.reasoning` or `research.baselines`. `research/` never imports `backend` or `frontend`.
- **Log decisions.** Anything that changes the design gets a row in `docs/DECISION_LOG.md` (create it from the pack's Section 48 table). Failed experiments and rejected ideas go in `docs/RESEARCH_LOG.md`. Do not delete them.

## 7. First Team Meeting: Decisions to Make (30 to 45 Minutes)

Fill these in together. They come from the pack's open-decision list. Do not guess answers to the ones that need measurements.

| # | Topic | What to decide | Pack ref |
|---|---|---|---|
| 1 | Who is M1 to M5 | Assign the five workstreams by name. | Section 29 |
| 2 | Environment matrix | Each member fills their row: OS, RAM, Docker, WSL2, PostgreSQL, Python. | D-02 |
| 3 | ProvSQL spike | Who runs it, on which machine, and the time box (short: the pack says do not spend days on installation). | D-15 |
| 4 | Pack owner and CI host | One person keeps the docs current. Confirm GitHub Actions is the CI. | D-20 |
| 5 | Meeting rhythm | For example a short sync every two days, and the date of the four-day checkpoint. | Section 39 |
| 6 | Who settles the hard design questions | M2 and M4 own D-09 (how coverage is derived), D-10 (what counts as positive runtime evidence) and D-11 (ground-truth semantics). M4 owns D-12. Set a date in Week 2. | Section 46 |
| 7 | Kill-criteria session | Book a separate session before the pilot to fill the blank threshold table. | D-01 |

Leave the numbers (seeds, replicate counts, thresholds) open for now. They come after the spike and the first prototypes.
## 8. M1 Guide: Static Lineage

**Your mission.** Answer "what could this query depend on?" and never claim that anything actually ran. You produce `StaticEvidence` objects. The reasoning engine turns them into states later.

**Read first.** Pack Sections 30 (your plan), 14 (how your output is used) and 21 (the CASE example).

**What you implement.** `StaticLineageProvider.extract(sql, schema, dialect)` in `ingestion/sql/`, returning a `StaticExtraction` (see `contracts/interfaces.py`). Later: the dbt manifest adapter and the B1 baseline adapter.

### Day 1

1. `git switch -c feature/static-lineage` and `pip install sqlglot`.
2. Make a corpus folder `ingestion/sql/corpus/`. One JSON file per case, with your **hand-derived** expected dependencies. SQLGlot's output is not the truth, so you decide the expected answer first and then compare. Example:

```json
{
  "case_id": "W03_case_when",
  "sql": "SELECT CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary FROM employees",
  "schema": {"employees": {"country": "text", "salary": "int"}},
  "expected": {"adjusted_salary": ["employees.country", "employees.salary"]},
  "notes": "hand-derived by M1, to be reviewed by M4"
}
```

3. Try SQLGlot's lineage helper. **(ran in a sandbox, sqlglot 30.18.0, PostgreSQL dialect)**:

```python
import hashlib
import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage


def leaves(node):
    if not node.downstream:
        return [node.name]
    return [leaf for child in node.downstream for leaf in leaves(child)]


def column_deps(sql, schema, targets, dialect="postgres"):
    """target column -> sorted list of source columns."""
    out = {}
    for t in targets:
        node = lineage(t, sql, schema=schema, dialect=dialect)
        out[t] = sorted(set(leaves(node)))
    return out


def alias_map(sql, dialect="postgres"):
    tree = sqlglot.parse_one(sql, dialect=dialect)
    return {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}


def has_window(sql, dialect="postgres"):
    return sqlglot.parse_one(sql, dialect=dialect).find(exp.Window) is not None


def count_star_targets(sql, dialect="postgres"):
    tree = sqlglot.parse_one(sql, dialect=dialect)
    return [c.parent.alias for c in tree.find_all(exp.Count)
            if isinstance(c.this, exp.Star) and c.parent is not None]


def fingerprint(sql, dialect="postgres"):
    canonical = sqlglot.parse_one(sql, dialect=dialect).sql(dialect=dialect)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

4. **What I observed**, so you know where the work is (sqlglot 30.18.0; re-check after any upgrade):

| SQL | What SQLGlot returned | What you must do |
|---|---|---|
| `CASE WHEN country='US' THEN salary ELSE 0 END AS adjusted_salary` | `adjusted_salary` from `employees.country` and `employees.salary` | Good: matches the policy (condition and branch columns). |
| `SUM(amount) ... GROUP BY customer_id` | `total` from `orders.amount`; `customer_id` from `orders.customer_id` | Good. |
| `SUM(CASE WHEN status='paid' THEN amount ELSE 0 END)` | `paid` from `orders.amount` and `orders.status` | Good. |
| `COALESCE(amount, 0)` | `orders.amount` | Good. |
| `SELECT * FROM employees` | Worked, because a schema was supplied | Always require the schema. |
| Join with aliases (`orders o JOIN customers c`) | Returned `o.order_id` and `c.name`: **alias names, not table names** | Resolve aliases with `alias_map` before building IDs. |
| `COUNT(*) AS n` | Returned no source column (just `n`) | Emit **dataset-level** evidence (`Granularity.DATASET`), never column edges. |
| `ROW_NUMBER() OVER (...)` | Returned columns as if it were fine | **Mark UNSUPPORTED yourself** (`has_window`). Do not trust lineage to fail. |

5. Build the mapper from lineage output to `StaticEvidence`. It uses `fingerprint` from the snippet above. **(the mapper itself ran in a sandbox on a toy input; wiring it to real lineage output is your work)**:

```python
from contracts.evidence import StaticEvidence
from contracts.types import Granularity, ParserStatus


def to_evidence(sql, schema_fp, src_ds, tgt_ds, src_col, tgt_col, operator, status):
    fp = fingerprint(sql)
    return StaticEvidence(
        evidence_id=f"static:{fp}:{src_col}->{tgt_col}",
        source_dataset_id=src_ds, target_dataset_id=tgt_ds,
        source_column_id=src_col, target_column_id=tgt_col,
        granularity=Granularity.COLUMN, operator=operator,
        expression_fingerprint="TODO", query_fingerprint=fp,
        schema_fingerprint=schema_fp, parser_status=status,
    )
```

6. Unsupported handling. Windows, UDFs (functions SQLGlot does not know), dynamic SQL, unresolved aliases, missing schema and parse errors must each produce `ParserStatus.UNSUPPORTED` plus a diagnostic string. Never guess a dependency.

### Week 1 goals

- Supported subset extracted: projection, aliases, WHERE, CASE, COALESCE, casts, arithmetic, INNER JOIN, CTEs, simple subqueries, GROUP BY, `SUM/AVG/MIN/MAX/COUNT(x)`, `COUNT(*)`, `SELECT *` with schema.
- One corpus file per construct plus at least one unsupported example per category.
- A **construct support matrix** (SUPPORTED, PARTIAL or UNSUPPORTED per construct) in `ingestion/sql/SUPPORT_MATRIX.md`.
- A sample file `contracts/fixtures/static_evidence.sample.json` that M3, M4 and M5 can load.

### Tests to write (`tests/test_static_*.py`)

- Every corpus case: extracted dependencies equal the expected set.
- Aliased join resolves to real table names.
- `COUNT(*)` gives dataset-level evidence and no column edges.
- Window function, UDF, unresolved alias, missing schema and a parse error each give UNSUPPORTED plus a diagnostic.
- Same SQL with different whitespace gives the same `query_fingerprint`.

### Questions to settle with M4

1. Does an aggregate output (`total`) also depend on the `GROUP BY` column (`customer_id`)? The pack says group columns affect grouping identity, but not whether they feed every aggregate output. Decide and write the rule into the support matrix.
2. Is `PARTIAL` ever useful? The engine currently treats PARTIAL as "candidate that can never be refuted".

### Hand-off

Sample static evidence JSON, corpus, support matrix, the B1 adapter (`research/baselines/`, thin wrapper over your provider), and a limitations note.

### Must not

Assign runtime states, read ground truth, import from `research/ground_truth/`, treat SQLGlot output as ground truth, or silently guess unsupported SQL.

## 9. M2 Guide: Runtime Evidence and Ground Truth

**Your mission.** Own two things and keep them apart: what was **observed** at runtime (OpenLineage evidence) and what is **independently true** (ground truth). You are on the critical path early because of the ProvSQL spike.

**Read first.** Pack Sections 13 (ground truth, especially the feasibility gate and D-11), 31 (your plan), and 14 (D-09, D-10).

### Day 1

1. `git switch -c feature/runtime-groundtruth`.
2. Install PostgreSQL locally (native, or inside WSL2 on Windows). Create a database `kairos` and a user. Put the connection string in `.env` (copied from `.env.example`), never in code.
3. `pip install openlineage-python psycopg2-binary`.
4. Write a tiny real ETL in `ingestion/openlineage/etl_demo.py`. Use the CASE example from the fixture: one table where some rows are `'US'` and one where none are, and a query that writes `CASE WHEN country = 'US' THEN salary ELSE 0 END`. **(starting point, not run; needs your PostgreSQL)**:

```python
import psycopg2

conn = psycopg2.connect("dbname=kairos user=kairos host=localhost")   # read from .env
with conn, conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS out_adjusted")
    cur.execute("""
        CREATE TABLE out_adjusted AS
        SELECT country,
               CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary
        FROM employees_a
    """)
```

5. Emit an OpenLineage event **to a file**, not to the API, so you depend on nobody. **(ran in a sandbox: openlineage-python 1.53.0)**:

```python
import datetime
import uuid

from openlineage.client import OpenLineageClient
from openlineage.client.event_v2 import InputDataset, Job, OutputDataset, Run, RunEvent, RunState
from openlineage.client.transport.file import FileConfig, FileTransport

transport = FileTransport(FileConfig(log_file_path="events.jsonl", append=True))
client = OpenLineageClient(transport=transport)
client.emit(RunEvent(
    eventType=RunState.COMPLETE,
    eventTime=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    run=Run(runId=str(uuid.uuid4())),
    job=Job(namespace="kairos_demo", name="clean_orders"),
    producer="https://github.com/<your-org>/data-lineage-engine",
    inputs=[InputDataset(namespace="postgres://localhost:5432", name="public.employees_a")],
    outputs=[OutputDataset(namespace="postgres://localhost:5432", name="public.out_adjusted")],
))
```

6. **Look at the file it wrote.** The event names input and output **datasets**, but says nothing about which **columns** fed which. That is exactly open decision **D-10**: OBSERVED at column level needs column-level runtime evidence. Bring this to M4 in the first week. Do not paper over it by pretending dataset-level events prove column-level propagation.
7. Idempotency key. The events produced above carry no dedicated unique event ID field, so use a hash of the canonical payload:

```python
import hashlib
import json


def payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
```

### The ProvSQL spike (time-boxed)

Create `research/ground_truth/SPIKE_REPORT.md` and log every step as you do it. For each attempt record: OS, PostgreSQL version, compiler, extension version, exact commands, test query, expected output, actual output, limitations, and a command someone else can run to reproduce it. Try in this order: native install, WSL2, Docker only as a last resort. I have **not** verified ProvSQL's installation steps or capabilities, so follow its own documentation and do not assume the pack's claims. Then answer these questions in the report:

- Does it give **tuple-level** provenance only, or also **cell-level** (which input value ended up in which output value)? This decides whether column-level ground truth is possible without borrowing from static analysis (**D-11**).
- What does it say about aggregates, CASE, INNER JOIN, subqueries and NULLs?
- Which SQL constructs does it not support?

Decision tree if it fails: WSL2 next, then Docker (needs a written team decision because of the old no-Docker rule), then build the `ReferenceInterpreterProvider` (a small interpreter for the supported SQL subset that computes column contribution directly).

### Week 1 goals

- ETL runs and writes an events file. Raw events are preserved untouched.
- `RuntimeEvidenceProvider.normalize` turns your events file into `RuntimeEvidence` objects (positives only; never a record for a missing event).
- Spike report has a clear outcome (works, works with WSL2, needs Docker, unusable).
- Sample files in `contracts/fixtures/`: `runtime_evidence.sample.json` and a mock `ground_truth.sample.json`, both with `is_mock: true`.

### Tests to write

- Duplicate event is stored once. Retry gives the same hash. Out-of-order and late events are preserved with diagnostics.
- Normalizer never creates a negative evaluation from missing events.
- Independence test: `tests/test_ground_truth_independence.py` asserts no module under `research/ground_truth/` imports `sqlglot`, `ingestion`, `research.reasoning` or `research.baselines` (the CI checker already enforces this; add a test that asserts the rule itself).

### Hand-off

Spike report, sample runtime and ground-truth JSON, a list of SQL categories the ground truth supports and excludes, and the ground-truth artifact format (versioned and hashed).

### Must not

Feed ground truth into prediction. Import SQLGlot or reasoning code in a ground-truth provider. Derive column-level truth from static analysis. Claim ProvSQL works before you have recorded evidence. Store "no event" as a record.

## 10. M3 Guide: Storage and Bitemporal Lineage

**Your mission.** Be the authority. PostgreSQL is the only source of truth. You own identity, the schema, and the correctness of "what was valid at time X, according to what we knew at time Y".

**Read first.** Pack Sections 10, 11, 12 and 32.

### Day 1

1. `git switch -c feature/bitemporal-storage`. Install PostgreSQL locally and create a database.
2. **Write the oracle first.** Before any SQL, write a plain-Python function that answers the temporal question. Then write the SQL, and check that both give the same answers on the same data (differential testing). This gives you a correctness reference. **(ran in a sandbox)** It reproduces the pack's four-row example:

```python
# backend/app/temporal/reference.py
from datetime import date


def visible(versions, valid_at, known_as_of):
    """Half-open intervals on both time axes. None means open-ended."""
    def inside(lo, hi, t):
        return lo <= t and (hi is None or t < hi)

    return sorted(v["edge"] for v in versions
                  if inside(v["valid_from"], v["valid_to"], valid_at)
                  and inside(v["tx_from"], v["tx_to"], known_as_of))


D = date
versions = [
    # original belief, later closed in transaction time at the correction
    {"edge": "A->B", "valid_from": D(2026, 1, 1), "valid_to": None,
     "tx_from": D(2026, 1, 2), "tx_to": D(2026, 3, 10)},
    # corrected record: the edge really ended on 03-01, learned 03-10
    {"edge": "A->B", "valid_from": D(2026, 1, 1), "valid_to": D(2026, 3, 1),
     "tx_from": D(2026, 3, 10), "tx_to": None},
    # the new edge that replaced it, also learned 03-10
    {"edge": "A->C", "valid_from": D(2026, 3, 1), "valid_to": None,
     "tx_from": D(2026, 3, 10), "tx_to": None},
]
now = D(2026, 9, 20)
assert visible(versions, D(2026, 3, 5), D(2026, 3, 5)) == ["A->B"]    # believed then
assert visible(versions, D(2026, 3, 5), D(2026, 3, 11)) == ["A->C"]   # after the correction
assert visible(versions, D(2026, 3, 5), now) == ["A->C"]              # latest knowledge
assert visible(versions, now, D(2026, 3, 5)) == ["A->B"]              # graph as held on 03-05
assert visible(versions, D(2026, 3, 1), now) == ["A->C"]              # valid_to is exclusive
assert visible(versions, D(2026, 2, 28), now) == ["A->B"]
```

3. Turn those asserts into your first tests. Add "before the interval", "at its start", "inside", "at its end" and "after".
4. Write migration 0001 **(starting point, not run; check it against your PostgreSQL)**. Migrations are numbered files in `backend/migrations/` and are never edited after they are applied. A change is a new file (`0002_...`).

```sql
-- backend/migrations/0001_core.sql
CREATE TABLE dataset (
  id UUID PRIMARY KEY,
  source_system TEXT NOT NULL, namespace TEXT NOT NULL, database_name TEXT NOT NULL,
  schema_name TEXT NOT NULL, name TEXT NOT NULL, asset_type TEXT NOT NULL,
  UNIQUE (source_system, namespace, database_name, schema_name, name, asset_type)
);

CREATE TABLE raw_event (
  event_id TEXT PRIMARY KEY,          -- source event ID, or SHA-256 of the canonical payload
  payload JSONB NOT NULL,
  payload_hash TEXT NOT NULL,
  ingestion_time TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE edge_temporal_version (
  version_id UUID PRIMARY KEY,
  edge_id UUID NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL,     -- revisit for unknown effective time (D-14)
  valid_to TIMESTAMPTZ,
  transaction_from TIMESTAMPTZ NOT NULL,
  transaction_to TIMESTAMPTZ,
  CHECK (valid_to IS NULL OR valid_from < valid_to),
  CHECK (transaction_to IS NULL OR transaction_from < transaction_to)
);

CREATE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'raw evidence is immutable'; END $$ LANGUAGE plpgsql;
CREATE TRIGGER raw_event_immutable BEFORE UPDATE OR DELETE ON raw_event
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

5. The visibility query is the same half-open logic as your oracle:

```sql
SELECT edge_id FROM edge_temporal_version
WHERE valid_from <= :valid_at AND (valid_to IS NULL OR :valid_at < valid_to)
  AND transaction_from <= :known_as_of
  AND (transaction_to IS NULL OR :known_as_of < transaction_to);
```

6. Identity. Write functions that build the canonical dataset, column, job and edge identities from the tuples in Section 10 of the pack. One option (your call): a deterministic UUID version 5 over the normalized tuple, so the same dataset always gets the same ID. Test the tricky cases: same column name in two datasets, quoted identifiers, case differences, renames, schema versions, duplicate events.

### Week 1 goals

- Oracle plus tests passing. Migration 0001 applies from an empty database. SQL results equal oracle results.
- Late correction, deletion, reopening, overlapping intervals and timezone tests written.
- Raw events and evidence immutable (trigger or revoked permissions), with a test that tries to change one and fails.
- Sample lineage records in `contracts/fixtures/` for M4 and M5.
- A first `docs/DATA_MODEL.md` explaining why each column exists.

### Also on your plate

- The `evaluation` schema and a restricted database role for the predictor, so ground truth is physically unreadable by prediction code.
- **D-14** (edges with unknown effective time): propose the handling and have M1 review it.
- **Neo4j: do not start.** First measure PostgreSQL traversal with a recursive query and a depth limit, and report the numbers to the team (decision D-06).

### Hand-off

Migrations, seed script, `PostgresRepository` implementing `StorageRepository`, `DATA_MODEL.md`, temporal fixtures.

### Must not

Redefine SQL semantics or the meaning of the four states. Store four-state results as raw facts in `evidence`. Edit the schema outside numbered migrations. Use detection time in place of a known effective time. Delete or overwrite evidence.

## 11. M4 Guide: Reasoning and Experiments

**Your mission.** Turn evidence into states, and find out honestly whether that helps. You also keep the shared contracts and the research rules.

**What already exists (your starting point).** `research/reasoning/engine.py` (rules R1 to R5), `research/baselines/baselines.py` (B1 to B5), `research/metrics/metrics.py`, the leakage tests and the import checker. They work on mock data and are not validated. Your first job is to **review them critically**, not to trust them.

**Read first.** Pack Sections 14, 15, 20 to 28 and 33.

### Day 1

1. `git switch -c feature/reasoning-experiments`. Read `tests/test_engine_rules.py` first: each test states one rule.
2. Try to break the engine. Change a rule (for example make R4 return REFUTED_FOR_RUN) and see which tests fail. If nothing fails, a test is missing.
3. Collect review comments on `contracts/` from all members. Freeze it at the end of Week 1 (a pull request everyone approves).
4. Decide, with the team, the design questions the first version left open:
   - **R1 before R2.** The contract's order makes unsupported static semantics win even when a positive event exists. Keep it, or explain why not.
   - **PARTIAL static.** Currently it can never lead to REFUTED_FOR_RUN.
   - **D-12.** Which pairs are scored (candidates plus observed, or the full cross product). `evaluate()` currently scores only units present in both predictions and truth, and reports the rest.
   - **D-09.** How the engine learns what evidence was lost. See the note below.
5. Write the loss simulator in `research/missingness/`. Start with random loss (the MCAR mechanism). **(ran in a sandbox)** A seeded version that records the removed events and a mask hash:

```python
import hashlib
import random


def mcar_loss(event_ids, level_pct, seed):
    ids = sorted(event_ids)
    k = round(len(ids) * level_pct / 100)
    removed = set(random.Random(seed).sample(ids, k))
    kept = [e for e in ids if e not in removed]
    mask = ("|".join(sorted(removed)) + f"#{level_pct}#{seed}").encode()
    return kept, sorted(removed), hashlib.sha256(mask).hexdigest()[:16]
```

   Same seed gives the same loss; a different seed gives a different one. Then add operator, dataset, branch, complete-run and correlated loss. Levels are 0, 10, 30, 50, 70 and 90 percent.

6. Write the protocol file `research/protocol/v1.yaml` from the skeleton in the pack (Section 42). Every unknown stays `TBD`. Make the runner **refuse to run a real experiment while any value is `TBD`**; only a run flagged `--plumbing` may.
7. Write the runner skeleton `research/experiments/run.py`: load protocol, load case, apply loss, run the engine and baselines, load ground truth **only after** predictions exist, call `evaluate`, write a result file to `research/results/`. Every result must record: benchmark version, protocol version, loss mechanism and level, seed, removed-event hash, ground-truth hash, prediction hash, Git SHA, environment, and database and provider versions.

> **The hardest design question is yours and M2's (D-09).** After the simulator removes events, the engine must know what was lost **only as much as a real capture layer could know**, or the experiment cheats. Two options: a manifest saying which operators, datasets and branches the capture layer covered, or integrity signals such as sequence numbers that reveal gaps. Random single-event loss may be invisible under the first. If coverage cannot be derived reliably, that is kill criterion K6 and the pack says to report it.

### Week 1 goals

- Contracts frozen. Engine and baselines reviewed, with any change accompanied by a new test.
- MCAR simulator with tests (same seed same result, level respected, mask hash stable).
- Metrics tests still pass and any new metric has a hand-computed test.
- Protocol skeleton and a runner that works in `--plumbing` mode on the fixture.
- A written proposal for D-09, D-10, D-12 to discuss with M2 and M1.

### Also on your plate

- Facilitate the kill-criteria session (D-01) before the pilot. The threshold table in the pack is blank on purpose.
- Confidence intervals (D-08). Units inside one case are correlated, so consider resampling at the case-and-replicate level.
- Ablations. Some are expected to equal a baseline (for example "no coverage" behaves like B2). Report that; do not count it as independent evidence.

### Hand-off

Frozen `contracts/`, the reviewed engine and baselines, the protocol, the runner with usage notes, and later the results and failure analysis.

### Must not

Read ground truth during prediction. Change the protocol after seeing final results. Tune on held-out cases. Invent thresholds. Report PLUMBING outputs as findings.

## 12. M5 Guide: API and UI

**Your mission.** Make the system usable and inspectable. Build against mocks first. You also own integration and reproducibility.

**What already exists.** `backend/app/main.py` is a tiny FastAPI app. It has `/api/v1/health`, the stable error shape, and one route that runs the **real** four-state engine on the mock fixture. Tests for it are in `tests/test_api_slice.py`. **(ran in a sandbox: FastAPI 0.141.1)**

**Read first.** Pack Sections 17, 19 and 34.

### Day 1

1. `git switch -c feature/backend-ui`, then `pip install fastapi uvicorn httpx`.
2. Run the API and try it:

```bash
uvicorn backend.app.main:app --reload
# open http://127.0.0.1:8000/docs   (interactive OpenAPI page)
# try: /api/v1/runs/run_C/dependency/employees.salary/out.adjusted_salary
```

Expected: state `POSSIBLE` with the warning `NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE`. Run B gives `REFUTED_FOR_RUN` and run A gives `OBSERVED`. All of it is mock data.

3. Replace the loose dictionary response with Pydantic models from Section 17: `DependencyResponse` (state, interpretation, coverage, evidence list, reasoning version, warnings, temporal context) and `LineageResponse` (nodes, edges, temporal context, `truncated`). Every route needs a request model, a response model, status codes, examples and a test.
4. Add the remaining routes from the pack's table against a mock repository: search, lineage, upstream, downstream, runs, run lineage, evidence. Keep `as_of` (valid time) and `recorded_as_of` (transaction time) as separate parameters. Decision **D-13** (canonical IDs versus names in URLs) is yours with M3.
5. The API layer coordinates only. Parsing belongs to M1, storage and time logic to M3, reasoning to M4.

### The UI (Stage 1 only until accepted)

1. Create it with `npm create vite@latest frontend -- --template react` **(not run here)**.
2. Time-box a small spike comparing two graph libraries (React Flow and Cytoscape.js are the candidates). Compare directed edges, custom nodes and edges, zoom and pan, and how each behaves on a graph size the team agrees on. Record the result (**D-17**). Do not assume a winner.
3. Build against the mock API, in this order: search box, graph with a depth control, click a node for details, click an edge for the evidence panel.
4. **Two separate date controls: "Valid at" and "Known as of".** Never merge them. Whenever either is set, show a banner: "Showing historical lineage. Valid at X. Known as of Y."
5. Use the four state sentences from Section 19 of the pack word for word. Show each state with a text label and an icon or pattern, never colour alone. Never show a numeric confidence. Never draw a POSSIBLE edge so that it looks like absence.

### Also on your plate

- README steps and scripts so a second person can set up from a clean checkout. Ask a teammate to try it.
- Later stages (run page, filters, impact analysis) only after Stage 1 passes the acceptance list in the pack.

### Hand-off

OpenAPI file, a demo script, UI build instructions and the acceptance-checklist result.

### Must not

Reimplement parsing, storage or reasoning in the API or UI. Add authentication. Build beyond Stage 1 early. Show ground truth outside a clearly labelled evaluation mode. Use the word "confidence".

## 13. Week 1 and the Four-Day Checkpoint

A suggested shape (adjust to your calendar). The checkpoint reviews whether the design can proceed. **It is not evidence that the research idea is true.**

| Day | Everyone | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|---|
| 1 | Repo set up, machines ready, first meeting | SQLGlot spike, first corpus files | ETL plus events file, start ProvSQL | Oracle, migration 0001 | Review engine, contracts PR | API on mocks, graph spike |
| 2 | Mock samples shared in `contracts/fixtures/` | Extraction for core constructs | Normalizer, spike log | Temporal tests, identity | MCAR simulator | Pydantic schemas |
| 3 | First tests against contracts | Support matrix | Spike outcome drafted | Immutability, D-14 proposal | Protocol skeleton, plumbing runner | Routes on mocks, UI shell |
| 4 | **Checkpoint review** | Report | Report | Report | Report | Report |

At the checkpoint, answer these nine questions with evidence:

1. Is ProvSQL feasible, or which fallback applies? (M2: spike report)
2. Does static extraction work on the intended SQL subset? (M1: corpus tests, support matrix)
3. Can runtime evidence be captured? (M2: events file and normalizer)
4. Is the evidence schema sufficient? (M3: migration applied, sample data stored)
5. Does the bitemporal model work? (M3: the four-row example reproduced by tests)
6. Can the reasoning engine run on mocks? (M4: rule tests pass)
7. Is the protocol runnable? (M4: `--plumbing` run end to end)
8. Can the benchmark be generated? (M4 with M1, M2: case format and one case file)
9. Does the architecture need changes? (all: a written list, each with a decision-log row)

## 14. Common Mistakes

- Reporting the fixture numbers (`false_refutation 0.0 versus 0.5`) as a result. They are plumbing on made-up data.
- Editing a shared contract without review, or "fixing" a leakage test instead of the code.
- Importing ground truth into reasoning or baseline code, or importing SQLGlot into a ground-truth provider.
- Getting column-level ground truth by asking SQLGlot which columns matter (that destroys independence).
- Storing "no event was seen" as any kind of row.
- Using the time Kairos noticed a change as the time the change happened.
- Assuming dataset-level OpenLineage events prove column-level propagation.
- Committing `.env`, datasets or build output. Pushing to `main`.
- Writing "it works" without running it, or leaving a number in a report that nobody measured.

## 15. What Is Not Built Yet and Honest Limits

- **Not built:** ProvSQL spike and providers, SQLGlot adapter, dbt adapter, ETL, database migrations and temporal queries, identity functions, Neo4j (deliberately deferred), real API routes and schemas beyond the slice, the UI, the loss simulator, the protocol and the runner, the benchmark cases, and every experiment.
- **The engine is unvalidated.** It follows the pack's rules on mock data. Real data will expose gaps, and the design questions in Section 11 are still open.
- **Snippets marked "not run"** (PostgreSQL DDL, the ETL, the SQLGlot-to-evidence mapper, the UI setup) are starting points.
- **Library versions matter.** SQLGlot's behaviour was observed on 30.18.0, OpenLineage on 1.53.0 and FastAPI on 0.141.1. Freeze versions when your first build works.
- **CI has been run locally only.** The first push to GitHub will show whether the workflow needs adjusting.
- **Prior-art citations and product claims** in the pack were carried over from earlier notes and still need re-checking before any public presentation.

## 16. Quick Reference

```bash
# every day
git switch feature/<your-branch> && git pull --rebase origin main
python scripts/check_import_boundaries.py
python -m pytest -q

# open a pull request
git add -A && git commit -m "M<n>: <what and why>"
git push -u origin feature/<your-branch>
# then open the PR on GitHub, fill the ten-item report, request your reviewer

# regenerate the mock fixtures (only if you change the fixture design)
python scripts/make_fixtures.py
```

| Question | Where to look |
|---|---|
| What does a state mean? | Pack Section 15 and the four sentences in Section 19 |
| What am I allowed to import? | Section 6 of this guide, and `scripts/check_import_boundaries.py` |
| What are the open decisions? | Pack Section 46 (D-01 to D-20) |
| Why was something decided this way? | Pack Section 47 (conflict table) and Section 48 (decision log) |
| Who reviews my pull request? | Pack Section 29 (responsibility matrix) |
