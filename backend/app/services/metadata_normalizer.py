"""Normalize arbitrary JSON records into a safe, source-neutral metadata preview.

This module is deliberately side-effect free. It does not persist records, connect to
sources, or infer lineage. Explicit relationships are passed through only when supplied.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

_SECRET_KEY = re.compile(r"(token|secret|password|credential|private.?key|api.?key)", re.I)
_RECORD_KEYS = ("records", "items", "data", "results", "rows", "files", "images",
                "documents", "assets", "nodes", "objects", "entries")
_IDENTITY_KEYS = ("id", "uuid", "uid", "key", "path", "uri", "url", "name",
                  "title", "filename", "file_name")
_TYPE_KEYS = ("asset_type", "type", "kind", "resource_type")


def _safe_value(value: Any, depth: int = 0) -> Any:
    """Copy JSON-like values while excluding credential-like keys and limiting nesting."""
    if depth > 8:
        return "[nested value omitted]"
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item, depth + 1)
            for key, item in value.items()
            if not _SECRET_KEY.search(str(key))
        }
    if isinstance(value, list):
        return [_safe_value(item, depth + 1) for item in value[:500]]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _records_from(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in _RECORD_KEYS:
            candidate = payload.get(key)
            if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
                return candidate
        candidates = [
            value for value in payload.values()
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
        ]
        if candidates:
            return max(candidates, key=len)
        return [payload]
    return [{"value": payload}]


def _identity(record: dict[str, Any], index: int) -> str:
    for key in _IDENTITY_KEYS:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()[:700]
    return f"record-{index + 1:05d}"


def _asset_type(record: dict[str, Any]) -> str:
    for key in _TYPE_KEYS:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()[:120]
    mime = record.get("mime_type") or record.get("content_type")
    if isinstance(mime, str) and "/" in mime:
        prefix = mime.split("/", 1)[0].strip().lower()
        if prefix in {"image", "audio", "video", "text", "font", "model"}:
            return prefix
    return "json_record"


def normalize_json_records(payload: Any, source_name: str = "json_import") -> dict[str, Any]:
    """Return generic assets, explicit relationships, discovered fields and capabilities.

    No fields are fabricated except stable fallback identifiers and the generic type label.
    Relationship extraction is intentionally limited to an explicit top-level relationships
    array; relationships are never inferred from record names or matching metadata.
    """
    if not isinstance(payload, (dict, list)):
        payload = {"value": payload}

    raw_records = _records_from(payload)
    if len(raw_records) > 1000:
        raise ValueError("A preview is limited to 1000 records; split larger inputs.")

    root = payload if isinstance(payload, dict) else {}
    source_system = str(root.get("source_system") or root.get("source") or root.get("provider")
                        or source_name or "json_import")[:120]

    explicit_relationships = root.get("relationships", [])
    if not isinstance(explicit_relationships, list):
        explicit_relationships = []
    relationships = [
        _safe_value(item) for item in explicit_relationships[:500]
        if isinstance(item, dict)
    ]

    assets: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    discovered_fields: set[str] = set()
    for index, raw in enumerate(raw_records):
        record = raw if isinstance(raw, dict) else {"value": raw}
        base_id = _identity(record, index)
        asset_id = base_id
        suffix = 1
        while asset_id in used_ids:
            suffix += 1
            asset_id = f"{base_id}#{suffix}"
        used_ids.add(asset_id)

        safe_record = _safe_value(record)
        if not isinstance(safe_record, dict):
            safe_record = {"value": safe_record}
        discovered_fields.update(safe_record.keys())
        nested_metadata = safe_record.get("metadata")
        if isinstance(nested_metadata, dict):
            discovered_fields.update(nested_metadata.keys())

        name = next((str(record[key]) for key in ("name", "title", "path", "filename",
                                                    "file_name", "uri", "url")
                     if record.get(key) is not None and str(record[key]).strip()), asset_id)
        asset = {
            "id": f"json:{asset_id}",
            "name": name[:700],
            "qualified_name": f"{source_system}/{asset_id}",
            "source_system": source_system,
            "type": _asset_type(record),
            "metadata": {
                **safe_record,
                "source_record_index": index,
                "import_mode": "generic_json_preview",
            },
        }
        assets.append(asset)

    type_counts = Counter(asset["type"] for asset in assets)
    capabilities = {
        "asset_discovery": True,
        "metadata_inspection": bool(assets),
        "relationships": bool(relationships),
        "schema_exploration": any(
            isinstance(record, dict) and any(key in record for key in ("columns", "schema", "fields"))
            for record in raw_records
        ),
        "sql_analysis": any(
            isinstance(record, dict) and any(key in record for key in ("sql", "query_text", "compiled_sql"))
            for record in raw_records
        ),
        "execution_history": any(
            isinstance(record, dict) and any(key in record for key in ("run_id", "run", "execution_id"))
            for record in raw_records
        ),
    }
    return {
        "source_system": source_system,
        "is_persistent": False,
        "assets": assets,
        "relationships": relationships,
        "summary": {
            "asset_count": len(assets),
            "relationship_count": len(relationships),
            "discovered_fields": sorted(discovered_fields),
            "asset_type_counts": dict(sorted(type_counts.items())),
        },
        "capabilities": capabilities,
        "warnings": [
            "PREVIEW_ONLY_NOT_PERSISTED",
            "RELATIONSHIPS_ARE_PASSED_THROUGH_ONLY_NOT_INFERRED",
            "SOURCE_FRESHNESS_NOT_VERIFIED",
        ],
    }
