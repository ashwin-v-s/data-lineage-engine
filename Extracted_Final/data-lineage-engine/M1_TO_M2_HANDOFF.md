# M1 → M2 Handoff: SQL Corpus Test Cases

**For:** M2 (Runtime Evidence & Ground Truth)  
**From:** M1 (Static Metadata Ingestion & SQL Lineage)  
**Purpose:** M2 can now generate synthetic OpenLineage runtime events using M1's corpus  
**Date:** Week 1 Complete  
**Status:** ✅ READY FOR USE

---

## Overview

M1 has completed the SQL corpus—12 test cases covering supported and unsupported SQL constructs. M2 can now independently generate synthetic runtime events for these cases **without waiting for M1's SQLGlot implementation details**.

**Key Point:** M2 is **not dependent on M1's reasoning or static lineage extraction logic**. M2 only needs:
1. The SQL queries
2. The schema
3. The expected column dependencies (what M2 should observe at runtime)

---

## Available SQL Test Cases

### Supported Constructs (7 cases — can generate runtime events)

#### W03_case_when ✅
```json
{
  "case_id": "W03_case_when",
  "description": "CASE WHEN with condition and branch columns",
  "sql": "SELECT CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary FROM employees",
  "schema": {
    "employees": {"id": "int", "name": "text", "country": "text", "salary": "int"}
  },
  "target_dataset": "employees",
  "expected": {
    "adjusted_salary": ["employees.country", "employees.salary"]
  }
}
```
**Runtime Event Generated:** When SQL executes on sample data (e.g., rows with US/non-US), capture observations that `country` and `salary` both feed `adjusted_salary`.

---

#### W04_aggregate_sum ✅
```json
{
  "case_id": "W04_aggregate_sum",
  "description": "SUM aggregate with implicit source column dependency",
  "sql": "SELECT SUM(amount) AS total_amount FROM orders",
  "schema": {
    "orders": {"id": "int", "customer_id": "int", "amount": "numeric", "order_date": "date"}
  },
  "target_dataset": "orders",
  "expected": {
    "total_amount": ["orders.amount"]
  }
}
```
**Runtime Event Generated:** Observe that `orders.amount` feeds `total_amount`.

---

#### W05_join_alias ✅
```json
{
  "case_id": "W05_join_alias",
  "description": "INNER JOIN with table aliases",
  "sql": "SELECT o.order_id, c.name FROM orders o INNER JOIN customers c ON o.customer_id = c.id",
  "schema": {
    "orders": {"order_id": "int", "customer_id": "int"},
    "customers": {"id": "int", "name": "text"}
  },
  "expected": {
    "order_id": ["orders.order_id"],
    "name": ["customers.name"]
  }
}
```
**Runtime Event Generated:** Observe that `orders.order_id` and `customers.name` are outputs.

---

#### W06_count_star ✅
```json
{
  "case_id": "W06_count_star",
  "description": "COUNT(*) — dataset-level evidence only",
  "sql": "SELECT COUNT(*) AS row_count FROM orders",
  "schema": {
    "orders": {"id": "int", "amount": "numeric"}
  },
  "target_dataset": "orders",
  "expected": {
    "row_count": []
  }
}
```
**Runtime Event Generated:** Observe dataset-level event (no column-level evidence). M4 will use this to test "no column edges from COUNT(*)".

---

#### W07_select_star ✅
```json
{
  "case_id": "W07_select_star",
  "description": "SELECT * — must expand to all columns",
  "sql": "SELECT * FROM employees",
  "schema": {
    "employees": {"id": "int", "name": "text", "salary": "int", "country": "text"}
  },
  "target_dataset": "employees",
  "expected": {
    "id": ["employees.id"],
    "name": ["employees.name"],
    "salary": ["employees.salary"],
    "country": ["employees.country"]
  }
}
```
**Runtime Event Generated:** Observe all 4 columns map to themselves.

