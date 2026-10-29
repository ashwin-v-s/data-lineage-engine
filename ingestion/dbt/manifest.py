"""Pure dbt manifest adapter for the shared Kairos ingestion envelope.

This adapter reads manifest declarations only. A dependency in the manifest is
not evidence that a model executed; execution events belong to OpenLineage.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from ingestion.metadata_graph import (
    MAX_FILE_BYTES,
    _DuplicateJSONKey,
    Diagnostic,
    MetadataGraphResult,
    _canonical_json,
    _count_and_check_json,
    _reject_duplicate_keys,
    parse_metadata_graph,
)

ADAPTER_VERSION = "1.0.0"
MAX_RESOURCES = 1_000
SUPPORTED_TYPES = {"model", "seed", "snapshot", "source", "exposure"}


def _load(source: bytes | str | Mapping[str, Any]) -> tuple[dict[str, Any] | None, bytes | None, Diagnostic | None]:
    if isinstance(source, bytes):
        raw = source
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
        try:
            document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except ValueError as exc:
            return None, None, Diagnostic("INVALID_JSON", f"Could not parse UTF-8 JSON: {exc}")
        except (UnicodeDecodeError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON", f"Could not parse UTF-8 JSON: {exc}")
    elif isinstance(source, str):
        try:
            raw = source.encode("utf-8")
            document = json.loads(source, object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (UnicodeEncodeError, ValueError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON", f"Could not parse manifest JSON: {exc}")
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
    elif isinstance(source, Mapping):
        try:
            raw = _canonical_json(dict(source))
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (TypeError, ValueError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON_VALUE", f"Manifest must contain JSON-compatible values: {exc}")
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
    else:
        return None, None, Diagnostic("INVALID_ROOT", "dbt manifest must be a JSON object.")
    if not isinstance(document, dict):
        return None, None, Diagnostic("INVALID_ROOT", "dbt manifest must be a JSON object.")
    return document, raw, None


def _as_collection(document: dict[str, Any], key: str, errors: list[Diagnostic], *, required: bool = False) -> dict[str, Any]:
    value = document.get(key, {} if not required else None)
    if not isinstance(value, dict):
        errors.append(Diagnostic("INVALID_DBT_COLLECTION", f"{key} must be an object in a dbt manifest.", key))
        return {}
    return value


def _resource_id(key: str, resource: dict[str, Any], path: str, errors: list[Diagnostic]) -> str | None:
    value = resource.get("unique_id", key)
    if not isinstance(value, str) or not value.strip() or len(value) > 220:
        errors.append(Diagnostic("INVALID_DBT_UNIQUE_ID", "Resource unique_id must be a non-empty string of at most 220 characters.", f"{path}.unique_id"))
        return None
    return value.strip()


def parse_dbt_manifest(
    source: bytes | str | Mapping[str, Any],
    *,
    filename: str = "manifest.json",
    source_revision: str | None = None,
) -> MetadataGraphResult:
    """Normalize supported dbt manifest resources into ``kairos.ingest.v1``."""
    document, raw, load_error = _load(source)
    if load_error:
        return MetadataGraphResult(None, (load_error,))
    assert document is not None and raw is not None

    errors: list[Diagnostic] = []
    _count_and_check_json(document, errors)
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append(Diagnostic("INVALID_DBT_METADATA", "metadata must be an object.", "metadata"))
        metadata = {}
    nodes = _as_collection(document, "nodes", errors, required=True)
    sources = _as_collection(document, "sources", errors)
    exposures = _as_collection(document, "exposures", errors)
    if errors:
        return MetadataGraphResult(None, tuple(errors))

    assets: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    id_by_unique_id: dict[str, str] = {}
    resource_entries: list[tuple[str, str, Any]] = []
    resource_entries.extend(("nodes", key, value) for key, value in nodes.items())
    resource_entries.extend(("sources", key, value) for key, value in sources.items())
    resource_entries.extend(("exposures", key, value) for key, value in exposures.items())
    if len(resource_entries) > MAX_RESOURCES:
        return MetadataGraphResult(None, (Diagnostic("RESOURCE_LIMIT", f"Manifest contains more than {MAX_RESOURCES:,} resources."),))

    skipped_types: set[str] = set()
    dependencies: list[tuple[str, str, str]] = []
    for collection, key, raw_resource in resource_entries:
        path = f"{collection}.{key}"
        if not isinstance(key, str) or not isinstance(raw_resource, dict):
            errors.append(Diagnostic("INVALID_DBT_RESOURCE", "Each dbt resource must be an object keyed by its unique_id.", path))
            continue
        unique_id = _resource_id(key, raw_resource, path, errors)
        if unique_id is None:
            continue
        resource_type = "source" if collection == "sources" else "exposure" if collection == "exposures" else raw_resource.get("resource_type")
        if not isinstance(resource_type, str):
            resource_type = unique_id.split(".", 1)[0]
        resource_type = resource_type.strip().lower()
        if resource_type not in SUPPORTED_TYPES:
            skipped_types.add(resource_type or "unknown")
            continue
        if unique_id in id_by_unique_id:
            errors.append(Diagnostic("DUPLICATE_DBT_UNIQUE_ID", f"Resource {unique_id!r} appears more than once.", path))
            continue
        name = raw_resource.get("name")
        if not isinstance(name, str) or not name.strip():
            # Source identifiers are occasionally supplied as identifier only.
            name = raw_resource.get("identifier")
        if not isinstance(name, str) or not name.strip() or len(name) > 512:
            errors.append(Diagnostic("INVALID_DBT_NAME", "Supported resources require a non-empty name of at most 512 characters.", f"{path}.name"))
            continue

        package = raw_resource.get("package_name", "")
        if not isinstance(package, str):
            errors.append(Diagnostic("INVALID_DBT_PACKAGE", "package_name must be a string.", f"{path}.package_name"))
            continue
        asset_id = f"dbt:{unique_id}"
        namespace = f"dbt/{package.strip() or 'project'}/{resource_type}"
        qname = f"dbt/{unique_id}"
        config = raw_resource.get("config", {})
        if not isinstance(config, dict):
            config = {}
        meta = raw_resource.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}
        columns = raw_resource.get("columns", {})
        column_summary = []
        if isinstance(columns, dict):
            for column_name, column in sorted(columns.items()):
                if isinstance(column_name, str) and isinstance(column, dict):
                    column_summary.append({
                        "name": column_name[:256],
                        "data_type": column.get("data_type") if isinstance(column.get("data_type"), str) else None,
                        "description": column.get("description") if isinstance(column.get("description"), str) else None,
                    })
        tags = raw_resource.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        asset_metadata: dict[str, Any] = {
            "description": raw_resource.get("description") if isinstance(raw_resource.get("description"), str) else "",
            "tags": [tag for tag in tags if isinstance(tag, str)][:200],
            "original_file_path": raw_resource.get("original_file_path") if isinstance(raw_resource.get("original_file_path"), str) else None,
            "database": raw_resource.get("database") if isinstance(raw_resource.get("database"), str) else None,
            "schema": raw_resource.get("schema") if isinstance(raw_resource.get("schema"), str) else None,
            "alias": raw_resource.get("alias") if isinstance(raw_resource.get("alias"), str) else None,
            "materialized": config.get("materialized") if isinstance(config.get("materialized"), str) else None,
            "meta": meta,
            "columns": column_summary,
        }
        assets.append({
            "id": asset_id,
            "qualified_name": qname,
            "name": name.strip(),
            "namespace": namespace,
            "type": resource_type,
            "kind": "source" if resource_type == "source" else "transform" if resource_type in {"model", "snapshot"} else "asset",
            "metadata": asset_metadata,
        })
        id_by_unique_id[unique_id] = asset_id
        depends_on = raw_resource.get("depends_on", {})
        if collection == "exposures" or collection == "nodes":
            if not isinstance(depends_on, dict):
                errors.append(Diagnostic("INVALID_DBT_DEPENDENCIES", "depends_on must be an object when provided.", f"{path}.depends_on"))
                continue
            upstream_ids = depends_on.get("nodes", [])
            if not isinstance(upstream_ids, list) or any(not isinstance(item, str) for item in upstream_ids):
                errors.append(Diagnostic("INVALID_DBT_DEPENDENCIES", "depends_on.nodes must be an array of unique_id strings.", f"{path}.depends_on.nodes"))
                continue
            dependencies.extend((upstream_id, unique_id, f"{path}.depends_on.nodes") for upstream_id in upstream_ids)

    if errors:
        return MetadataGraphResult(None, tuple(errors))
    if not assets:
        return MetadataGraphResult(None, (Diagnostic("NO_SUPPORTED_DBT_RESOURCES", "Manifest contains no supported models, sources, seeds, snapshots, or exposures."),))

    for upstream_uid, downstream_uid, path in dependencies:
        upstream_id = id_by_unique_id.get(upstream_uid)
        downstream_id = id_by_unique_id.get(downstream_uid)
        if upstream_id is None or downstream_id is None:
            continue
        relationships.append({
            "source_id": upstream_id,
            "target_id": downstream_id,
            "edge_type": "declared_dependency",
            "provenance": "dbt manifest depends_on.nodes",
        })

    warnings: list[Diagnostic] = []
    if skipped_types:
        warnings.append(Diagnostic(
            "UNSUPPORTED_DBT_RESOURCE_TYPES",
            "Skipped unsupported dbt resource types: " + ", ".join(sorted(skipped_types)) + ".",
        ))
    unresolved = sum(1 for upstream_uid, downstream_uid, _ in dependencies if upstream_uid not in id_by_unique_id or downstream_uid not in id_by_unique_id)
    if unresolved:
        warnings.append(Diagnostic(
            "UNRESOLVED_DBT_DEPENDENCIES",
            f"Skipped {unresolved} dependency reference(s) whose resources are unsupported or absent from this manifest.",
        ))
    schema_version = metadata.get("dbt_schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        warnings.append(Diagnostic("MISSING_DBT_SCHEMA_VERSION", "Manifest metadata does not identify dbt_schema_version; supported fields were parsed conservatively.", "metadata.dbt_schema_version"))

    envelope = {
        "contract_version": "kairos.ingest.v1",
        "source": {
            "kind": "upload",
            "ref": f"dbt:{metadata['project_name']}" if isinstance(metadata.get("project_name"), str) and metadata["project_name"].strip() else "dbt:project",
        },
        "assets": assets,
        "relationships": relationships,
        "runs": [],
        "evidence": [],
    }
    result = parse_metadata_graph(envelope, filename=filename, source_revision=source_revision)
    if result.payload is None:
        return result
    result.payload["provenance"]["adapter"] = "kairos.dbt_manifest"
    result.payload["provenance"]["adapter_version"] = ADAPTER_VERSION
    result.payload["provenance"]["content_sha256"] = hashlib.sha256(raw).hexdigest()
    if schema_version:
        result.payload["provenance"]["dbt_schema_version"] = schema_version
    combined_warnings = tuple(warnings) + result.warnings
    return MetadataGraphResult(result.payload, (), combined_warnings)
