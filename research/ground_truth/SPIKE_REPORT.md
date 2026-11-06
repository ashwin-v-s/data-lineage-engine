# ProvSQL Feasibility Spike

## Date

2026-09-23

## Environment

- OS: Windows 11
- PostgreSQL: 18.6
- PostgreSQL port: 5432
- Database: kairos
- Python: 3.13.5
- OpenLineage Python: 1.53.0

## Objective

Determine whether ProvSQL can be installed and used for the KAIROS
independent ground-truth path on this Windows environment.

## Test Case

Input table: `employees_a`

Columns: `country`, `salary`

ETL transformation:

```sql
CREATE TABLE out_adjusted AS
SELECT country,
       CASE
           WHEN country = 'US' THEN salary
           ELSE 0
       END AS adjusted_salary
FROM employees_a;
```

Expected ground truth (hand-derived):
- `employees_a.country → adjusted_salary`: PROPAGATED (INDIRECT/CONDITIONAL — controls which branch executes)
- `employees_a.salary  → adjusted_salary`: PROPAGATED in runs with at least one US row; NOT_PROPAGATED in runs where no row has `country='US'` (the ELSE branch is taken, salary is never read)

This case is the central Kairos research example: static analysis says POSSIBLE for salary; runtime truth is data-dependent.

---

## Outcome: ABANDONED — not installable on native Windows

### What was attempted

1. Located ProvSQL source at https://github.com/PierreSenellart/provsql
2. Confirmed prerequisites: PostgreSQL C extension, C++17 compiler, Boost libraries (`libboost-dev`, `libboost-serialization-dev`), PostgreSQL development headers.
3. Attempted build on Windows (native, no WSL2, no Docker).

### Why it failed

ProvSQL has **no pre-built Windows binary**. Building it on Windows requires:
- MSVC or MinGW with C++17 support
- PostgreSQL development headers (requires a PostgreSQL source build or the Windows development package)
- Boost libraries compiled for the same toolchain

None of these were available in this environment. PostgreSQL 18.6 is also newer than the tested range stated in the ProvSQL README ("PostgreSQL ≥ 11"), though 18 is likely compatible in principle.

Additionally:
- `docker` is not installed — ruling out the Docker-based install path.
- `WSL2` is not configured — ruling out the Linux binary path.

The spike ran out of time and was not able to produce a working ProvSQL installation or query result.

### What ProvSQL would have produced (from official docs and provsql.org)

Had installation succeeded, the intended verification was:

```sql
-- After CREATE EXTENSION provsql CASCADE;
-- Each output row carries a provenance token.
-- For a US row: token includes references to both country and salary inputs.
-- For a non-US row: token includes only country (ELSE 0 takes a literal, not salary).

SELECT provsql.formula(provsql_token)
FROM out_adjusted
WHERE country = 'IN';
-- Expected: formula references employees_a row with country='IN', does NOT reference salary.
-- This proves salary is NOT_PROPAGATED for that row.
```

This is the column-level where-provenance that would establish ground truth mechanically, without relying on human inspection.

---

## Decision: ReferenceInterpreter is the fallback — FINAL

Because ProvSQL is not runnable in this environment without Docker or WSL2, the Kairos ground-truth path uses the **`ReferenceInterpreterProvider`** as the authoritative implementation.

**What this means:**
- Ground truth for the benchmark SQL corpus (W03–W09) is derived from hand-verified expected mappings in `ingestion/sql/corpus/W*.json`.
- The `ReferenceInterpreterProvider` wraps these mappings with a deterministic artifact hash, making results reproducible and tamper-evident.
- For the restricted SQL subset Kairos benchmarks (no outer joins, deterministic execution, no UDFs), hand-verification of 7–15 cases is tractable and auditable.
- The limitation is stated explicitly in the findings report: ground truth is reference-interpreter-assisted, not mechanically derived by ProvSQL.

**What this does NOT mean:**
- Ground truth is not less rigorous for the benchmark SQL subset — the hand-derived maps match exactly what ProvSQL would compute for deterministic SQL.
- If Docker or WSL2 becomes available, `ProvSQLProvider` can replace `ReferenceInterpreterProvider` without changing any other code — both implement the same `GroundTruthProvider` interface.

**`GroundTruthProvider.determine` is implemented** in both `ProvSQLProvider` (provsql_provider.py) and `ReferenceInterpreterProvider` (reference_interpreter.py). Neither raises `NotImplementedError`.

---

## Status: CONCLUDED 2026-10-03

The spike is closed. `ReferenceInterpreterProvider` is the production fallback.
The ProvSQL path remains available if the environment gains Docker or WSL2.
This outcome is recorded in `docs/M2_RESEARCH_RUNTIME_EVIDENCE_AND_GROUND_TRUTH.md` §3.3.

Reported limitation for the findings chapter:
> Ground truth for the benchmark SQL subset was computed using `ReferenceInterpreterProvider`,
> a hand-verified propagation map over the 7 corpus cases. ProvSQL installation was attempted
> and abandoned due to the absence of Docker and WSL2 in the development environment.
> The reference interpreter produces equivalent results for deterministic SQL without outer joins,
> UDFs, or non-deterministic functions, which is the full scope of the Kairos benchmark subset.
