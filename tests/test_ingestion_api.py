"""M3 ingestion API contract tests.

These run offline: no Supabase session, no database.  They pin the parts of the
preview/commit contract that must hold regardless of infrastructure — auth is
required, preview has no side effects, client identity is never trusted, and
derived identifiers are workspace-scoped and deterministic.

The live persistence checks (import once, idempotent replay, cross-workspace
isolation) live in ``tests/test_live_ingestion_storage.py`` and are opt-in.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.api.routes import ingestion as ingestion_module
from backend.app.api.routes.ingestion import _canonical, _evidence_key, _validate_graph
from backend.app.auth import require_user
from backend.app.main import app
from backend.app.schemas.ingestion import ImportEnvelope, ImportRelationship

ENDPOINT = "/api/v1/ingestion"


def envelope(**overrides) -> ImportEnvelope:
    data = {
        "contract_version": "kairos.ingest.v1",
        "source": {"kind": "upload", "ref": "graph.json"},
        "idempotency_key": "test-run-001",
        "assets": [
            {"id": "raw", "name": "raw_orders", "namespace": "demo/raw", "type": "table"},
            {"id": "model", "name": "orders", "namespace": "demo/model", "type": "model"},
        ],
        "relationships": [{"source_id": "raw", "target_id": "model", "type": "declared_dependency"}],
    }
    data.update(overrides)
    return ImportEnvelope.model_validate(data)


def payload(**overrides) -> dict:
    return envelope(**overrides).model_dump(mode="json")


@pytest.fixture
def authenticated():
    """Override the Supabase dependency; routes still receive a verified shape."""
    user = {"id": "test-user-123", "email": "tester@example.com"}
    app.dependency_overrides[require_user] = lambda: user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_user, None)


# ── Authentication ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("route", ["preview", "commit"])
def test_endpoints_require_authentication(route):
    response = TestClient(app).post(f"{ENDPOINT}/{route}", json=payload())
    assert response.status_code == 401


# ── Preview: read-only ────────────────────────────────────────────────────────

def test_preview_returns_counts_digest_and_evidence_classification(authenticated):
    response = authenticated.post(f"{ENDPOINT}/preview", json=payload())
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["counts"] == {"assets": 2, "relationships": 1}
    assert len(data["content_sha256"]) == 64
    # Declared metadata must never be presented as runtime proof.
    assert "not verified" in data["evidence_classification"]
    assert data["warnings"] == []


def test_preview_opens_no_database_connection(authenticated, monkeypatch):
    def explode():
        raise AssertionError("preview must not touch the database")

    monkeypatch.setattr(ingestion_module, "get_conn", explode)
    response = authenticated.post(f"{ENDPOINT}/preview", json=payload())
    assert response.status_code == 200


def test_preview_warns_when_no_relationships_are_supplied(authenticated):
    response = authenticated.post(f"{ENDPOINT}/preview", json=payload(relationships=[]))
    assert response.status_code == 200
    assert response.json()["counts"]["relationships"] == 0
    assert response.json()["warnings"]


# ── Contract validation ───────────────────────────────────────────────────────

def test_canonical_digest_is_deterministic_and_ignores_idempotency_key():
    assert _canonical(envelope())[1] == _canonical(envelope(idempotency_key="another-key"))[1]
    assert _canonical(envelope())[1] == _canonical(envelope())[1]


def test_canonical_digest_changes_with_content():
    first = _canonical(envelope())[1]
    second = _canonical(envelope(assets=[{"id": "a", "name": "a", "namespace": "n", "type": "table"}]))[1]
    assert first != second


def test_contract_rejects_client_supplied_workspace_identity():
    with pytest.raises(ValidationError):
        envelope(workspace_id="attacker")
    with pytest.raises(ValidationError):
        envelope(user_id="attacker")


def test_rejects_empty_import_instead_of_reporting_success():
    with pytest.raises(HTTPException) as error:
        _validate_graph(envelope(assets=[], relationships=[]))
    assert error.value.status_code == 422
    assert "no assets" in error.value.detail.lower()


def test_rejects_unknown_relationship_endpoint():
    with pytest.raises(HTTPException) as error:
        _validate_graph(envelope(relationships=[{"source_id": "raw", "target_id": "missing"}]))
    assert error.value.status_code == 422


def test_rejects_self_relationship():
    with pytest.raises(HTTPException) as error:
        _validate_graph(envelope(relationships=[{"source_id": "raw", "target_id": "raw"}]))
    assert error.value.status_code == 422


def test_rejects_duplicate_asset_identity():
    duplicate = {
        "id": "other",
        "name": "raw_orders",
        "namespace": "demo/raw",
        "type": "table",
    }
    with pytest.raises(HTTPException) as error:
        _validate_graph(envelope(assets=[payload()["assets"][0], duplicate], relationships=[]))
    assert error.value.status_code == 422


def test_rejects_credentials_in_asset_metadata():
    with pytest.raises(HTTPException) as error:
        _validate_graph(
            envelope(
                assets=[
                    {"id": "raw", "name": "raw", "namespace": "demo", "metadata": {"api_key": "never-store"}},
                    {"id": "model", "name": "model", "namespace": "demo2"},
                ]
            )
        )
    assert error.value.status_code == 422


def test_rejects_unsupported_contract_version():
    with pytest.raises(ValidationError):
        envelope(contract_version="kairos.ingest.v2")


# ── Identifier scoping ────────────────────────────────────────────────────────

def test_evidence_key_is_workspace_scoped_and_deterministic():
    edge = ImportRelationship(source_id="raw", target_id="model", type="declared_dependency")
    key_a = _evidence_key("workspace-a", "a" * 64, 0, edge)
    key_b = _evidence_key("workspace-b", "a" * 64, 0, edge)

    # Identical content in two workspaces must not collide: evidence.evidence_id
    # carries a legacy global UNIQUE constraint.
    assert key_a != key_b
    assert key_a == _evidence_key("workspace-a", "a" * 64, 0, edge)
    assert key_a != _evidence_key("workspace-a", "a" * 64, 1, edge)


def test_evidence_key_changes_with_content():
    edge = ImportRelationship(source_id="raw", target_id="model", type="declared_dependency")
    assert _evidence_key("ws", "a" * 64, 0, edge) != _evidence_key("ws", "b" * 64, 0, edge)
