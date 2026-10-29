"""Live end-to-end API integration tests against the shared Supabase project.

These tests exercise the real HTTP surface of the Kairos API, so they are
fail-closed in two independent ways:

* ``tests.conftest.requires_live_backend`` keeps the module dormant unless an
  operator opts in with ``KAIROS_LIVE_API_TESTS=1`` (together with
  ``DATABASE_URL`` and ``SUPABASE_URL``).
* A real, verified Supabase end-user access token must be supplied in
  ``KAIROS_TEST_USER_TOKEN``; without it every protected route fails closed
  with 401/503.

When either condition is unmet the whole module is skipped with a clear,
human-readable reason, so the default offline run never touches the network or
the shared database.
"""
from __future__ import annotations

import os

import pytest

from tests.conftest import requires_live_backend

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from backend.app.main import app


def _operator_token() -> str | None:
    """The bearer token an operator supplies to run these live tests."""
    token = os.getenv("KAIROS_TEST_USER_TOKEN", "").strip()
    return token or None


# A single module-level gate: nothing runs unless live mode is opted in *and*
# an operator has supplied an end-user token.
pytestmark = [
    requires_live_backend,
    pytest.mark.skipif(
        _operator_token() is None,
        reason=(
            "Set KAIROS_TEST_USER_TOKEN to a valid Supabase end-user access "
            "token to run the live API integration tests."
        ),
    ),
]


def _client() -> TestClient:
    """A TestClient authenticated as the operator-supplied end user."""
    return TestClient(app, headers={"Authorization": f"Bearer {_operator_token()}"})


def test_catalog_read_returns_200():
    res = _client().get("/api/v1/catalog")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("ok") is True
    assert isinstance(body.get("assets"), list)


def test_search_returns_200():
    res = _client().get("/api/v1/search", params={"q": "", "page": 1, "page_size": 5})
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body.get("results"), list)
    assert isinstance(body.get("total"), int)


def test_recently_viewed_returns_items_and_total():
    res = _client().get("/api/v1/me/recently-viewed")
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body.get("items"), list)
    assert isinstance(body.get("total"), int)


def test_downstream_impact_returns_200_for_one_asset():
    client = _client()
    catalog = client.get("/api/v1/catalog")
    assert catalog.status_code == 200, catalog.text
    assets = catalog.json().get("assets") or []
    if not assets:
        pytest.skip("The live catalog exposes no assets to use as a lineage anchor.")
    asset_id = assets[0]["id"]
    res = client.get(f"/api/v1/assets/{asset_id}/downstream-impact")
    assert res.status_code == 200, res.text
