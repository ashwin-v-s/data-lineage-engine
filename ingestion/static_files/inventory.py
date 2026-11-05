"""Static file-inventory adapter; inventory membership is not data lineage."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from ingestion.metadata_graph import (
    MAX_FILE_BYTES,
    Diagnostic,
    MetadataGraphResult,
    _canonical_json,
    _DuplicateJSONKey,
    _reject_duplicate_keys,
    parse_metadata_graph,
)

ADAPTER_VERSION = "1.0.0"
MAX_FILES = 1_000
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _decode(source: bytes | str | Mapping[str, Any]) -> tuple[dict[str, Any] | None, bytes | None, Diagnostic | None]:
    if isinstance(source, bytes):
        raw = source
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
        try:
            document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (UnicodeError, ValueError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON", f"Could not parse UTF-8 JSON: {exc}")
    elif isinstance(source, str):
        try:
            raw = source.encode("utf-8")
            document = json.loads(source, object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (UnicodeError, ValueError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON", f"Could not parse JSON: {exc}")
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
    elif isinstance(source, Mapping):
        try:
            raw = _canonical_json(dict(source))
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (TypeError, ValueError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON_VALUE", f"Inventory must contain JSON-compatible values: {exc}")
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE", f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
    else:
        return None, None, Diagnostic("INVALID_ROOT", "File inventory must be a JSON object.")
    if not isinstance(document, dict):
        return None, None, Diagnostic("INVALID_ROOT", "File inventory must be a JSON object.")
    return document, raw, None


def _relative_path(value: Any, path: str) -> tuple[str | None, Diagnostic | None]:
    if not isinstance(value, str) or not value.strip() or len(value) > 500 or _CONTROL.search(value):
        return None, Diagnostic("INVALID_FILE_PATH", "File path must be a non-empty, printable relative path of at most 500 characters.", path)
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return None, Diagnostic("ABSOLUTE_FILE_PATH", "Absolute paths are not accepted in an inventory import.", path)
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None, Diagnostic("INVALID_FILE_PATH", "File paths cannot be empty or escape their inventory root.", path)
    return "/".join(parts), None


def parse_file_inventory(
    source: bytes | str | Mapping[str, Any],
    *,
    filename: str = "file-inventory.json",
    source_revision: str | None = None,
) -> MetadataGraphResult:
    """Convert an explicit ``files`` inventory into metadata assets, no lineage edges."""
    document, raw, load_error = _decode(source)
    if load_error:
        return MetadataGraphResult(None, (load_error,))
    assert document is not None and raw is not None
    files = document.get("files")
    if not isinstance(files, list):
        return MetadataGraphResult(None, (Diagnostic("FILES_REQUIRED", "files must be an array.", "files"),))
    if not files:
        return MetadataGraphResult(None, (Diagnostic("EMPTY_FILE_INVENTORY", "At least one file is required.", "files"),))
    if len(files) > MAX_FILES:
        return MetadataGraphResult(None, (Diagnostic("FILE_COUNT_LIMIT", f"At most {MAX_FILES:,} files are accepted.", "files"),))

    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[Diagnostic] = []
    for index, item in enumerate(files):
        path = f"files[{index}]"
        if not isinstance(item, dict):
            errors.append(Diagnostic("INVALID_FILE_ENTRY", "Each files entry must be an object.", path))
            continue
        normalized_path, path_error = _relative_path(item.get("path"), f"{path}.path")
        if path_error:
            errors.append(path_error)
            continue
        assert normalized_path is not None
        if normalized_path in seen:
            errors.append(Diagnostic("DUPLICATE_FILE_PATH", f"File path {normalized_path!r} appears more than once.", f"{path}.path"))
            continue
        seen.add(normalized_path)
        size = item.get("size_bytes")
        if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
            errors.append(Diagnostic("INVALID_FILE_SIZE", "size_bytes must be a non-negative integer when provided.", f"{path}.size_bytes"))
            continue
        digest = item.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
            errors.append(Diagnostic("INVALID_FILE_DIGEST", "sha256 must be exactly 64 hexadecimal characters.", f"{path}.sha256"))
            continue
        name = normalized_path.rsplit("/", 1)[-1]
        parent = normalized_path.rsplit("/", 1)[0] if "/" in normalized_path else ""
        file_format = item.get("format")
        if file_format is None and "." in name:
            file_format = name.rsplit(".", 1)[-1].lower()
        assets.append({
            "id": "file:" + hashlib.sha256(normalized_path.encode("utf-8")).hexdigest(),
            "qualified_name": f"file:///{normalized_path}",
            "name": name,
            "namespace": "filesystem",
            "type": "file",
            "kind": "source",
            "metadata": {
                "inventory_only": True,
                "relative_path": normalized_path,
                "parent_directory": parent or None,
                "size_bytes": size,
                "sha256": digest,
                "modified_at": item.get("modified_at")[:100] if isinstance(item.get("modified_at"), str) else None,
                "format": file_format[:64] if isinstance(file_format, str) else None,
            },
        })
    if errors:
        return MetadataGraphResult(None, tuple(errors))

    source_system = document.get("source_system")
    if not isinstance(source_system, str) or not source_system.strip():
        source_system = "file_inventory"
    envelope = {
        "contract_version": "kairos.ingest.v1",
        "source": {"kind": "upload", "ref": source_system.strip()[:512]},
        "assets": assets,
        "relationships": [],
        "runs": [],
        "evidence": [],
    }
    result = parse_metadata_graph(envelope, filename=filename, source_revision=source_revision)
    if result.payload is None:
        return result
    result.payload["provenance"]["adapter"] = "kairos.file_inventory"
    result.payload["provenance"]["adapter_version"] = ADAPTER_VERSION
    result.payload["provenance"]["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return result