---

#### W08_where_filter ✅
```json
{
  "case_id": "W08_where_filter",
  "description": "WHERE clause — filter columns included in dependencies",
  "sql": "SELECT salary FROM employees WHERE country = 'US'",
  "schema": {
    "employees": {"id": "int", "name": "text", "country": "text", "salary": "int"}
  },
  "target_dataset": "employees",
  "expected": {
    "salary": ["employees.country", "employees.salary"]
  }
}
```
**Runtime Event Generated:** Observe that both `country` (filter) and `salary` (select) feed the output.

---

#### W09_coalesce ✅
```json
{
  "case_id": "W09_coalesce",
  "description": "COALESCE — all arguments feed output",
  "sql": "SELECT COALESCE(email, phone, 'unknown') AS contact FROM users",
  "schema": {
    "users": {"id": "int", "email": "text", "phone": "text"}
  },
  "target_dataset": "users",
  "expected": {
    "contact": ["users.email", "users.phone"]
  }
}
```
**Runtime Event Generated:** Observe that both `email` and `phone` feed `contact`.

---

### Unsupported Constructs (5 cases — generate UNSUPPORTED markers, no runtime events)

#### UNSUPPORTED_missing_schema ❌
```json
{
  "case_id": "UNSUPPORTED_missing_schema",
  "description": "SELECT * without schema — cannot expand",
  "sql": "SELECT * FROM unknown_table",
  "expected": null
}
```
**For M2:** Don't generate runtime events. M4 will see `UNSUPPORTED` marker.

---

#### UNSUPPORTED_outer_join ❌
```json
{
  "case_id": "UNSUPPORTED_outer_join",
  "description": "LEFT OUTER JOIN — out of MVP scope",
  "sql": "SELECT o.id, c.name FROM orders o LEFT JOIN customers c ON o.customer_id = c.id",
  "expected": null
}
```
**For M2:** Don't generate runtime events. This is an MVP-scope boundary.

---

#### UNSUPPORTED_parse_error ❌
```json
{
  "case_id": "UNSUPPORTED_parse_error",
  "description": "SQL syntax error",
  "sql": "SELECT FROM WHERE",
  "expected": null
}
```
**For M2:** Don't generate runtime events. Parser fails.

---

#### UNSUPPORTED_window_function ❌
```json
{
  "case_id": "UNSUPPORTED_window_function",
  "description": "Window function — not supported",
  "sql": "SELECT row_number() OVER (PARTITION BY department ORDER BY salary DESC) AS rank FROM employees",
  "expected": null
}
```
**For M2:** Don't generate runtime events. This is intentionally unsupported.

---

## How M2 Uses This

### Step 1: Load the Corpus
```python
import json

corpus_dir = "ingestion/sql/corpus"
cases = {}

for case_file in os.listdir(corpus_dir):
    if case_file.endswith(".json"):
        with open(f"{corpus_dir}/{case_file}") as f:
            case = json.load(f)
            cases[case["case_id"]] = case
```

### Step 2: For Each Supported Case, Generate Synthetic Data + Events

**For W03_case_when:**
```python
case = cases["W03_case_when"]

# Generate synthetic data with different loss conditions
data_with_us = [
    {"id": 1, "country": "US", "salary": 100000},
    {"id": 2, "country": "US", "salary": 120000}
]

data_no_us = [
    {"id": 3, "country": "CA", "salary": 90000},
    {"id": 4, "country": "MX", "salary": 85000}
]

# Run SQL on each, capture events
# For data_with_us: OBSERVED: employees.country → adjusted_salary
#                           employees.salary → adjusted_salary
#
# For data_no_us:   OBSERVED: employees.country → adjusted_salary
#                   NOT_OBSERVED: employees.salary → adjusted_salary (lost evidence)
```

