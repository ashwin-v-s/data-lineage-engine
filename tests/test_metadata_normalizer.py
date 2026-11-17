from __future__ import annotations

from backend.app.services.metadata_normalizer import normalize_json_records


def test_arbitrary_image_records_preserve_unknown_fields_and_discover_type():
    payload = [
        {
            "id": "image-1",
            "path": "photos/field.jpg",
            "mime_type": "image/jpeg",
            "width": 1920,
            "height": 1080,
            "camera_model": "Example camera",
        },
        {
            "id": "image-2",
            "path": "photos/field.png",
            "mime_type": "image/png",
            "labels": ["outdoor", "station"],
        },
    ]
    result = normalize_json_records(payload, source_name="image_archive")

    assert result["is_persistent"] is False
    assert result["summary"]["asset_count"] == 2
    assert result["summary"]["asset_type_counts"] == {"image": 2}
    assert "camera_model" in result["summary"]["discovered_fields"]
    assert result["assets"][0]["metadata"]["width"] == 1920
    assert result["capabilities"]["metadata_inspection"] is True
    assert result["capabilities"]["relationships"] is False
    assert result["relationships"] == []


def test_unknown_record_type_remains_generic_and_custom_fields_survive():
    result = normalize_json_records(
        {"records": [{"custom_sensor_format": "thermal-v7", "vendor_extension": {"mode": "x"}}]}
    )
    asset = result["assets"][0]
    assert asset["type"] == "json_record"
    assert asset["metadata"]["custom_sensor_format"] == "thermal-v7"
    assert asset["metadata"]["vendor_extension"] == {"mode": "x"}


def test_explicit_relationships_are_preserved_but_never_inferred():
    result = normalize_json_records({
        "assets": [{"id": "a"}, {"id": "b"}],
        "relationships": [{"source_id": "a", "target_id": "b", "type": "contains"}],
    })
    assert result["summary"]["relationship_count"] == 1
    assert result["relationships"][0]["type"] == "contains"
    assert result["capabilities"]["relationships"] is True


def test_secret_like_fields_are_filtered_recursively():
    result = normalize_json_records({
        "records": [{"id": "safe", "api_token": "never-return", "metadata": {
            "password": "never-return", "mime_type": "image/jpeg"
        }}]
    })
    serialized = str(result)
    assert "never-return" not in serialized
    assert "api_token" not in serialized
    assert "password" not in serialized
    assert result["assets"][0]["type"] == "json_record"


def test_duplicate_identifiers_get_stable_unique_suffixes():
    result = normalize_json_records([{"id": "same"}, {"id": "same"}])
    assert result["assets"][0]["id"] == "json:same"
    assert result["assets"][1]["id"] == "json:same#2"


def test_preview_rejects_oversized_record_collections():
    try:
        normalize_json_records([{"id": str(i)} for i in range(1001)])
    except ValueError as exc:
        assert "1000" in str(exc)
    else:
        raise AssertionError("Expected a preview size limit error")
