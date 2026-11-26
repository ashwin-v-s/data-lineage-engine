from psycopg2.extras import Json

from backend.app.schemas.audit import RollbackRequest
from backend.app.services.asset_versions import (
    SNAPSHOT_FIELDS,
    ensure_baseline_version,
    read_metadata_snapshot,
    record_asset_version,
)


class FakeCursor:
    def __init__(self, dataset, versions=None):
        self.dataset = dataset
        self.versions = list(versions or [])
        self.result = None
        self.insert_params = None
        self.sql = ""

    def execute(self, sql, params=None):
        self.sql = " ".join(sql.split())
        if self.sql.startswith("SELECT description, tags, owner_name"):
            self.result = tuple(self.dataset[field] for field in SNAPSHOT_FIELDS)
        elif self.sql.startswith("SELECT COALESCE(MAX(version_number)"):
            self.result = (max(self.versions, default=0) + 1,)
        elif self.sql.startswith("SELECT 1 FROM asset_version"):
            self.result = (1,) if self.versions else None
        elif self.sql.startswith("INSERT INTO asset_version"):
            self.insert_params = params
            self.versions.append(params[1])
            self.result = None
        else:
            raise AssertionError(f"unexpected SQL: {self.sql}")

    def fetchone(self):
        return self.result


def test_snapshot_excludes_identity_and_serializes_mutable_fields():
    dataset = {
        "description": "Revenue mart",
        "tags": ["revenue", "gold"],
        "owner_name": "Gauree Hatkar",
        "steward_name": "Finance Analytics Steward",
        "owner_id": None,
        "steward_id": None,
    }
    cur = FakeCursor(dataset, versions=[1])

    version = record_asset_version(cur, "asset-1", "tester@example.com", "Tags updated")

    assert version == 2
    assert cur.insert_params[0] == "asset-1"
    assert cur.insert_params[1] == 2
    assert isinstance(cur.insert_params[2], Json)
    assert cur.insert_params[2].adapted == dataset
    assert "name" not in cur.insert_params[2].adapted


def test_baseline_is_created_once_then_not_replaced():
    dataset = {
        "description": "Before",
        "tags": [],
        "owner_name": "Owner",
        "steward_name": "Steward",
        "owner_id": None,
        "steward_id": None,
    }
    cur = FakeCursor(dataset)

    ensure_baseline_version(cur, "asset-1", "tester@example.com")
    assert cur.versions == [1]

    ensure_baseline_version(cur, "asset-1", "tester@example.com")
    assert cur.versions == [1]


def test_rollback_request_accepts_path_asset_id_without_body_duplicate():
    request = RollbackRequest(
        from_version=2,
        to_version=1,
        rollback_reason="Restore the previous description",
    )
    assert request.asset_id is None
    assert request.from_version == 2


def test_snapshot_reader_returns_none_for_missing_asset():
    cur = FakeCursor({})
    cur.execute = lambda *args, **kwargs: setattr(cur, "result", None)
    assert read_metadata_snapshot(cur, "missing") is None
