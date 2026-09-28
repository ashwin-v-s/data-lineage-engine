"""
M1: Static lineage extraction via SQLGlot.

Implements StaticLineageProvider.extract(sql, schema, dialect) -> StaticExtraction.
Produces StaticEvidence objects for column-level and dataset-level dependencies.
Never claims anything actually ran. Never stores absence as evidence.
"""

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Set, Tuple

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage

from contracts.evidence import StaticEvidence
from contracts.interfaces import SchemaSnapshot, StaticExtraction, StaticLineageProvider
from contracts.types import Granularity, ParserStatus


def _leaves(node) -> list:
    """Recursively collect leaf column names from a lineage tree."""
    if not node.downstream:
        return [node.name]
    return [leaf for child in node.downstream for leaf in _leaves(child)]


def _column_deps(
    sql: str, schema: Dict[str, Dict[str, str]], targets: Sequence[str], dialect: str = "postgres"
) -> Dict[str, Sequence[str]]:
    """For each target column, return sorted list of source columns it depends on."""
    out = {}
    for t in targets:
        try:
            node = lineage(t, sql, schema=schema, dialect=dialect)
            out[t] = sorted(set(_leaves(node)))
        except Exception as e:
            # Lineage extraction failed for this target; record as empty
            out[t] = []
    return out


def _alias_map(sql: str, dialect: str = "postgres") -> Dict[str, str]:
    """Build a map from table alias (or table name if no alias) to real table name."""
    tree = sqlglot.parse_one(sql, dialect=dialect)
    return {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}


def _has_window(sql: str, dialect: str = "postgres") -> bool:
    """Check if SQL contains a window function."""
    try:
        return sqlglot.parse_one(sql, dialect=dialect).find(exp.Window) is not None
    except Exception:
        return False


def _count_star_targets(sql: str, dialect: str = "postgres") -> Sequence[str]:
    """Return list of column aliases that have COUNT(*) applied to them."""
    try:
        tree = sqlglot.parse_one(sql, dialect=dialect)
        return [
            c.parent.alias
            for c in tree.find_all(exp.Count)
            if isinstance(c.this, exp.Star) and c.parent is not None
        ]
    except Exception:
        return []


def _has_udf(sql: str, dialect: str = "postgres") -> bool:
    """Check if SQL contains unknown user-defined functions."""
    try:
        tree = sqlglot.parse_one(sql, dialect=dialect)
        for func in tree.find_all(exp.Func):
            # SQLGlot has a list of known functions; anything else is suspicious
            if not hasattr(func, '__class__') or func.__class__.__name__ == "Anonymous":
                return True
        return False
    except Exception:
        return False


def _fingerprint(sql: str, dialect: str = "postgres") -> str:
    """SHA-256[:16] of the normalized (canonical form) SQL. Deterministic across whitespace variations."""
    try:
        canonical = sqlglot.parse_one(sql, dialect=dialect).sql(dialect=dialect)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
    except Exception:
        # Parse failed; use a hash of the original
        return hashlib.sha256(sql.encode()).hexdigest()[:16]


