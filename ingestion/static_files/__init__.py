"""Explicit static-file adapter registry following the Kairos envelope.

Format choice is explicit, like a connector recipe: the registry never guesses
that arbitrary JSON is trustworthy metadata and never writes to a database.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ingestion.dbt.manifest import parse_dbt_manifest
from ingestion.dbt.run_results import parse_dbt_run_results
from ingestion.sql.static_file import parse_sql_file
from ingestion.metadata_graph import Diagnostic, MetadataGraphResult, parse_metadata_graph
from ingestion.postgres_query_log import parse_postgres_query_log
from .csv_headers import parse_csv_headers
from .inventory import parse_file_inventory


def parse_static_file(
    kind: str,
    source: bytes | str | Mapping[str, Any],
    *,
    filename: str | None = None,
    source_revision: str | None = None,
) -> MetadataGraphResult:
    """Dispatch an explicitly selected file format to its pure adapter."""
    if kind == "metadata_graph":
        return parse_metadata_graph(
            source,
            filename=filename or "metadata-graph.json",
            source_revision=source_revision,
        )
    if kind == "dbt_manifest":
        return parse_dbt_manifest(
            source,
            filename=filename or "manifest.json",
            source_revision=source_revision,
        )
    if kind == "dbt_run_results":
        return parse_dbt_run_results(
            source,
            filename=filename or "run_results.json",
        )
    if kind == "sql_file":
        return parse_sql_file(source, filename=filename or "query.sql")
    if kind == "postgres_query_log":
        return parse_postgres_query_log(
            source,
            filename=filename or "query_log.json",
        )
    if kind == "file_inventory":
        return parse_file_inventory(
            source,
            filename=filename or "file-inventory.json",
            source_revision=source_revision,
        )
    if kind == "csv_headers":
        return parse_csv_headers(
            source,
            filename=filename or "data.csv",
            source_revision=source_revision,
        )
    return MetadataGraphResult(
        None,
        (Diagnostic("UNSUPPORTED_STATIC_FILE_KIND",
            f"Unsupported static file kind {kind!r}. "
            "Choose metadata_graph, sql_file, dbt_manifest, dbt_run_results, "
            "postgres_query_log, file_inventory, or csv_headers."),),
    )


__all__ = ["parse_static_file"]
