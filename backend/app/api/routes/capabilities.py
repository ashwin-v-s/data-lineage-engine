"""
backend/app/api/routes/capabilities.py
───────────────────────────────────────
Per-asset capability registry.

The frontend never hardcodes which tabs or sections an asset page shows.  For
each asset Kairos publishes a small registry describing which capabilities it
*supports* at all and which are *available for this asset right now*, each with
an optional, human-readable ``reason`` when it is not available.

Endpoint
────────
  GET /api/v1/assets/{asset_id}/capabilities

``asset_id`` is a dataset UUID or a dataset name (resolved the same way as the
personalization routes).  Every fact is gathered with a cheap, defensive query;
optional tables introduced by later migrations are probed with ``to_regclass``
so that a missing migration degrades to "not supported" instead of raising.

The decision logic lives in the pure ``resolve_capabilities`` function so it can
be unit-tested without a database.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import RealDictCursor

from backend.app.auth import require_user
from backend.app.db import get_conn

router = APIRouter(tags=["capabilities"], dependencies=[Depends(require_user)])

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)

# The capability vocabulary, in the order the UI should present it.  Every key
# here is always present in a resolver result.
CAPABILITY_KEYS = ("schema", "preview", "lineage", "runs", "quality", "profile", "usage")


def resolve_capabilities(
    *,
    has_columns: bool,
    edge_count: int,
    run_count: int,
    quality_supported: bool,
    quality_available: bool,
    profile_supported: bool = False,
) -> dict[str, dict]:
    """Map raw asset facts to the published capability registry.

    Pure and deterministic: it performs no I/O so the policy can be unit-tested
    in isolation.  Every returned entry has exactly the keys ``supported``,
    ``available`` and ``reason``, and ``reason`` is ``None`` if and only if
    ``available`` is ``True``.
    """
    capabilities: dict[str, dict] = {}

    capabilities["schema"] = {
        "supported": True,
        "available": bool(has_columns),
        "reason": None if has_columns else "No columns have been imported for this asset yet.",
    }
    capabilities["preview"] = {
        "supported": True,
        "available": bool(has_columns),
        "reason": None if has_columns else "Row preview requires imported column metadata.",
    }

    has_edges = edge_count > 0
    capabilities["lineage"] = {
        "supported": True,
        "available": has_edges,
        # The absence of an edge is not a claim that no relationship exists, only
        # that Kairos has no evidence for one yet.
        "reason": None if has_edges else "No evidence-backed relationships were found for this asset.",
    }

    has_runs = run_count > 0
    capabilities["runs"] = {
        "supported": True,
        "available": has_runs,
        "reason": None if has_runs else "No ingestion or execution runs reference this asset.",
    }

    if quality_supported:
        capabilities["quality"] = {
            "supported": True,
            "available": bool(quality_available),
            "reason": None if quality_available else "This asset has no stored quality results.",
        }
    else:
        capabilities["quality"] = {
            "supported": False,
            "available": False,
            "reason": "Kairos does not support quality assertions without the governance migration.",
        }

    profile_available = bool(profile_supported and has_columns)
    capabilities["profile"] = {
        "supported": bool(profile_supported),
        "available": profile_available,
        "reason": None if profile_available else "Column profiling is not enabled for this deployment.",
    }

    capabilities["usage"] = {
        "supported": False,
        "available": False,
        "reason": "Query-log based usage statistics are not collected by Kairos.",
    }

    return capabilities


def _resolve_dataset_id(cur, asset_id: str) -> str | None:
    """Resolve an asset UUID or dataset name to a workspace-scoped dataset id."""
    if _UUID_RE.match(asset_id):
        cur.execute("SELECT id::text FROM dataset WHERE id = %s::uuid LIMIT 1", (asset_id,))
        row = cur.fetchone()
        if row:
            return row["id"]
    cur.execute(
        """
        SELECT id::text FROM dataset
        WHERE lower(name) = lower(%s)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (asset_id,),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _table_exists(cur, name: str) -> bool:
    """Whether an optional (later-migration) table is present in ``public``."""
    cur.execute("SELECT to_regclass(%s) AS reg", (f"public.{name}",))
    return cur.fetchone()["reg"] is not None


def _count_runs(cur, dataset_id: str) -> int:
    """Count committed runs that reference this asset.

    ``execution_run`` (migration 0001) links only to ``job`` -- it carries no
    dataset or column reference -- so there is no reliable dataset<->run link on
    it.  We therefore count only ``import_run`` rows, and we match them to the
    asset through the ``evidence`` rows a commit creates: each committed import
    writes evidence with ``raw_event_id = 'kairos-import:<import_run.id>'`` and
    the dataset/column endpoints it touched.  When the import-run migration is
    absent we cannot determine this at all and honestly return 0.
    """
    if not _table_exists(cur, "import_run"):
        return 0
    cur.execute(
        """
        SELECT COUNT(DISTINCT ir.id)::int AS run_count
        FROM   import_run ir
        JOIN   evidence e ON e.raw_event_id = 'kairos-import:' || ir.id::text
        WHERE  e.source_dataset_id = %s::uuid OR e.target_dataset_id = %s::uuid
        """,
        (dataset_id, dataset_id),
    )
    return int(cur.fetchone()["run_count"])


def _quality_facts(cur, dataset_id: str) -> tuple[bool, bool]:
    """Return ``(supported, available)`` for the quality capability.

    ``quality_assertion`` / ``freshness_evaluation`` are proposal-only today, so
    ``supported`` is expected to be ``False`` in the current deployment.
    """
    supported = _table_exists(cur, "quality_assertion") or _table_exists(cur, "freshness_evaluation")
    if not supported:
        return False, False
    # Prefer the richer freshness table when present, else the legacy results.
    table = "freshness_evaluation" if _table_exists(cur, "freshness_evaluation") else "quality_result"
    cur.execute(
        f"SELECT EXISTS (SELECT 1 FROM {table} WHERE dataset_id = %s::uuid) AS has_quality",
        (dataset_id,),
    )
    return True, bool(cur.fetchone()["has_quality"])


@router.get("/assets/{asset_id}/capabilities")
def get_asset_capabilities(asset_id: str, user: dict = Depends(require_user)):
    """Publish the capability registry for one asset (UUID or dataset name)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            dataset_id = _resolve_dataset_id(cur, asset_id)
            if dataset_id is None:
                raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")

            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM column_record WHERE dataset_id = %s::uuid) AS has_columns",
                (dataset_id,),
            )
            has_columns = bool(cur.fetchone()["has_columns"])

            cur.execute(
                """
                SELECT COUNT(*)::int AS edge_count
                FROM   lineage_edge
                WHERE  source_id = %s::uuid OR target_id = %s::uuid
                """,
                (dataset_id, dataset_id),
            )
            edge_count = int(cur.fetchone()["edge_count"])

            run_count = _count_runs(cur, dataset_id)
            quality_supported, quality_available = _quality_facts(cur, dataset_id)

    capabilities = resolve_capabilities(
        has_columns=has_columns,
        edge_count=edge_count,
        run_count=run_count,
        quality_supported=quality_supported,
        quality_available=quality_available,
        profile_supported=False,
    )
    return {
        "asset_id": dataset_id,
        "capabilities": capabilities,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
