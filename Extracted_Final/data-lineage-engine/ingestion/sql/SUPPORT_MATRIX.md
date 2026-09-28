# M1: SQL Construct Support Matrix

**Version:** 1.0-mvp  
**Owner:** M1  
**Status:** LOCKED (frozen at Week 1)  
**Last Updated:** 2026-09-23

This document defines which SQL constructs are supported, partially supported, or unsupported in MVP-1. Unsupported constructs trigger `ParserStatus.UNSUPPORTED` and prevent lineage extraction.

---

## Summary Table

| Construct | Status | Granularity | Notes |
|---|---|---|---|
| **Projection** (SELECT col FROM ...) | SUPPORTED | COLUMN | Basic column selection |
| **Column aliases** (SELECT col AS alias) | SUPPORTED | COLUMN | Aliases resolved and tracked |
| **Table aliases** (FROM tbl AS t) | SUPPORTED | COLUMN | Table aliases resolved via alias_map |
| **Multiple tables** (FROM a, b) | SUPPORTED | COLUMN | Cross join treated as implicit join |
| **WHERE clause** | SUPPORTED | COLUMN | Filter columns included in dependencies |
| **CASE WHEN** | SUPPORTED | COLUMN | Condition + all branch columns feed output |
| **COALESCE** | SUPPORTED | COLUMN | All column arguments feed output |
| **Type casts** (CAST(col AS type)) | SUPPORTED | COLUMN | Source column feeds output |
| **Arithmetic** (col1 + col2) | SUPPORTED | COLUMN | All operands feed output |
| **INNER JOIN** | SUPPORTED | COLUMN | Both tables' columns per lineage; aliases resolved |
| **CTEs** (WITH cte AS (...) SELECT) | SUPPORTED | COLUMN | CTE result columns feed parent references |
| **Subqueries** (SELECT FROM (SELECT ...)) | SUPPORTED | COLUMN | Subquery result columns feed parent |
| **GROUP BY** | SUPPORTED | COLUMN | Aggregates track source columns; group semantics TBD with M4 |
| **Aggregates** (SUM, AVG, MIN, MAX, COUNT(col)) | SUPPORTED | COLUMN | Column argument feeds output |
| **COUNT(\*)** | SUPPORTED | DATASET | Emits dataset-level evidence only; no column edges |
| **SELECT \*** | SUPPORTED | COLUMN | Requires schema; expands to all columns |
| **ORDER BY** | SUPPORTED | COLUMN | Order columns treated as dependencies |
| **DISTINCT** | SUPPORTED | COLUMN | All selected columns feed output |
| **UNION** | SUPPORTED | COLUMN | Matching columns across branches feed output |
| **LIMIT/OFFSET** | SUPPORTED | COLUMN | All selected columns feed output (no row selection) |

---

## Unsupported Constructs (UNSUPPORTED Status)

| Construct | Why | Diagnostic Message |
|---|---|---|
| **Window functions** (ROW_NUMBER() OVER, RANK() OVER, etc.) | Unclear semantics for column contribution; out of MVP scope | `"Window function not supported in MVP"` |
| **User-defined functions (UDFs)** | Unknown behavior; SQLGlot cannot analyze | `"User-defined function not supported"` |
| **Dynamic SQL** (EXECUTE ... USING) | Cannot statically analyze | `"Dynamic SQL not supported"` |
| **LEFT/RIGHT/FULL OUTER JOIN** | Ground truth via ProvSQL cannot handle outer joins | `"Outer join ({type}) not supported in MVP"` |
| **Missing or empty schema** | Cannot expand SELECT * or resolve columns | `"Empty or missing schema"` |
| **SQL parse errors** (malformed syntax) | SQLGlot parser fails | `"SQL parse error: {error details}"` |
| **Unresolved aliases** (referencing undefined tables) | Cannot build correct identities | `"Unresolved alias or missing table"` |

---

## Partially Supported Constructs (PARTIAL Status)

Currently, M1 does not emit `PARTIAL` status. All constructs are either `SUPPORTED` or `UNSUPPORTED`. This may change per M4's guidance.

---

## Group BY Semantics (PENDING Decision D-04)

**Question:** Does `GROUP BY customer_id` mean `customer_id` is a dependency for every `SUM(amount)` output?

**Current behavior:** Group columns are included in lineage output from SQLGlot. Each aggregate output depends on both its operand (e.g., `amount` for `SUM(amount)`) and all group columns.

