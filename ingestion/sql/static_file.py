"""SQLGlot adapter for user-selected SQL files.

This adapter records only static declarations. A parsed dependency is a lineage
candidate and is never evidence that the statement executed.
"""
from __future__ import annotations

import hashlib
from typing import Any

import sqlglot
from sqlglot import exp

from ingestion.metadata_graph import Diagnostic, MetadataGraphResult, parse_metadata_graph


def _table_name(table: exp.Table) -> str:
    return ".".join(part.name for part in table.parts if part.name)


def _add_column(asset: dict[str, Any], column_name: str) -> None:
    """Record a column discovered in a SQL projection on the asset."""
    name = str(column_name or "").strip()
    if not name or not name.replace("_", "").isalnum():
        return
    metadata = asset.setdefault("metadata", {})
    columns = metadata.setdefault("columns", [])
    if any(item.get("name") == name for item in columns if isinstance(item, dict)):
        return
    columns.append({"name": name, "data_type": None})


def _target_columns(statement: exp.Expression, query: exp.Expression) -> list[str]:
    """Return the target column names a statement writes, in projection order."""
    select = query.find(exp.Select)
    if select is None:
        return []
    if isinstance(statement, exp.Insert) and isinstance(statement.this, exp.Schema):
        declared = [expr.name for expr in statement.this.expressions if getattr(expr, "name", "")]
        if declared:
            return declared
    columns: list[str] = []
    for expression in select.expressions:
        if isinstance(expression, exp.Star):
            return []
        columns.append(expression.alias_or_name)
    return columns


def _column_mappings(
    statement: exp.Expression,
    query: exp.Expression,
    target_name: str,
    target_id: str,
) -> list[tuple[str, str, str, str]]:
    """Return ``(source_id, source_column, target_column, source_table)`` rows.

    This is a static projection analysis: a SELECT expression's source columns
    are mapped to the column the statement writes.  It deliberately skips
    ``SELECT *`` and unresolved aliases rather than inventing a mapping.
    """
    select = query.find(exp.Select)
    target_columns = _target_columns(statement, query)
    if select is None or not target_columns:
        return []
    alias_to_table: dict[str, str] = {}
    for source_table in query.find_all(exp.Table):
        name = _table_name(source_table)
        if not name or name.casefold() == target_name.casefold():
            continue
        alias_to_table[source_table.alias_or_name] = name
        alias_to_table.setdefault(source_table.name, name)

    mappings: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, expression in enumerate(select.expressions):
        if isinstance(expression, exp.Star):
            continue
        target_column = target_columns[index] if index < len(target_columns) else expression.alias_or_name
        if not target_column:
            continue
        for column in expression.find_all(exp.Column):
            source_table = alias_to_table.get(column.table or "")
            if not source_table or not column.name:
                continue
            if source_table.casefold() == target_name.casefold():
                continue
            key = (source_table.lower(), column.name.lower(), target_column.lower())
            if key in seen:
                continue
            seen.add(key)
            mappings.append(("sql-table:" + source_table.lower(), column.name, target_column, source_table))
    return mappings


def parse_sql_file(source: bytes | str, *, filename: str = "query.sql", dialect: str = "postgres") -> MetadataGraphResult:
    """Parse DDL/DML target dependencies into the canonical import envelope."""
    try:
        if isinstance(source, bytes):
            sql = source.decode("utf-8-sig")
        elif isinstance(source, str):
            sql = source
        else:
            return MetadataGraphResult(
                None,
                (Diagnostic("SQL_PARSE_ERROR", f"SQL file content must be text; received {type(source).__name__}.", filename),),
            )
        statements = [statement for statement in sqlglot.parse(sql, read=dialect) if statement is not None]
    except (UnicodeDecodeError, sqlglot.errors.ParseError, ValueError) as exc:
        return MetadataGraphResult(None, (Diagnostic("SQL_PARSE_ERROR", f"SQLGlot could not parse this file: {exc}", filename),))

    file_name = filename.replace("\\", "/").rsplit("/", 1)[-1] or "query.sql"
    file_id = "sql-file:" + hashlib.sha256(file_name.encode("utf-8")).hexdigest()
    assets: dict[str, dict[str, Any]] = {
        file_id: {
            "id": file_id,
            "qualified_name": f"sql-file/{file_name}",
            "namespace": "sql-file",
            "name": file_name,
            "type": "file",
            "metadata": {
                "format": "sql", "parser": "sqlglot", "parser_version": sqlglot.__version__,
                "dialect": dialect, "statement_count": len(statements), "original_sql": sql,
            },
        }
    }
    relationships: list[dict[str, str]] = []
    for index, statement in enumerate(statements):
        target: exp.Table | None = None
        query: exp.Expression | None = None
        if isinstance(statement, exp.Create) and isinstance(statement.this, exp.Table):
            target = statement.this
            query = statement.expression
        elif isinstance(statement, exp.Insert):
            if isinstance(statement.this, exp.Table):
                target = statement.this
            elif isinstance(statement.this, exp.Schema) and isinstance(statement.this.this, exp.Table):
                target = statement.this.this
            else:
                target = None
            query = statement.expression

        if target is None or query is None:
            continue
        target_name = _table_name(target)
        if not target_name:
            continue
        target_id = "sql-table:" + target_name.lower()
        assets.setdefault(target_id, {
            "id": target_id, "qualified_name": target_name, "namespace": target.db or target.catalog or "sql",
            "name": target.name, "type": "table", "metadata": {"declared_by_sql_file": file_name},
        })
        for source_table in sorted(query.find_all(exp.Table), key=_table_name):
            source_name = _table_name(source_table)
            if not source_name or source_name.casefold() == target_name.casefold():
                continue
            source_id = "sql-table:" + source_name.lower()
            assets.setdefault(source_id, {
                "id": source_id, "qualified_name": source_name, "namespace": source_table.db or source_table.catalog or "sql",
                "name": source_table.name, "type": "table", "metadata": {"referenced_by_sql_file": file_name},
            })
            relationships.append({"source_id": source_id, "target_id": target_id, "edge_type": "sql_static_candidate"})

        # Expand the SELECT projection into column-level candidates.  The
        # target columns are recorded on both assets so the commit path can
        # create column_record rows without a live schema snapshot.
        for source_id, source_column, target_column, source_table in _column_mappings(
            statement, query, target_name, target_id
        ):
            _add_column(assets[target_id], target_column)
            _add_column(assets[source_id], source_column)
            relationships.append({
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": "sql_column_candidate",
                "source_column": source_column,
                "target_column": target_column,
                "provenance": f"SQLGlot static SELECT projection in {file_name}",
            })

    graph = {
        "contract_version": "kairos.ingest.v1",
        "source": {"kind": "sql_file", "ref": file_name},
        "assets": list(assets.values()),
        "relationships": relationships,
    }
    result = parse_metadata_graph(graph, filename=file_name)
    if result.ok and result.payload is not None:
        result.payload["provenance"]["adapter"] = "kairos.sqlglot_file"
        result.payload["provenance"]["adapter_version"] = sqlglot.__version__
    return result
