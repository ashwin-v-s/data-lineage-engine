# M1 Implementation & Viva Guide: Static Metadata Ingestion & SQL Lineage

This document provides a comprehensive explanation of what I (Member 1) have implemented in the Kairos Data Lineage & Metadata Engine repository. It covers the exact location of the code, how it works, and how to confidently explain it in a review or viva.

---

## SECTION 1 — M1 IN ONE MINUTE

**What is M1?**
M1 is the Static Metadata Ingestion & SQL Lineage component of Kairos.

**What problem does M1 solve?**
We need to know the possible dependencies between columns and datasets by statically analyzing SQL queries *before* they are executed. This allows the system to predict lineage relationships.

**Why does Kairos need static lineage?**
Static lineage tells us what *could* happen based on the code. Runtime lineage (M2) tells us what *actually* happened. Kairos needs both to confidently predict and verify data dependencies.

**What does "static lineage" mean?**
It means extracting dependencies by parsing and analyzing SQL source code without actually running it against a database.

**What does SQLGlot do?**
SQLGlot is a pure Python SQL parser and transpiler. M1 uses it to parse SQL into an Abstract Syntax Tree (AST), resolve aliases, and trace column-level lineage from the SELECT targets back to the source tables.

**What does M1 NOT claim?**
M1 NEVER claims that a query actually executed. It only provides *static evidence* that a dependency exists in the code. M1 also does not guarantee that absence of static evidence means absence of execution (e.g. if a query is dynamic or unsupported).

**How does M1 differ from runtime lineage?**
M1 is based purely on the SQL code (what *should* happen). Runtime lineage (M2) is based on actual database logs/events (what *did* happen).

**How does M1 differ from ground truth?**
Ground truth is the absolute, verified reality used for benchmarking. M1 is merely a predictor that generates static evidence, which may be correct, incomplete, or unsupported for certain complex queries.

---

## SECTION 2 — WHAT I HAVE ACTUALLY IMPLEMENTED

| M1 Feature | Status | File(s) | Function/Class | What It Does | Evidence |
| ---------- | ------ | ------- | -------------- | ------------ | -------- |
| **SQLGlot integration** | IMPLEMENTED | `ingestion/sql/__init__.py` | `SQLGlotLineageProvider` | Parses SQL using SQLGlot and extracts lineage. | `extract()` method fully implemented. |
| **SQL parsing & normalization** | IMPLEMENTED | `ingestion/sql/__init__.py` | `_fingerprint` | Generates a deterministic SHA-256 hash of the canonical SQL. | `_fingerprint(sql)` |
| **Schema-snapshot lookup** | IMPLEMENTED | `ingestion/sql/__init__.py` | `extract()` | Converts `SchemaSnapshot` into a format SQLGlot expects to resolve `SELECT *`. | `schema_dict` logic in `extract()` |
| **Dataset-level lineage** | IMPLEMENTED | `ingestion/sql/__init__.py` | `_count_star_targets` | Extracts `COUNT(*)` targets and emits `DATASET` granularity evidence. | Code block checking `tgt_col in count_star_cols` |
| **Column-level lineage** | IMPLEMENTED | `ingestion/sql/__init__.py` | `_column_deps` | Recursively walks SQLGlot AST to find source columns for each target. | `sqlglot.lineage.lineage()` call |
| **Unsupported-SQL detection** | PARTIALLY IMPLEMENTED | `ingestion/sql/__init__.py` | `_has_window`, `_has_udf`, `extract()` | Detects window functions, UDFs, dynamic SQL, and some outer joins. | Rejects with `ParserStatus.UNSUPPORTED`. LEFT/RIGHT join detection is still unreliable (MVP-2). |
| **Static evidence generation** | IMPLEMENTED | `ingestion/sql/__init__.py` | `extract()` | Builds `StaticEvidence` objects with fingerprints and IDs. | `StaticEvidence(...)` constructors |
| **dbt manifest parsing** | PLANNED | `ingestion/dbt/` | N/A | Scaffolded directory; README states it is for MVP-2. | Empty directory with README. |

---

## SECTION 3 — FILE-BY-FILE EXPLANATION

### `ingestion/sql/__init__.py`

#### 1. Why this file exists
This is the core engine for M1. It contains the logic to parse SQL, analyze its structure using SQLGlot, and generate static evidence objects.

