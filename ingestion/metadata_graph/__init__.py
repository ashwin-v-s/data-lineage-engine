"""Strict, deterministic parser for Kairos metadata-graph JSON files.

This module is intentionally pure: it does not access Supabase, a database,
the network, or source credentials. It validates and normalizes declarations;
it does not claim that declared relationships were executed.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping


CONTRACT_VERSION = "kairos.ingest.v1"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ASSETS = 1_000
MAX_RELATIONSHIPS = 5_000
MAX_JSON_NODES = 100_000
MAX_DEPTH = 16
MAX_ID_LENGTH = 256
MAX_NAME_LENGTH = 512
_SECRET_KEY = re.compile(r"(?:token|secret|password|credential|private.?key|api.?key)", re.I)


class _DuplicateJSONKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(f"Duplicate object key {key!r}.")
        result[key] = value
    return result


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.path is not None:
            result["path"] = self.path
        return result


@dataclass(frozen=True)
class MetadataGraphResult:
    payload: dict[str, Any] | None
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[Diagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return self.payload is not None and not self.diagnostics


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _safe_filename(filename: str) -> str:
    # Support paths supplied from either Windows or POSIX, but retain only the
    # basename so a client path is never treated as a server filesystem path.
    basename = str(filename or "metadata-graph.json").replace("\\", "/").split("/")[-1]
    basename = "".join(ch for ch in basename if ch.isprintable() and ch not in "\r\n\t")
    return basename[:255] or "metadata-graph.json"


def _count_and_check_json(value: Any, diagnostics: list[Diagnostic]) -> None:
    count = 0
    stack: list[tuple[Any, int, str]] = [(value, 0, "$")]
    while stack:
        current, depth, path = stack.pop()
        count += 1
        if count > MAX_JSON_NODES:
            diagnostics.append(Diagnostic("JSON_NODE_LIMIT", f"JSON exceeds {MAX_JSON_NODES:,} values.", path))
            return
        if depth > MAX_DEPTH:
            diagnostics.append(Diagnostic("JSON_DEPTH_LIMIT", f"JSON nesting exceeds {MAX_DEPTH} levels.", path))
            return
        if isinstance(current, float) and not math.isfinite(current):
            diagnostics.append(Diagnostic("NON_FINITE_NUMBER", "JSON numbers must be finite.", path))
            return
        if isinstance(current, dict):
            stack.extend((child, depth + 1, f"{path}.{key}") for key, child in current.items())
        elif isinstance(current, list):
            stack.extend((child, depth + 1, f"{path}[{index}]") for index, child in enumerate(current))


def _sanitize(value: Any, path: str, removed: list[str]) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key in sorted(value):
            if _SECRET_KEY.search(str(key)):
                removed.append(f"{path}.{key}")
                continue
            cleaned[str(key)] = _sanitize(value[key], f"{path}.{key}", removed)
        return cleaned
    if isinstance(value, list):
        return [_sanitize(item, f"{path}[{index}]", removed) for index, item in enumerate(value)]
    return value


def _text(value: Any, *, max_length: int, path: str, label: str, errors: list[Diagnostic]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(Diagnostic("REQUIRED_TEXT", f"{label} must be a non-empty string.", path))
        return None
    value = value.strip()
    if len(value) > max_length:
        errors.append(Diagnostic("TEXT_TOO_LONG", f"{label} must be at most {max_length} characters.", path))
        return None
    if any(ord(char) < 32 for char in value):
        errors.append(Diagnostic("INVALID_TEXT", f"{label} cannot contain control characters.", path))
        return None
    return value


def _qualified_name(asset: Mapping[str, Any], index: int, errors: list[Diagnostic]) -> str | None:
    qualified = asset.get("qualified_name")
    if qualified is not None:
        return _text(qualified, max_length=MAX_NAME_LENGTH, path=f"assets[{index}].qualified_name", label="qualified_name", errors=errors)
    name = _text(asset.get("name"), max_length=MAX_NAME_LENGTH, path=f"assets[{index}].name", label="name (or qualified_name)", errors=errors)
    if name is None:
        return None
    namespace = asset.get("namespace", "general")
    if not isinstance(namespace, str) or not namespace.strip():
        errors.append(Diagnostic("INVALID_NAMESPACE", "namespace must be a non-empty string when provided.", f"assets[{index}].namespace"))
        return None
    namespace = namespace.strip()
    if len(namespace) > MAX_NAME_LENGTH or any(ord(char) < 32 for char in namespace):
        errors.append(Diagnostic("INVALID_NAMESPACE", f"namespace must be at most {MAX_NAME_LENGTH} printable characters.", f"assets[{index}].namespace"))
        return None
    return f"{namespace}/{name}"


def _source_descriptor(value: Any, errors: list[Diagnostic]) -> dict[str, str]:
    if value is None:
        value = {"kind": "upload", "ref": ""}
    if not isinstance(value, dict):
        errors.append(Diagnostic("INVALID_SOURCE", "source must be an object with kind and optional ref.", "source"))
        return {"kind": "upload", "ref": ""}
    kind = value.get("kind", "upload")
    ref = value.get("ref", "")
    if not isinstance(kind, str) or not kind.strip() or len(kind.strip()) > 64:
        errors.append(Diagnostic("INVALID_SOURCE_KIND", "source.kind must be a non-empty string of at most 64 characters.", "source.kind"))
        kind = "upload"
    if not isinstance(ref, str) or len(ref) > 512:
        errors.append(Diagnostic("INVALID_SOURCE_REF", "source.ref must be a string of at most 512 characters.", "source.ref"))
        ref = ""
    return {"kind": kind.strip(), "ref": ref.strip()}


def parse_metadata_graph(
    source: bytes | str | Mapping[str, Any],
    *,
    filename: str = "metadata-graph.json",
    source_revision: str | None = None,
) -> MetadataGraphResult:
    """Validate a `kairos.ingest.v1` metadata graph and return canonical output.

    Accepts UTF-8 bytes/text or an already-decoded object. Invalid input returns
    diagnostics and no payload, so callers cannot accidentally persist partial
    or malformed batches.
    """
    errors: list[Diagnostic] = []
    warnings: list[Diagnostic] = []
    raw: bytes
    document: Any
    if isinstance(source, bytes):
        raw = source
        if len(raw) > MAX_FILE_BYTES:
            return MetadataGraphResult(None, (Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit."),))
        try:
            document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return MetadataGraphResult(None, (Diagnostic("DUPLICATE_JSON_KEY", str(exc)),))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            return MetadataGraphResult(None, (Diagnostic("INVALID_JSON", f"Could not parse UTF-8 JSON: {exc}"),))
    elif isinstance(source, str):
        try:
            raw = source.encode("utf-8")
        except UnicodeEncodeError:
            return MetadataGraphResult(None, (Diagnostic("INVALID_UTF8", "Input text must be valid UTF-8."),))
        if len(raw) > MAX_FILE_BYTES:
            return MetadataGraphResult(None, (Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit."),))
        try:
            document = json.loads(source, object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return MetadataGraphResult(None, (Diagnostic("DUPLICATE_JSON_KEY", str(exc)),))
        except json.JSONDecodeError as exc:
            return MetadataGraphResult(None, (Diagnostic("INVALID_JSON", f"Could not parse JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}."),))
        except RecursionError:
            return MetadataGraphResult(None, (Diagnostic("JSON_DEPTH_LIMIT", f"JSON nesting exceeds {MAX_DEPTH} levels."),))
    elif isinstance(source, Mapping):
        document = dict(source)
        try:
            raw = _canonical_json(document)
            # Reparse canonical JSON to apply the same JSON key/value rules as
            # byte/text input (including string object keys).
            document = json.loads(raw.decode("utf-8"))
        except (TypeError, ValueError, RecursionError):
            return MetadataGraphResult(None, (Diagnostic("INVALID_JSON_VALUE", "Input must contain only JSON-compatible values and finite numbers."),))
        if len(raw) > MAX_FILE_BYTES:
            return MetadataGraphResult(None, (Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit."),))
    else:
        return MetadataGraphResult(None, (Diagnostic("INVALID_ROOT", "Metadata graph must be a JSON object."),))

    if not isinstance(document, dict):
        return MetadataGraphResult(None, (Diagnostic("INVALID_ROOT", "Metadata graph must be a JSON object."),))
    _count_and_check_json(document, errors)

    # The legacy CLI wraps graphs in {kind, payload}; accept that input form,
    # while requiring the current contract version on the graph itself.
    if document.get("kind") == "metadata_graph" and isinstance(document.get("payload"), dict):
        document = document["payload"]

    version = document.get("contract_version")
    if version != CONTRACT_VERSION:
        errors.append(Diagnostic("UNSUPPORTED_CONTRACT_VERSION", f"contract_version must be {CONTRACT_VERSION!r}.", "contract_version"))

    assets = document.get("assets")
    relationships = document.get("relationships", [])
    if not isinstance(assets, list):
        errors.append(Diagnostic("ASSETS_REQUIRED", "assets must be an array.", "assets"))
        assets = []
    if not isinstance(relationships, list):
        errors.append(Diagnostic("RELATIONSHIPS_INVALID", "relationships must be an array when provided.", "relationships"))
        relationships = []
    runs = document.get("runs", [])
    evidence = document.get("evidence", [])
    if not isinstance(runs, list):
        errors.append(Diagnostic("RUNS_INVALID", "runs must be an array when provided.", "runs"))
        runs = []
    if not isinstance(evidence, list):
        errors.append(Diagnostic("EVIDENCE_INVALID", "evidence must be an array when provided.", "evidence"))
        evidence = []
    if isinstance(runs, list) and any(not isinstance(item, dict) for item in runs):
        errors.append(Diagnostic("INVALID_RUN", "Each run must be an object.", "runs"))
    if isinstance(evidence, list) and any(not isinstance(item, dict) for item in evidence):
        errors.append(Diagnostic("INVALID_EVIDENCE", "Each evidence item must be an object.", "evidence"))
    if isinstance(assets, list) and not assets:
        errors.append(Diagnostic("EMPTY_ASSET_BATCH", "At least one asset is required; empty imports are not accepted.", "assets"))
    if len(assets) > MAX_ASSETS:
        errors.append(Diagnostic("ASSET_LIMIT", f"At most {MAX_ASSETS:,} assets are accepted per file.", "assets"))
    if len(relationships) > MAX_RELATIONSHIPS:
        errors.append(Diagnostic("RELATIONSHIP_LIMIT", f"At most {MAX_RELATIONSHIPS:,} relationships are accepted per file.", "relationships"))

    normalized_assets: list[dict[str, Any]] = []
    asset_ids: set[str] = set()
    qualified_names: set[str] = set()
    removed_secret_paths: list[str] = []
    for index, asset in enumerate(assets):
        path = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(Diagnostic("INVALID_ASSET", "Each asset must be an object.", path))
            continue
        asset_id = _text(asset.get("id"), max_length=MAX_ID_LENGTH, path=f"{path}.id", label="Asset id", errors=errors)
        qname = _qualified_name(asset, index, errors)
        if asset_id is not None:
            if asset_id in asset_ids:
                errors.append(Diagnostic("DUPLICATE_ASSET_ID", f"Asset id {asset_id!r} is duplicated.", f"{path}.id"))
            asset_ids.add(asset_id)
        if qname is not None:
            if qname in qualified_names:
                errors.append(Diagnostic("DUPLICATE_QUALIFIED_NAME", f"Qualified name {qname!r} is duplicated.", f"{path}.qualified_name"))
            qualified_names.add(qname)
        if "metadata" in asset and not isinstance(asset["metadata"], dict):
            errors.append(Diagnostic("INVALID_METADATA", "metadata must be an object when provided.", f"{path}.metadata"))
        cleaned = _sanitize(asset, path, removed_secret_paths)
        if asset_id is not None and qname is not None:
            cleaned["id"] = asset_id
            cleaned["qualified_name"] = qname
            cleaned.setdefault("name", qname.rsplit("/", 1)[-1])
            cleaned.setdefault("namespace", qname.rsplit("/", 1)[0] if "/" in qname else "general")
            normalized_assets.append(cleaned)

    normalized_relationships: list[dict[str, Any]] = []
    relationship_keys: set[tuple[str, str, str]] = set()
    for index, relationship in enumerate(relationships):
        path = f"relationships[{index}]"
        if not isinstance(relationship, dict):
            errors.append(Diagnostic("INVALID_RELATIONSHIP", "Each relationship must be an object.", path))
            continue
        source_id = _text(relationship.get("source_id"), max_length=MAX_ID_LENGTH, path=f"{path}.source_id", label="source_id", errors=errors)
        target_id = _text(relationship.get("target_id"), max_length=MAX_ID_LENGTH, path=f"{path}.target_id", label="target_id", errors=errors)
        rel_type = relationship.get("edge_type", relationship.get("type", "declared_dependency"))
        rel_type = _text(rel_type, max_length=128, path=f"{path}.edge_type", label="relationship type", errors=errors)
        if source_id and source_id not in asset_ids:
            errors.append(Diagnostic("UNKNOWN_RELATIONSHIP_SOURCE", f"Relationship source {source_id!r} is not in this asset batch.", f"{path}.source_id"))
        if target_id and target_id not in asset_ids:
            errors.append(Diagnostic("UNKNOWN_RELATIONSHIP_TARGET", f"Relationship target {target_id!r} is not in this asset batch.", f"{path}.target_id"))
        if source_id and target_id and rel_type:
            key = (source_id, target_id, rel_type)
            if key in relationship_keys:
                errors.append(Diagnostic("DUPLICATE_RELATIONSHIP", "Duplicate relationship in this batch.", path))
            relationship_keys.add(key)
            cleaned_rel = _sanitize(relationship, path, removed_secret_paths)
            cleaned_rel["source_id"] = source_id
            cleaned_rel["target_id"] = target_id
            cleaned_rel["edge_type"] = rel_type
            cleaned_rel["evidence_class"] = "DECLARED_METADATA"
            normalized_relationships.append(cleaned_rel)

    source_descriptor = _source_descriptor(document.get("source"), errors)
    if source_revision is not None and (not isinstance(source_revision, str) or len(source_revision) > 512):
        errors.append(Diagnostic("INVALID_SOURCE_REVISION", "source_revision must be a string of at most 512 characters."))
    normalized_runs = _sanitize(runs, "runs", removed_secret_paths)
    normalized_evidence = _sanitize(evidence, "evidence", removed_secret_paths)
    if not normalized_relationships:
        warnings.append(Diagnostic("NO_RELATIONSHIPS", "No relationships are declared; Kairos will not infer them from names or metadata."))
    if removed_secret_paths:
        warnings.append(Diagnostic("SENSITIVE_FIELDS_REMOVED", f"Removed {len(removed_secret_paths)} secret-like field(s) from metadata.", removed_secret_paths[0]))

    if errors:
        return MetadataGraphResult(None, tuple(errors), tuple(warnings))

    normalized_assets.sort(key=lambda item: (item["id"], item["qualified_name"]))
    normalized_relationships.sort(key=lambda item: (item["source_id"], item["target_id"], item["edge_type"]))
    result = {
        "contract_version": CONTRACT_VERSION,
        "source": source_descriptor,
        "assets": normalized_assets,
        "relationships": normalized_relationships,
        "runs": normalized_runs,
        "evidence": normalized_evidence,
        "diagnostics": [],
        "provenance": {
            "adapter": "kairos.metadata_graph",
            "adapter_version": "1.0.0",
            "original_filename": _safe_filename(filename),
            "source_revision": source_revision.strip() if isinstance(source_revision, str) else None,
            "content_sha256": hashlib.sha256(raw).hexdigest(),
        },
    }
    return MetadataGraphResult(result, (), tuple(warnings))