### Step 3: Emit OpenLineage Events
```python
from openlineage.client.event_v2 import InputDataset, OutputDataset, RunEvent

event = RunEvent(
    eventType=RunState.COMPLETE,
    run=Run(runId="run_A_w03_case_when"),
    job=Job(namespace="kairos.demo", name="case_when_demo"),
    inputs=[
        InputDataset(namespace="postgres://local", name="public.employees")
    ],
    outputs=[
        OutputDataset(namespace="postgres://local", name="public.adjusted_salary_output")
    ],
    # Column-level facets here (if using OpenLineage column lineage extension)
)
```

### Step 4: Build RuntimeEvidence Objects for M4
M2 converts the captured events into `RuntimeEvidence` objects (from `contracts.evidence`).

---

## Files Location

| File | Purpose |
|------|---------|
| `ingestion/sql/corpus/W03_case_when.json` | CASE WHEN test case |
| `ingestion/sql/corpus/W04_aggregate_sum.json` | Aggregate test case |
| `ingestion/sql/corpus/W05_join_alias.json` | JOIN test case |
| `ingestion/sql/corpus/W06_count_star.json` | COUNT(*) test case |
| `ingestion/sql/corpus/W07_select_star.json` | SELECT * test case |
| `ingestion/sql/corpus/W08_where_filter.json` | WHERE filter test case |
| `ingestion/sql/corpus/W09_coalesce.json` | COALESCE test case |
| `ingestion/sql/corpus/UNSUPPORTED_*.json` | Unsupported cases (5 files) |

All in: `ingestion/sql/corpus/`

---

## What M2 Can Do Now

✅ **Independently generate synthetic OpenLineage events** for W03-W09  
✅ **Create RuntimeEvidence objects** without waiting for M1's SQLGlot output  
✅ **Test M4's reasoning engine** with synthetic event combinations  
✅ **Simulate different loss conditions** (complete evidence, partial, missing)  
✅ **Generate ground truth candidates** for validation  

---

## Dependencies & Change Notifications

### M2 Does NOT Depend On
- M1's SQLGlot adapter implementation
- M1's static lineage extraction logic
- M1's parser status detection

### M2 DOES Depend On
- **Schema definitions** in each corpus file (these are static and won't change much)
- **Expected column dependencies** in `expected` field (these are M1's domain expertise, frozen)
- **Case IDs** and **SQL queries** (these are the benchmark definition)

### If M1 Changes a Corpus File
M2 should:
1. Detect which case changed
2. Regenerate synthetic data + events for that case
3. Re-run M4 reasoning pipeline with new events

**Suggestion:** M2 can add a `schema_hash` or `case_version` field to corpus files so M2 can detect changes automatically.

---

## Questions for M2

1. **Do you need PostgreSQL running, or can you mock the execution?**  
   → The corpus has schema; M2 can generate fake data in memory and emit OpenLineage events without actual DB execution.

2. **Which OpenLineage version are you using?**  
   → Check `pyproject.toml` for pinned version.

3. **Do you need column-level lineage in events, or just dataset-level?**  
   → The corpus has `expected` at column level. M2 should emit column-level events (OpenLineage supports facets for this).

4. **How do you represent the different loss levels?**  
   → M2 controls which events are "observed" vs. "lost". Same query, different event capture scenarios = different loss levels.

---

## Summary for M2

✅ **All 12 SQL test cases ready**  
✅ **Schema defined for each**  
✅ **Expected dependencies documented**  
✅ **You can start generating runtime events immediately**  
✅ **You do NOT need to wait for M1's implementation**  
✅ **You DO need to integrate with M3's ground truth provider and M4's reasoning engine**

**Next Step:** M2 should coordinate with M4 to finalize D-10 (what counts as positive runtime evidence) and D-11 (ground truth semantics) before finalizing the synthetic event format.

---

**Generated:** Week 1 Complete  
**Contact:** M1 with questions about corpus schema or expected lineage  
**Status:** ✅ HANDOFF READY
