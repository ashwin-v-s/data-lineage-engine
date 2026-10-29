"""M1 pure metadata-graph adapter contract and safety tests."""
from __future__ import annotations

import json
from pathlib import Path

from ingestion.metadata_graph import MAX_FILE_BYTES, parse_metadata_graph


FIXTURES = Path(__file__).parent / "fixtures" / "ingestion" / "metadata_graph"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_valid_graph_matches_canonical_fixture_and_preserves_declared_semantics():
    source = _read("valid.json")
    result = parse_metadata_graph(source, filename=r"C:\imports\orders.json", source_revision="git:abc123")

    assert result.ok
    assert not result.diagnostics
    expected = json.loads(_read("expected_normalized.json"))
    assert result.payload == expected
    assert [asset["id"] for asset in result.payload["assets"]] == ["orders-model", "raw-orders"]
    edge = result.payload["relationships"][0]
    assert edge["evidence_class"] == "DECLARED_METADATA"
    assert edge["edge_type"] == "declared_dependency"
    assert result.payload["provenance"]["original_filename"] == "orders.json"
    assert result.payload["provenance"]["source_revision"] == "git:abc123"


def test_same_mapping_normalizes_deterministically_and_sorts_records():
    first = json.loads(_read("valid.json"))
    second = dict(first)
    second["assets"] = list(reversed(first["assets"]))
    second["relationships"] = list(reversed(first["relationships"]))

    result_a = parse_metadata_graph(first)
    result_b = parse_metadata_graph(second)

    assert result_a.ok and result_b.ok
    assert result_a.payload["assets"] == result_b.payload["assets"]
    assert result_a.payload["relationships"] == result_b.payload["relationships"]


def test_invalid_relationship_endpoint_blocks_entire_batch():
    result = parse_metadata_graph(_read("invalid_endpoint.json"))

    assert not result.ok
    assert result.payload is None
    assert "UNKNOWN_RELATIONSHIP_SOURCE" in {item.code for item in result.diagnostics}


def test_unknown_contract_version_has_actionable_diagnostic():
    result = parse_metadata_graph(_read("unsupported_version.json"))

    assert not result.ok
    diagnostic = next(item for item in result.diagnostics if item.code == "UNSUPPORTED_CONTRACT_VERSION")
    assert diagnostic.path == "contract_version"
    assert "kairos.ingest.v1" in diagnostic.message


def test_file_size_limit_is_checked_before_json_parsing():
    result = parse_metadata_graph(b" " * (MAX_FILE_BYTES + 1))

    assert not result.ok
    assert [item.code for item in result.diagnostics] == ["FILE_TOO_LARGE"]


def test_duplicate_ids_and_qualified_names_are_rejected():
    payload = {
        "contract_version": "kairos.ingest.v1",
        "assets": [
            {"id": "same", "namespace": "demo", "name": "asset"},
            {"id": "same", "namespace": "demo", "name": "asset"},
        ],
    }

    result = parse_metadata_graph(payload)

    assert not result.ok
    codes = {item.code for item in result.diagnostics}
    assert {"DUPLICATE_ASSET_ID", "DUPLICATE_QUALIFIED_NAME"} <= codes


def test_secret_like_metadata_fields_are_removed_and_reported():
    payload = {
        "contract_version": "kairos.ingest.v1",
        "assets": [{
            "id": "safe",
            "name": "safe_asset",
            "metadata": {"owner": "team", "api_key": "never-keep-this", "nested": {"password": "secret"}},
        }],
    }

    result = parse_metadata_graph(payload)

    assert result.ok
    metadata = result.payload["assets"][0]["metadata"]
    assert metadata == {"nested": {}, "owner": "team"}
    assert "never-keep-this" not in json.dumps(result.payload)
    assert "SENSITIVE_FIELDS_REMOVED" in {item.code for item in result.warnings}


def test_relationships_are_not_inferred_and_missing_list_is_a_warning():
    result = parse_metadata_graph({
        "contract_version": "kairos.ingest.v1",
        "assets": [{"id": "a", "name": "a"}, {"id": "b", "name": "b"}],
    })

    assert result.ok
    assert result.payload["relationships"] == []
    assert "NO_RELATIONSHIPS" in {item.code for item in result.warnings}


def test_legacy_cli_wrapper_is_accepted_but_normalized_to_current_contract():
    graph = json.loads(_read("valid.json"))
    wrapped = {"kind": "metadata_graph", "payload": graph}

    result = parse_metadata_graph(wrapped)

    assert result.ok
    assert result.payload["contract_version"] == "kairos.ingest.v1"
    assert "kind" not in result.payload


def test_invalid_json_and_non_object_roots_are_rejected():
    invalid_json = parse_metadata_graph(b"{nope")
    non_object = parse_metadata_graph(b"[]")

    assert "INVALID_JSON" in {item.code for item in invalid_json.diagnostics}
    assert "INVALID_ROOT" in {item.code for item in non_object.diagnostics}


def test_utf8_bom_is_accepted_for_files_exported_by_windows_tools():
    result = parse_metadata_graph(b"\xef\xbb\xbf" + _read("valid.json"))

    assert result.ok


def test_duplicate_json_object_keys_are_rejected_instead_of_silently_overwritten():
    result = parse_metadata_graph(
        b'{"contract_version":"kairos.ingest.v1","assets":[],"assets":[{"id":"x","name":"x"}]}'
    )

    assert not result.ok
    assert result.diagnostics[0].code == "DUPLICATE_JSON_KEY"