**Example:**
```sql
SELECT customer_id, SUM(amount) AS total
FROM orders
GROUP BY customer_id
```

**Extracted dependencies:**
- `total` depends on `orders.amount` and `orders.customer_id`

**Rationale:** Group columns define the identity of output rows; without them, the aggregation is incomplete.

**Pending:** M4 may propose an alternative interpretation. See pack decision D-04.

---

## Supported SQL Patterns: Week 1 Test Coverage

### Pattern 1: Basic Projection
```sql
SELECT col1, col2 FROM table
```
**Result:** col1 → output.col1, col2 → output.col2

---

### Pattern 2: Column Aliases
```sql
SELECT col1 AS renamed_col FROM table
```
**Result:** col1 → output.renamed_col

---

### Pattern 3: WHERE Filters
```sql
SELECT col1 FROM table WHERE col2 = 'value'
```
**Result:** col1 and col2 both feed output (filter columns matter)

---

### Pattern 4: CASE Expressions
```sql
SELECT CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted FROM employees
```
**Result:** Both `country` (condition) and `salary` (then branch) feed output

---

### Pattern 5: Aggregates with GROUP BY
```sql
SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id
```
**Result:** `total` depends on `orders.amount` and `orders.customer_id`

---

### Pattern 6: INNER JOIN with Table Aliases
```sql
SELECT o.id, c.name FROM orders o INNER JOIN customers c ON o.customer_id = c.id
```
**Result:** o.id → orders.id, c.name → customers.name (aliases resolved)

---

### Pattern 7: COUNT(\*)
```sql
SELECT COUNT(*) AS row_count FROM orders
```
**Result:** Dataset-level evidence only; `Granularity.DATASET`, source_column_id=null

---

### Pattern 8: SELECT \* with Schema
```sql
SELECT * FROM employees
```
**Result:** Output.id → employees.id, output.name → employees.name, etc. (expands via schema)

---

### Pattern 9: COALESCE
```sql
SELECT COALESCE(email, phone, 'unknown') AS contact FROM users
```
**Result:** `contact` depends on `users.email` and `users.phone`

---

### Pattern 10: CTEs (Common Table Expressions)
```sql
WITH cte AS (SELECT col1 FROM source)
SELECT col1 FROM cte
```
**Result:** CTE output column depends on source column

---

## Unsupported Patterns: MVP Exclusions

### Pattern: Window Functions
```sql
SELECT row_number() OVER (PARTITION BY dept ORDER BY salary) AS rank FROM employees
```
**Status:** UNSUPPORTED  
**Reason:** Window function semantics unclear for column contribution

---

### Pattern: LEFT OUTER JOIN
```sql
SELECT o.id, c.name FROM orders o LEFT JOIN customers c ON o.customer_id = c.id
```
**Status:** UNSUPPORTED  
**Reason:** Ground truth via ProvSQL does not support outer joins

---

### Pattern: Dynamic SQL
```sql
EXECUTE 'SELECT * FROM ' || table_name USING table_name
```
**Status:** UNSUPPORTED  
**Reason:** Cannot statically analyze dynamic statements

---

## Fingerprinting & Determinism

**Rule:** Same SQL with different whitespace must produce identical `query_fingerprint`.

**Implementation:** Normalize SQL via `sqlglot.parse_one(sql).sql(dialect)` then SHA-256[:16].

**Test:** See `tests/test_static_fingerprints.py`

---

## Evidence Production Rules

1. **Never store absence.** No `StaticEvidence` is produced for "we found no dependency". Only positive dependencies are recorded.
2. **Deduplicate.** If the same (source, target) pair is found multiple times in one query, emit it once.
3. **Include filter columns.** WHERE, JOIN conditions, and CASE conditions are dependencies.
4. **Resolve aliases before building IDs.** `orders o` → aliases.get('o', 'o') → 'orders'
5. **Mark unsupported immediately.** As soon as a disqualifying construct is detected, return `ParserStatus.UNSUPPORTED` with diagnostics.

---

## Open Decisions

| Decision ID | Topic | Owner | Status |
|---|---|---|---|
| D-04 | GROUP BY semantics: are group columns dependencies for every aggregate? | M4 | PENDING |
| D-11 | Column-level ground truth: how is it derived from ProvSQL? | M2 | PENDING |

---

## Changelog

- **2026-09-23:** Initial version. Locked for MVP-1.