class SQLGlotLineageProvider:
    """M1: Static lineage extraction using SQLGlot.

    Implements StaticLineageProvider.extract(sql, schema, dialect) -> StaticExtraction.
    """

    def extract(
        self, sql: str, schema: SchemaSnapshot, dialect: str = "postgres"
    ) -> StaticExtraction:
        """Extract static lineage from SQL text and schema.

        Args:
            sql: SQL query text.
            schema: SchemaSnapshot with dataset_id, columns, fingerprint.
            dialect: SQLGlot dialect ("postgres", "bigquery", etc.).

        Returns:
            StaticExtraction with static_evidence, parser_status, and diagnostics.
        """
        diagnostics: list = []
        static_evidence: list = []

        # Step 1: Validate schema
        if not schema or not schema.columns:
            diagnostics.append("Empty or missing schema")
            return StaticExtraction(
                evidence=tuple(),
                parser_status=ParserStatus.UNSUPPORTED,
                diagnostics=tuple(diagnostics),
            )

        # Step 2: Try to parse SQL
        try:
            tree = sqlglot.parse_one(sql, dialect=dialect)
        except Exception as e:
            diagnostics.append(f"SQL parse error: {str(e)}")
            return StaticExtraction(
                evidence=tuple(),
                parser_status=ParserStatus.UNSUPPORTED,
                diagnostics=tuple(diagnostics),
            )

        # Step 3: Check for unsupported constructs
        if _has_window(sql, dialect):
            diagnostics.append("Window function not supported in MVP")
            return StaticExtraction(
                evidence=tuple(),
                parser_status=ParserStatus.UNSUPPORTED,
                diagnostics=tuple(diagnostics),
            )

        if _has_udf(sql, dialect):
            diagnostics.append("User-defined function not supported")
            return StaticExtraction(
                evidence=tuple(),
                parser_status=ParserStatus.UNSUPPORTED,
                diagnostics=tuple(diagnostics),
            )

        # Check for LEFT/RIGHT/FULL OUTER JOINs (not supported in MVP)
        for join in tree.find_all(exp.Join):
            join_type = join.kind
            if join_type and any(x in str(join_type).upper() for x in ["LEFT", "RIGHT", "FULL", "OUTER"]):
                diagnostics.append(f"Outer join ({join_type}) not supported in MVP")
                return StaticExtraction(
                    evidence=tuple(),
                    parser_status=ParserStatus.UNSUPPORTED,
                    diagnostics=tuple(diagnostics),
                )

        # Check for dynamic SQL patterns
        if "EXECUTE" in sql.upper() or "USING" in sql.upper():
            diagnostics.append("Dynamic SQL not supported")
            return StaticExtraction(
                evidence=tuple(),
                parser_status=ParserStatus.UNSUPPORTED,
                diagnostics=tuple(diagnostics),
            )

        # Step 4: Resolve aliases
        aliases = _alias_map(sql, dialect)

        # Step 5: Extract SELECT targets
        select = tree.find(exp.Select)
        if not select:
            diagnostics.append("No SELECT clause found")
            return StaticExtraction(
                evidence=tuple(),
                parser_status=ParserStatus.UNSUPPORTED,
                diagnostics=tuple(diagnostics),
            )

        # Build schema dict for lineage extraction
        # Convert SchemaSnapshot to format SQLGlot expects: {table_name: {col_name: type}}
        schema_dict = {}
        for col in schema.columns:
            # Assume simple column names; full qualified names are dataset.column
            if "." in col:
                parts = col.split(".", 1)
                table, colname = parts
            else:
                table = schema.dataset_id.split(".")[-1]  # Use the last part as table name
                colname = col

            if table not in schema_dict:
                schema_dict[table] = {}
            schema_dict[table][colname] = "VARCHAR"  # Type unknown, assume VARCHAR

        # Get all select expressions
        select_cols = select.expressions
        count_star_cols = _count_star_targets(sql, dialect)

        # Extract target column names
        target_cols = []
        for expr in select_cols:
            if isinstance(expr, exp.Star):
                # SELECT * — need schema to expand
                # For now, expand using schema columns
                if schema.columns:
                    target_cols.extend([c.split(".")[-1] for c in schema.columns])
            else:
                # Named expression
                target_cols.append(expr.alias_or_name)

        # Step 6: Extract column dependencies via lineage
        try:
            col_deps = _column_deps(sql, schema_dict, target_cols, dialect)
        except Exception as e:
            diagnostics.append(f"Lineage extraction failed: {str(e)}")
            col_deps = {}

        # Step 7: Build StaticEvidence objects
        query_fp = _fingerprint(sql, dialect)
        schema_fp = schema.fingerprint

        # Track which target columns we've already processed (for dedup)
        processed_pairs: Set[Tuple[str, str]] = set()

        for tgt_col in target_cols:
            # Check if this is a COUNT(*) — emit dataset-level evidence only
            if tgt_col in count_star_cols:
                evidence_id = f"static:{query_fp}:dataset->{schema.dataset_id}"
                if evidence_id not in processed_pairs:
                    evidence = StaticEvidence(
                        evidence_id=evidence_id,
                        source_dataset_id=schema.dataset_id,
                        target_dataset_id=schema.dataset_id,
                        source_column_id=None,
                        target_column_id=None,
                        granularity=Granularity.DATASET,
                        operator="COUNT(*)",
                        expression_fingerprint=f"expr-count-star",
                        query_fingerprint=query_fp,
                        schema_fingerprint=schema_fp,
                        parser_status=ParserStatus.SUPPORTED,
                        unsupported_constructs=(),
                        diagnostics=(),
                    )
                    static_evidence.append(evidence)
                    processed_pairs.add((schema.dataset_id, schema.dataset_id))
            else:
                # Column-level dependencies
                src_cols = col_deps.get(tgt_col, [])
                for src_col in src_cols:
                    # Resolve alias in source column
                    if "." in src_col:
                        table_alias, col_name = src_col.split(".", 1)
                        real_table = aliases.get(table_alias, table_alias)
                        resolved_src = f"{real_table}.{col_name}"
                    else:
                        resolved_src = src_col

                    # Build IDs
                    src_id = f"{schema.dataset_id}.{resolved_src}" if "." not in resolved_src else resolved_src
                    tgt_id = f"{schema.dataset_id}.{tgt_col}"

                    evidence_id = f"static:{query_fp}:{src_id}->{tgt_id}"
                    pair_key = (src_id, tgt_id)

                    if pair_key not in processed_pairs:
                        evidence = StaticEvidence(
                            evidence_id=evidence_id,
                            source_dataset_id=schema.dataset_id,
                            target_dataset_id=schema.dataset_id,
                            source_column_id=src_id,
                            target_column_id=tgt_id,
                            granularity=Granularity.COLUMN,
                            operator="project",
                            expression_fingerprint=f"expr-{hashlib.md5(src_col.encode()).hexdigest()[:8]}",
                            query_fingerprint=query_fp,
                            schema_fingerprint=schema_fp,
                            parser_status=ParserStatus.SUPPORTED,
                            unsupported_constructs=(),
                            diagnostics=(),
                        )
                        static_evidence.append(evidence)
                        processed_pairs.add(pair_key)

        # Step 8: Determine overall parser status
        parser_status = ParserStatus.SUPPORTED if not diagnostics else ParserStatus.PARTIAL

        return StaticExtraction(
            evidence=tuple(static_evidence),
            parser_status=parser_status,
            diagnostics=tuple(diagnostics),
        )


# Export the provider for use by other modules
__all__ = ["SQLGlotLineageProvider", "extract"]


def extract(sql: str, schema: SchemaSnapshot, dialect: str = "postgres") -> StaticExtraction:
    """Convenience function: extract static lineage from SQL."""
    provider = SQLGlotLineageProvider()
    return provider.extract(sql, schema, dialect)