#### 2. What is inside it
- `SQLGlotLineageProvider` (The main class)
- `_leaves()` (Helper for AST traversal)
- `_column_deps()` (Wrapper around SQLGlot's lineage tool)
- `_alias_map()` (Helper for resolving `t` to `table_name`)
- `_count_star_targets()` (Detects `COUNT(*)`)
- `_fingerprint()` (Creates normalized SQL hashes)
- `_has_window()`, `_has_udf()` (Checkers for unsupported SQL)

#### 3. What each function does
- `_column_deps()` asks SQLGlot to trace a specific target column back to its root sources.
- `_alias_map()` finds all `FROM table AS alias` clauses and maps `alias -> table`.
- `_count_star_targets()` finds aggregates like `COUNT(*)` because they depend on the whole table, not specific columns.
- `_fingerprint()` converts the SQL to a standard format (canonical form) and hashes it. This means `SELECT A` and `select a` get the same fingerprint.
- `extract()` is the main orchestrator that validates the schema, parses the SQL, checks for unsupported features, extracts dependencies, and builds `StaticEvidence` objects.

#### 4. Input
`extract(sql: str, schema: SchemaSnapshot, dialect: str)`

#### 5. Processing
1. Validate the schema is not empty.
2. Attempt to parse the SQL with SQLGlot.
3. Check for unsupported constructs (Window, UDF, Outer Join, Dynamic SQL).
4. Build an alias map.
5. Identify all SELECT target expressions.
6. Run SQLGlot lineage extraction for each target.
7. Map the aliases back to real table names.

#### 6. Output
Returns a `StaticExtraction` object, which contains a tuple of `StaticEvidence` objects, a `ParserStatus`, and any diagnostic messages.

#### 7. Who uses this output?
The `StaticExtraction` is passed up to the engine components. The `StaticEvidence` objects are eventually stored by M3 (StorageRepository) and consumed by M4 (ReasoningEngine) to predict lineage.

#### 8. Why this design was chosen
We use helper functions to encapsulate SQLGlot's complexity. We separate dataset-level (`COUNT(*)`) and column-level logic because they produce different granularities of evidence. We fingerprint the SQL to deduplicate identical queries that vary only by formatting.

#### 9. How I should explain it in a viva
"This file contains the `SQLGlotLineageProvider`, which takes a raw SQL string and a schema snapshot. It uses SQLGlot to parse the query into an AST. I traverse this tree to resolve aliases, handle `SELECT *` using the schema, and trace column dependencies. Finally, I wrap these dependencies into standardized `StaticEvidence` objects."

---

### `contracts/interfaces.py` & `contracts/evidence.py`

#### 1. Why these files exist
They define the rigid contracts (Protocol seams) between the different members.

#### 2. What is inside it
- `StaticLineageProvider` Protocol (My interface)
- `StaticExtraction` (My output wrapper)
- `StaticEvidence` (The actual dependency record)

#### 3. What each function does
They are dataclasses and protocols; they just define shapes, not logic.

#### 4. Input / Output
`StaticEvidence` takes IDs, fingerprints, granularity, and parser status.

#### 5. How I should explain it in a viva
"My implementation strictly adheres to the `StaticLineageProvider` protocol defined in `contracts/interfaces.py`. I produce `StaticExtraction` and `StaticEvidence` records without knowing how M3 will store them or how M4 will use them."

---

## SECTION 4 — COMPLETE M1 DATA FLOW

**SQL** `SELECT e.name FROM employees e`
↓
**SQLGlot** (parses string into an AST)
↓
**parsing** (Checks for syntax errors)
↓
**normalization** (Creates `schema_dict` from `SchemaSnapshot`)
↓
**schema information** (`schema_dict = {'employees': {'name': 'VARCHAR', 'id': 'VARCHAR'}}`)
↓
**lineage extraction** (Calls `_column_deps('name')`)
↓
**dependency representation** (Finds `e.name` → `employees.name`)
↓
**static evidence** (Creates `StaticEvidence(source_column_id='employees.name', target_column_id='employees.name')`)
↓
**consumer** (Returns `StaticExtraction` containing the evidence)

---

## SECTION 5 — SQLGlot EXPLANATION FOR ME

* **What SQLGlot is:** A pure Python SQL parser and transpiler.
* **Why Kairos uses it:** It's lightweight, supports many dialects, and has built-in AST lineage traversal, meaning we don't have to write a SQL parser from scratch.
* **What SQLGlot receives:** A raw SQL string and a dialect identifier (e.g., "postgres").
* **What SQLGlot produces:** An Abstract Syntax Tree (AST) composed of `exp.Expression` nodes.
* **How aliases are handled:** **IMPLEMENTED**. `_alias_map` finds all `exp.Table` nodes and creates a dictionary mapping `t.alias_or_name` to `t.name`.
* **How tables are handled:** **IMPLEMENTED**. Tables are matched to the `SchemaSnapshot`.
* **How columns are handled:** **IMPLEMENTED**. Target columns are extracted from `exp.Select` expressions, and source columns are found via `sqlglot.lineage`.
* **How expressions are handled:** **IMPLEMENTED**. Expressions are hashed into `expression_fingerprint`.
* **How CTEs are handled:** **IMPLEMENTED**. Handled automatically by SQLGlot's built-in lineage generator.
* **How joins are handled:** **PARTIAL**. INNER JOINs work. LEFT/RIGHT/FULL OUTER JOINs are explicitly rejected because they complicate lineage (they can produce NULLs, which MVP-1 doesn't handle well).
* **How WHERE is handled:** **IMPLEMENTED**. SQLGlot automatically traces dependencies through WHERE clauses if they affect the output.
* **How CASE is handled:** **IMPLEMENTED**. SQLGlot traces both the condition and the branches.
* **How aggregates are handled:** **IMPLEMENTED**. Normal aggregates like `SUM(amount)` trace to `amount`.
* **How SELECT * is handled:** **IMPLEMENTED**. It uses the provided `SchemaSnapshot` to expand `exp.Star` into explicit column names.
* **What happens when SQL cannot be supported:** **IMPLEMENTED**. The provider catches exceptions or detects unsupported nodes (like `exp.Window`) and returns a `ParserStatus.UNSUPPORTED` with zero evidence.

---

## SECTION 6 — STATIC LINEAGE VS RUNTIME LINEAGE

| Question | M1 Static Lineage | M2 Runtime Evidence |
| --- | --- | --- |
| **What does it tell us?** | What *could* happen based on the source code. | What *actually* happened in the database. |
| **When is it generated?** | At code analysis / ingestion time. | During or after query execution (log parsing). |
| **Source** | SQL source code files. | Database audit logs / query history. |
| **Can it prove execution?** | **NO.** | **YES.** |
| **Example** | `SELECT a FROM table` means `a` *might* be read. | Log shows User X ran `SELECT a FROM table` at 10:00 AM. |
| **Owner** | M1 | M2 |

**Viva Answer for "Does SQLGlot prove that a column actually contributed to the output?"**
"No, SQLGlot cannot prove execution. It only proves that the dependency exists in the source code definition. A query might never be executed, or it might be skipped due to runtime conditions. That is why M1 only generates *static evidence*, which must be corroborated by M2's runtime evidence."

---

## SECTION 7 — DATASET-LEVEL VS COLUMN-LEVEL LINEAGE

**Dataset lineage (`dataset A → dataset B`)**:
Indicates that a target dataset depends on a source dataset, without specifying exactly which columns.
*M1 Support:* **IMPLEMENTED**. Specifically used for `COUNT(*)`, which depends on the existence of rows in a table rather than the values of specific columns.

**Column lineage (`A.column_x → B.column_y`)**:
Indicates that a specific target column is computed using a specific source column.
*M1 Support:* **IMPLEMENTED**. Generated for explicit column selections and scalar transformations.

---

## SECTION 8 — SCHEMA SNAPSHOT

**Why schema information is needed:**
You cannot resolve `SELECT *` without knowing what columns actually exist in the table. You also need it to know which columns belong to which tables when joins are involved without explicit aliases.

**Where it comes from:**
It is passed as a `SchemaSnapshot` dataclass into the `extract()` method.

**How it affects lineage:**
M1 converts the `SchemaSnapshot` into a dictionary format that SQLGlot can use during lineage extraction to resolve ambiguities.

**Viva Answer for "Why can't you always resolve SELECT * without schema information?"**
"Because `SELECT *` is essentially a wildcard. The SQL parser alone has no idea what columns exist in the underlying database table. I need the `SchemaSnapshot` to expand that wildcard into the actual column names so I can generate precise column-level static evidence."

---

## SECTION 9 — NORMALIZATION AND FINGERPRINTING

**SQL Normalization:** **IMPLEMENTED**. SQLGlot transpiles the AST back into a canonical SQL string.
**Query Fingerprint:** **IMPLEMENTED**. `_fingerprint()` generates a SHA-256 hash (truncated to 16 chars) of the canonical SQL.
**Schema Fingerprint:** **IMPLEMENTED**. Simply passed through from the `SchemaSnapshot`.
**Expression Fingerprint:** **IMPLEMENTED**. Generated using an MD5 hash of the source column name (or a special "expr-count-star" string).

**Why fingerprints are useful:** They allow the system to quickly determine if a query has logically changed. If the formatting changes but the fingerprint remains the same, we don't need to recompute the lineage.

---

## SECTION 10 — UNSUPPORTED SQL

M1 explicitly catches constructs that are too complex for MVP-1 and prevents the system from making false lineage claims.

| SQL Construct | Current Status | Reason / Handling |
| --- | --- | --- |
| **Window Functions** | UNSUPPORTED | Detected via `_has_window()`. Complex state tracking not supported yet. |
| **UDFs** | UNSUPPORTED | Detected via `_has_udf()`. SQLGlot cannot see inside anonymous functions. |
| **Dynamic SQL** | UNSUPPORTED | Text search for `EXECUTE` / `USING`. Cannot statically determine targets. |
| **FULL OUTER JOIN** | UNSUPPORTED | Checked in AST. Complicates nullable dependency logic. |
| **LEFT/RIGHT JOIN** | PARTIAL (Fails tests) | Intended to be unsupported, but AST detection is currently unreliable. |
| **Missing Schema** | UNSUPPORTED | Rejected immediately. Cannot resolve `SELECT *`. |
| **Parse Errors** | UNSUPPORTED | SQLGlot throws exception; caught and wrapped in diagnostic. |

If a query is unsupported, M1 returns `ParserStatus.UNSUPPORTED` and an empty evidence list. This prevents silent failures or false positives.

---

## SECTION 11 — STATIC EVIDENCE

`StaticEvidence` is the core output of M1.

*   **evidence_id**: `static:<query_fp>:<src_id>-><tgt_id>`
*   **source_dataset_id**: From schema.
*   **target_dataset_id**: From schema.
*   **source_column_id**: Resolved real column name.
*   **target_column_id**: Target alias or column.
*   **granularity**: `COLUMN` or `DATASET`.
*   **parser_status**: `SUPPORTED`, `UNSUPPORTED`, or `PARTIAL`.
*   **diagnostics**: Text strings explaining why something failed.
*   **timestamps / coverage**: *ARCHITECTURALLY REQUIRED BUT NOT IMPLEMENTED IN STATIC EVIDENCE* (Timestamps and coverage belong strictly to *RuntimeEvidence*).

---

## SECTION 12 — DBT

**Status: PLANNED (SCAFFOLDED)**

The directory `ingestion/dbt/` exists, but only contains an `__init__.py` and a `README.md`. The README explicitly states: *"dbt manifest adapter (MVP-2). Start after SQL extraction works. Pack Section 30."*

I have not implemented dbt parsing yet. It is my immediate next step for MVP-2.

---

## SECTION 13 — TESTS

| Test | What It Proves | Status |
| --- | --- | --- |
| `test_static_alias_resolution.py` | Proves that `e.name` resolves to `employees.name`. | Passes |
| `test_static_unsupported.py` | Proves that Window, Full Join, and Dynamic SQL are rejected. | Passes (Left/Right skip) |
| `test_static_corpus.py` | Validates against hand-derived JSON fixtures (`W03`, `W04`, `W07`). | Passes |
| `test_static_fingerprints.py` | (Implicitly tested by the corpus tests asserting on output shapes) | Exists |

### "Tests I can mention in the review"
1. **The Alias Resolution Test:** "I wrote tests to prove that when a user writes `SELECT e.name FROM employees e`, my code correctly traces the dependency back to `employees.name`, not the temporary alias `e`."
2. **The Unsupported Construct Test:** "I wrote tests proving that if a user submits a query with a Window function, M1 safely rejects it with a diagnostic message instead of generating corrupted evidence."
3. **The Corpus Tests:** "I validate my engine against hand-derived JSON JSON corpus cases to ensure `SELECT *` properly expands into explicit columns using the schema snapshot."

---

## SECTION 14 — ACTUAL IMPLEMENTATION VS ARCHITECTURE

| Architecture says M1 should do | What repository currently does |
| --- | --- |
| SQL Parsing via SQLGlot | **IMPLEMENTED** |
| Alias resolution | **IMPLEMENTED** |
| Handling `SELECT *` | **IMPLEMENTED** (using `SchemaSnapshot`) |
| Detecting unsupported SQL | **IMPLEMENTED** (Window, UDF, Dynamic) |
| Detecting LEFT/RIGHT JOINs | **PARTIALLY DONE** (Tests skipped due to unreliability) |
| dbt manifest parsing | **NOT YET STARTED** (Scaffolded only) |

### Already Done
SQLGlot parsing, AST traversal, alias mapping, schema injection, fingerprinting, unsupported rejection, static evidence generation.

### Partially Done
Accurate detection of `LEFT OUTER JOIN` and `RIGHT OUTER JOIN`.

### Not Yet Started
dbt manifest (`manifest.json`) ingestion and parsing.

---

## SECTION 15 — HOW M1 CONNECTS TO OTHER MEMBERS

### M1 → M2
M2 (Runtime) operates entirely independently of M1. M2 reads logs; I read SQL. We do not pass data to each other.

### M1 → M3
My output (`StaticExtraction` containing `StaticEvidence`) is passed into the system and stored by M3 (StorageRepository) via `put_evidence()`.

### M1 → M4
M4 (ReasoningEngine) will eventually query M3 to retrieve my `StaticEvidence` alongside M2's `RuntimeEvidence` to predict the final lineage graph.

### M1 → M5
M5 (API) serves the final graph to the user. M5 never talks to me directly.

**What M1 must NEVER do:**
* M1 must not claim execution occurred.
* M1 must not turn missing runtime evidence into a negative dependency.
* M1 must not silently support unsupported SQL (it must raise `UNSUPPORTED`).

---

## SECTION 16 — ONE COMPLETE EXAMPLE

**1. SQL input:**
`SELECT e.name, e.salary FROM employees e`

**2. Parser & Schema Lookup:**
I receive the SQL and a `SchemaSnapshot` containing `dataset_id: employees`, `columns: [id, name, salary]`. I use SQLGlot to parse the string into an AST.

**3. Normalization:**
I build a `schema_dict` so SQLGlot knows what columns belong to what tables.

**4. Dependency discovery:**
I call `_alias_map`, which tells me `e` = `employees`. I call `_column_deps` on targets `name` and `salary`. SQLGlot traces them to `e.name` and `e.salary`.

**5. Lineage Result:**
I resolve `e.name` to `employees.name`.

**6. Evidence representation:**
I create two `StaticEvidence` objects:
1: `source: employees.name -> target: employees.name`
2: `source: employees.salary -> target: employees.salary`

**7. Downstream:**
I return these in a `StaticExtraction` to be saved by M3.

---

## SECTION 17 — WHAT I SHOULD SAY IN THE REVIEW

1. **"What is your role?"**
   "I am Member 1. I am responsible for Static Metadata Ingestion and SQL Lineage. I built the engine that statically analyzes SQL code to discover theoretical dependencies."
2. **"What exactly have you implemented?"**
   "I implemented the `SQLGlotLineageProvider`, which parses SQL, resolves table aliases, handles `SELECT *` expansion using schema snapshots, detects unsupported constructs, and generates standardized `StaticEvidence` records."
3. **"Why did you use SQLGlot?"**
   "Because it's a robust, pure-Python parser with built-in AST lineage traversal. It saves us from writing a custom SQL grammar."
4. **"What happens for unsupported SQL?"**
   "My code actively scans the AST for constructs we don't support in MVP-1, like Window functions or Dynamic SQL. If found, it safely rejects the query by returning a `ParserStatus.UNSUPPORTED` flag with diagnostic messages, ensuring we don't generate false lineage."
5. **"What have you NOT implemented yet?"**
   "I have not implemented dbt manifest parsing yet. The directory is scaffolded, but it is slated for MVP-2."

---

## SECTION 18 — POSSIBLE CROSS-QUESTIONS

**Question:** "Show me where SQLGlot is used."
**Short answer:** "In `ingestion/sql/__init__.py`."
**Detailed answer:** "I import `sqlglot` at the top of the file, use `sqlglot.parse_one()` to create the AST, and `sqlglot.lineage.lineage()` to trace column dependencies."

**Question:** "How do you handle SELECT *?"
**Short answer:** "By injecting the `SchemaSnapshot`."
**Detailed answer:** "When I detect an `exp.Star` node in the AST, I look at the `SchemaSnapshot` passed into my `extract()` function and expand the star into explicit target column names."

**Question:** "Can SQLGlot prove actual execution?"
**Short answer:** "No."
**Detailed answer:** "Static analysis only proves that the code *contains* the dependency. M2's runtime evidence is required to prove actual execution."

---

## SECTION 19 — CODE WALKTHROUGH CHEAT SHEET

*   **Main Entry Point** → `ingestion/sql/__init__.py` → `SQLGlotLineageProvider` → `extract()`
*   **Alias Resolution** → `_alias_map(sql)`
*   **Column Tracing** → `_column_deps(sql, schema_dict, target_cols)`
*   **Unsupported Detection** → `_has_window(sql)`, `_has_udf(sql)`
*   **Hashing/Fingerprints** → `_fingerprint(sql)`
*   **Input** → `sql` (string), `schema` (`SchemaSnapshot`)
*   **Output** → `StaticExtraction` (contains `StaticEvidence`)

---

## SECTION 20 — M1 ONE-PAGE CHEAT SHEET

### My Role
Static Metadata Ingestion & SQL Lineage.

### What I Built
A static SQL analyzer that parses queries, traces column dependencies, and handles schema integration to produce `StaticEvidence`.

### Main Files
*   `ingestion/sql/__init__.py` (Core logic)
*   `tests/test_static_*.py` (Validation)

### Main Technologies
Python, SQLGlot.

### Current Limitations
Window functions, UDFs, dynamic SQL, and some Outer Joins are safely rejected as unsupported.

### Next Implementation
dbt `manifest.json` parsing (MVP-2).

### M1 → Downstream
I output `StaticEvidence`. M3 stores it. M4 reasons over it.

### 60-second explanation
"I built the static lineage engine for Kairos. When a SQL query enters the system, my code uses SQLGlot to parse it into an Abstract Syntax Tree. I resolve table aliases and use schema snapshots to expand wildcard selects. I then trace every output column back to its source, creating `StaticEvidence` records. I also built strict safety checks: if a query uses complex unsupported features like Window functions, I catch it in the AST and reject it with detailed diagnostics. My output tells the rest of the system what dependencies *should* exist according to the source code."

---

## Claims I MUST NOT Make

*   **DO NOT claim that I have implemented dbt parsing.** It is only a scaffolded directory right now.
*   **DO NOT claim that LEFT/RIGHT outer join detection is working perfectly.** The tests for it are explicitly skipped, noting it as unreliable in MVP-1.
*   **DO NOT claim that M1 generates timestamps or coverage metrics.** That belongs exclusively to M2 (Runtime Evidence).
*   **DO NOT claim that M1 proves a query was executed.** Static evidence only proves the code *exists*.

---

## My M1 Implementation Roadmap

### Already implemented
SQLGlot parsing, column dependency tracing, `SELECT *` expansion, alias resolution, and basic unsupported construct detection (Window, UDF).

### Immediate next step
**Fix LEFT/RIGHT OUTER JOIN detection.**
*   *File:* `ingestion/sql/__init__.py`
*   *Why:* To ensure we safely reject outer joins without false positives.
*   *Test:* Un-skip and pass `test_outer_join_left_detected` in `test_static_unsupported.py`.

### After that
**Implement dbt manifest parsing (MVP-2).**
*   *File:* `ingestion/dbt/__init__.py`
*   *What:* Parse `manifest.json` to extract models, sources, and dependencies.
*   *Output:* `StaticEvidence` records derived from dbt metadata instead of raw SQL.

### Final M1 handoff
Ensure `StaticExtraction` integrates seamlessly with M3's `StorageRepository.put_evidence()` pipeline.
