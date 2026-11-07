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


def parse_sql_file(source: bytes | str, *, filename: str = "query.sql", dialect: str = "postgres") -> MetadataGraphResult:
    """Parse DDL/DML target dependencies into the canonical import envelope."""
    try:
        sql = source.decode("utf-8-sig") if isinstance(source, bytes) else source
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
            target = statement.this if isinstance(statement.this, exp.Table) else None
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
