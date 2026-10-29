"""Header-only CSV schema adapter; data rows are never imported or inferred."""
from __future__ import annotations

import csv
import hashlib
import io
import re

from ingestion.metadata_graph import MAX_FILE_BYTES, Diagnostic, MetadataGraphResult, _safe_filename, parse_metadata_graph

ADAPTER_VERSION = "1.0.0"
MAX_COLUMNS = 1_000
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def parse_csv_headers(
    source: bytes | str,
    *,
    filename: str = "data.csv",
    source_revision: str | None = None,
) -> MetadataGraphResult:
    """Read only the header row and emit one table asset with unknown column types."""
    if isinstance(source, bytes):
        raw = source
        if len(raw) > MAX_FILE_BYTES:
            return MetadataGraphResult(None, (Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit."),))
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            return MetadataGraphResult(None, (Diagnostic("INVALID_CSV_ENCODING", f"CSV must be UTF-8 encoded: {exc}"),))
    elif isinstance(source, str):
        text = source
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            return MetadataGraphResult(None, (Diagnostic("INVALID_CSV_ENCODING", f"CSV must be UTF-8 encoded: {exc}"),))
        if len(raw) > MAX_FILE_BYTES:
            return MetadataGraphResult(None, (Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit."),))
    else:
        return MetadataGraphResult(None, (Diagnostic("INVALID_CSV_INPUT", "CSV input must be bytes or text."),))
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = next(reader, None)
    except (csv.Error, StopIteration) as exc:
        return MetadataGraphResult(None, (Diagnostic("INVALID_CSV", f"Could not read CSV header: {exc}"),))
    if not headers:
        return MetadataGraphResult(None, (Diagnostic("CSV_HEADER_REQUIRED", "CSV must have a non-empty header row."),))
    if len(headers) > MAX_COLUMNS:
        return MetadataGraphResult(None, (Diagnostic("CSV_COLUMN_LIMIT", f"At most {MAX_COLUMNS:,} columns are accepted."),))

    columns: list[dict[str, str | int | None]] = []
    seen: set[str] = set()
    for index, header in enumerate(headers):
        name = header.strip()
        if not name or len(name) > 256 or _CONTROL.search(name):
            return MetadataGraphResult(None, (Diagnostic("INVALID_CSV_HEADER", "Column names must be non-empty, printable strings of at most 256 characters.", f"header[{index}]"),))
        if name.casefold() in seen:
            return MetadataGraphResult(None, (Diagnostic("DUPLICATE_CSV_HEADER", f"Column {name!r} appears more than once.", f"header[{index}]"),))
        seen.add(name.casefold())
        columns.append({"name": name, "data_type": None, "position": index + 1})

    safe_name = _safe_filename(filename)
    stem = safe_name.rsplit(".", 1)[0] if "." in safe_name else safe_name
    stem = stem[:200] or "data"
    asset = {
        "id": "csv:" + hashlib.sha256(safe_name.encode("utf-8")).hexdigest(),
        "qualified_name": f"csv/{stem}",
        "name": stem,
        "namespace": "csv-upload",
        "type": "table",
        "kind": "source",
        "metadata": {"filename": safe_name, "columns": columns, "column_count": len(columns), "schema_source": "csv_header_only"},
    }
    result = parse_metadata_graph({
        "contract_version": "kairos.ingest.v1",
        "source": {"kind": "upload", "ref": "csv_headers"},
        "assets": [asset],
        "relationships": [],
        "runs": [],
        "evidence": [],
    }, filename=safe_name, source_revision=source_revision)
    if result.payload is None:
        return result
    result.payload["provenance"]["adapter"] = "kairos.csv_headers"
    result.payload["provenance"]["adapter_version"] = ADAPTER_VERSION
    result.payload["provenance"]["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return MetadataGraphResult(
        result.payload,
        result.diagnostics,
        result.warnings + (Diagnostic("CSV_HEADER_ONLY", "Only the header row was read; no data rows or runtime lineage were imported."),),
    )
