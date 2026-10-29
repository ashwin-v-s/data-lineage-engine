"""Explicit static-file adapter registry following the Kairos envelope.

Format choice is explicit, like a connector recipe: the registry never guesses
that arbitrary JSON is trustworthy metadata and never writes to a database.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ingestion.dbt.manifest import parse_dbt_manifest
from ingestion.metadata_graph import Diagnostic, MetadataGraphResult, parse_metadata_graph
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
        (Diagnostic("UNSUPPORTED_STATIC_FILE_KIND", f"Unsupported static file kind {kind!r}. Choose metadata_graph, dbt_manifest, file_inventory, or csv_headers."),),
    )


__all__ = ["parse_static_file"]
