# ingestion/sql (M1): Static Lineage Extraction

**Status:** IMPLEMENTED (MVP-1)  
**Owner:** M1  
**Version:** 1.0-mvp

SQLGlot adapter implementing `contracts.interfaces.StaticLineageProvider.extract(sql, schema, dialect)`.

## What This Module Does

Extracts static (possible) column-level and dataset-level lineage from SQL text and schema, producing `StaticEvidence` objects that capture what a query *could* depend on — never claiming anything actually ran.

## Components

### Core Implementation

- **`__init__.py`**: `SQLGlotLineageProvider` class with:
  - `extract(sql, schema, dialect)` → `StaticExtraction`
  - Helper functions: `_column_deps()`, `_alias_map()`, `_has_window()`, `_fingerprint()`, etc.
  - Full support for 19 SQL constructs (see `SUPPORT_MATRIX.md`)
  - Unsupported construct detection (windows, UDFs, outer joins, dynamic SQL, parse errors)
  - Deterministic fingerprinting (SHA-256[:16] of normalized SQL)
  - Alias resolution (table and column aliases correctly mapped to real names)

### Test Corpus

- **`corpus/`** directory with 12 test cases (hand-derived):
  - **Supported**: W03_case_when, W04_aggregate_sum, W05_join_alias, W06_count_star, W07_select_star, W08_where_filter, W09_coalesce
  - **Unsupported**: UNSUPPORTED_window_function, UNSUPPORTED_missing_schema, UNSUPPORTED_outer_join, UNSUPPORTED_parse_error

Each corpus case has:
- SQL query
- Schema definition
- Hand-derived expected dependencies (not from SQLGlot)
- Expected status (SUPPORTED or UNSUPPORTED)
- Diagnostic expectations

### Documentation

- **`SUPPORT_MATRIX.md`**: Complete matrix of supported vs unsupported SQL constructs with rationale

## Supported SQL Constructs (19 total)

**SUPPORTED:**
- Projection (SELECT col FROM ...)
- Column and table aliases
- WHERE filters
- CASE WHEN expressions (condition + branch columns)
- COALESCE, casts, arithmetic
- INNER JOIN with alias resolution
- CTEs (WITH ... SELECT)
- Subqueries
- GROUP BY with aggregates
- Aggregates: SUM, AVG, MIN, MAX, COUNT(col)
- COUNT(*) → dataset-level evidence
- SELECT * with schema expansion
- ORDER BY, DISTINCT, UNION, LIMIT/OFFSET

**UNSUPPORTED (mark with ParserStatus.UNSUPPORTED):**
- Window functions (ROW_NUMBER() OVER, RANK() OVER, etc.)
- User-defined functions (UDFs)
- Dynamic SQL (EXECUTE ... USING)
- LEFT/RIGHT/FULL OUTER JOINs
- Missing or empty schema
- SQL parse errors
- Unresolved aliases

## Usage

### Basic Usage

```python
from ingestion.sql import SQLGlotLineageProvider
from contracts.interfaces import SchemaSnapshot

provider = SQLGlotLineageProvider()

schema = SchemaSnapshot(
    dataset_id="employees",
    columns=("id", "name", "salary", "country"),
    fingerprint="schema-xyz"
)

result = provider.extract(
    sql="SELECT CASE WHEN country='US' THEN salary ELSE 0 END AS adjusted FROM employees",
    schema=schema,
    dialect="postgres"
)

print(result.parser_status)  # SUPPORTED
print(len(result.evidence))  # 2 StaticEvidence objects
```

### Testing

Run M1-specific tests:

```bash
pytest tests/test_static_corpus.py -v
pytest tests/test_static_fingerprints.py -v
pytest tests/test_static_unsupported.py -v
pytest tests/test_static_alias_resolution.py -v
```

## Integration Points

- **M2 (Ground Truth)**: Uses M1's support matrix to decide which SQL categories to benchmark
- **M3 (Storage)**: Stores `StaticEvidence` objects with identity and temporal versions
- **M4 (Reasoning)**: Consumes `parser_status` and `diagnostics` to apply R1 rule (unsupported → UNKNOWN)
- **M5 (API/UI)**: Displays fingerprints and lineage in the UI
- **B1 (Baseline)**: B1 adapter (`research/baselines/b1_adapter.py`) wraps this provider for static-only baseline

## Key Design Decisions

1. **Never store absence**: No `StaticEvidence` is produced for "we found no dependency". Only positive dependencies.
2. **Alias resolution before IDs**: `orders o` is resolved to `orders` before building `source_column_id`.
3. **COUNT(*) is dataset-level**: Produces `Granularity.DATASET`, not column edges.
4. **Deterministic fingerprints**: Same SQL, different whitespace → identical `query_fingerprint`.
5. **Fail fast on unsupported**: Return `ParserStatus.UNSUPPORTED` immediately with diagnostics.

## Pending Decisions

- **D-04** (M4): Should `GROUP BY customer_id` make `customer_id` a dependency for every aggregate output? (Currently: yes)
- **D-11** (M2): How is column-level ground truth derived from ProvSQL if it only gives tuple-level provenance?

## Limitations

- PARTIAL status not currently emitted (all constructs are SUPPORTED or UNSUPPORTED)
- Window function detection relies on AST inspection; some edge cases may slip through
- UDF detection is heuristic-based (checks for Anonymous functions)
- No support for vendor-specific SQL extensions (only core ANSI patterns)

## Dependencies

- **sqlglot >= 30.18.0**: SQL parsing and lineage extraction
- **Python >= 3.11**: Type hints and dataclasses

## Next Steps (MVP-2+)

- `ingestion/dbt/__init__.py`: dbt manifest adapter (deferred until SQL extraction validated)
- Benchmark integration: real SQL corpus from production queries
- Performance optimization: caching parsed ASTs for large queries

