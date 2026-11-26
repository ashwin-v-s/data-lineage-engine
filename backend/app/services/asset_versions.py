"""Asset metadata version snapshots.

The audit UI historically exposed a version-history endpoint and a rollback
endpoint, but no code ever wrote an ``asset_version`` row and rollback returned
501.  This module is the single writer used by metadata edits and rollback so
the history is built from the rows that were actually changed.

Only mutable metadata is snapshotted.  Identity columns (name, namespace,
asset type) are deliberately excluded: a rollback restores metadata, never
re-identifies an asset or moves its lineage.
"""
from __future__ import annotations

from typing import Any

from psycopg2.extras import Json

# Keep this list in sync with the UPDATE built by the rollback executor.
SNAPSHOT_FIELDS = (
    "description",
    "tags",
    "owner_name",
    "steward_name",
    "owner_id",
    "steward_id",
)


def read_metadata_snapshot(cur, asset_id: str) -> dict[str, Any] | None:
    """Read the mutable metadata of one asset, or ``None`` when it is absent."""
    cur.execute(
        f"SELECT {', '.join(SNAPSHOT_FIELDS)} FROM dataset WHERE id=%s::uuid",
        (asset_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return {field: row[field] for field in SNAPSHOT_FIELDS}
    return {field: row[index] for index, field in enumerate(SNAPSHOT_FIELDS)}


def record_asset_version(
    cur,
    asset_id: str,
    actor: str,
    change_summary: str,
) -> int | None:
    """Append a snapshot and return its version number.

    The caller owns the transaction, so an update and its version row commit or
    roll back together.  A missing asset is a no-op; route-level existence
    checks still return the appropriate 404.
    """
    snapshot = read_metadata_snapshot(cur, asset_id)
    if snapshot is None:
        return None
    cur.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next FROM asset_version WHERE asset_id=%s::uuid",
        (asset_id,),
    )
    next_row = cur.fetchone()
    next_version = next_row["next"] if isinstance(next_row, dict) else next_row[0]
    cur.execute(
        """
        INSERT INTO asset_version
            (asset_id, version_number, snapshot_data, created_by, change_summary)
        VALUES (%s::uuid, %s, %s, %s, %s)
        """,
        (asset_id, next_version, Json(snapshot), actor, change_summary[:500]),
    )
    return next_version


def ensure_baseline_version(cur, asset_id: str, actor: str) -> None:
    """Capture the pre-change state once, so the first edit is reversible."""
    cur.execute(
        "SELECT 1 FROM asset_version WHERE asset_id=%s::uuid LIMIT 1",
        (asset_id,),
    )
    if cur.fetchone() is None:
        record_asset_version(
            cur,
            asset_id,
            actor,
            "Baseline snapshot before the first recorded metadata change",
        )
