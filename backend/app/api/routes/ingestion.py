"""Authenticated, explicit metadata-graph preview and commit API.

Preview is strictly read-only: it validates the envelope and returns counts,
diagnostics, and the deterministic content digest without opening a database
connection.  Commit is the explicit second action and writes one workspace-scoped
transaction: an import/run record for idempotency, the immutable raw event, the
datasets, one evidence row per relationship, and the bitemporal lineage edge.

Identity rules:

* The workspace and user are derived from the verified Supabase token
  (``require_user``) and the database session settings, never from the request
  body.  ``ImportEnvelope`` forbids unknown fields, so a client-supplied
  ``workspace_id`` is a validation error.
* Every derived identifier that is unique in the database includes the
  workspace, so two workspaces importing byte-identical content do not collide.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import Json, RealDictCursor

from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.schemas.ingestion import ImportEnvelope, ImportRelationship

router = APIRouter(prefix="/ingestion", tags=["ingestion"], dependencies=[Depends(require_user)])
_SENSITIVE_KEY = re.compile(r"token|secret|password|credential|private.?key|api.?key", re.I)

# Evidence classification is part of the response contract: an explicit
# metadata graph is a declaration, never proof that the edge executed.
_STATIC_CLASSIFICATION = (
    "Static declared relationships supplied in a metadata graph; execution is not verified."
)


def _reject_sensitive_keys(value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _SENSITIVE_KEY.search(str(key)):
                raise HTTPException(422, detail="Metadata must not contain credential or secret fields")
            _reject_sensitive_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_sensitive_keys(child)


def _validate_graph(payload: ImportEnvelope) -> list[str]:
    """Validate the envelope before any write; return non-fatal warnings."""
    if not payload.assets:
        raise HTTPException(
            422,
            detail="Import contains no assets. Nothing was imported; add at least one asset.",
        )
    for asset in payload.assets:
        _reject_sensitive_keys(asset.metadata)
    ids = [asset.id for asset in payload.assets]
    identities = [(asset.namespace, asset.name, asset.type) for asset in payload.assets]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, detail="Asset IDs must be unique within an import")
    if len(set(identities)) != len(identities):
        raise HTTPException(422, detail="Asset namespace, name, and type must be unique")
    known = set(ids)
    for edge in payload.relationships:
        if edge.source_id == edge.target_id:
            raise HTTPException(422, detail="Self relationships are not supported")
        if edge.source_id not in known or edge.target_id not in known:
            raise HTTPException(422, detail="Every relationship endpoint must reference an asset in this import")
    return ["No relationships supplied; no lineage edges will be created."] if not payload.relationships else []


def _canonical(payload: ImportEnvelope) -> tuple[dict, str]:
    """Return the normalized body and its content digest.

    The idempotency key is excluded on purpose: retrying the *same content* under
    a new key yields the same digest, while reusing a key for different content
    is rejected by the commit path.
    """
    data = payload.model_dump(mode="json")
    data.pop("idempotency_key", None)
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return data, hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _evidence_key(workspace_id: str, content_sha256: str, index: int, edge: ImportRelationship) -> str:
    """Workspace-scoped, deterministic evidence identifier.

    ``evidence.evidence_id`` carries a legacy global UNIQUE constraint, so the
    workspace must be part of the key.  Without it the second workspace to import
    identical content would fail on a constraint violation.
    """
    digest = hashlib.sha256(
        f"{content_sha256}:{index}:{edge.source_id}:{edge.target_id}:{edge.type}".encode()
    ).hexdigest()
    return f"upload:{workspace_id}:{digest}"


def _split_namespace(namespace: str) -> tuple[str, str]:
    """Map an artifact namespace onto the dataset identity tuple.

    An uploaded artifact has no database: the dotted namespace already holds the
    schema path (``warehouse.raw``).  ``dataset.database_name`` and
    ``schema_name`` are NOT NULL, so the database is stored as an empty string
    and the namespace as the schema.  The catalog builds qualified names by
    skipping empty parts, which yields ``warehouse.raw.orders`` rather than the
    old ``metadata.warehouse.raw.orders`` placeholder.
    """
    return ("", str(namespace or "")[:200])


@router.post("/preview")
def preview(payload: ImportEnvelope, _user: dict = Depends(require_user)):
    """Validate without writing anything; no database connection is opened."""
    warnings = _validate_graph(payload)
    _, content_sha256 = _canonical(payload)
    return {
        "ok": True,
        "contract_version": payload.contract_version,
        "source": payload.source.model_dump(),
        "content_sha256": content_sha256,
        "counts": {"assets": len(payload.assets), "relationships": len(payload.relationships)},
        "warnings": warnings,
        "evidence_classification": _STATIC_CLASSIFICATION,
    }


def _persist_import(
    cur,
    workspace_id: str,
    user_id: str,
    payload: ImportEnvelope,
    content: dict,
    content_sha256: str,
    warnings: list[str],
    now: datetime | None = None,
) -> dict:
    """Write one import on an open, workspace-scoped cursor.

    The caller owns the transaction.  Returns the response body for commit,
    including ``replayed`` when an idempotency key had already been used.
    """
    now = now or datetime.now(timezone.utc)
    cur.execute(
        """
        INSERT INTO import_run (workspace_id, actor_user_id, idempotency_key, source_kind, source_ref,
            content_sha256, contract_version, adapter_name, adapter_version, status, result_summary)
        VALUES (%s, %s, %s, %s, %s, %s, 'kairos.ingest.v1', 'metadata_graph', '1', %s, %s)
        ON CONFLICT (workspace_id, idempotency_key) DO NOTHING
        RETURNING id::text AS id
        """,
        (
            workspace_id,
            user_id,
            payload.idempotency_key,
            payload.source.kind,
            payload.source.ref,
            content_sha256,
            "COMMITTED_WITH_WARNINGS" if warnings else "COMMITTED",
            Json({"assets": len(payload.assets), "relationships": len(payload.relationships)}),
        ),
    )
    inserted = cur.fetchone()
    if inserted is None:
        # Same workspace + idempotency key already exists: replay, never duplicate.
        # The workspace predicate is explicit and not merely inherited from RLS:
        # this lookup must not resolve to another tenant's run even if the policy
        # is ever relaxed or bypassed by the connecting role.
        cur.execute(
            """
            SELECT id::text AS id, content_sha256, result_summary
            FROM import_run WHERE workspace_id = %s AND idempotency_key = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (workspace_id, payload.idempotency_key),
        )
        prior = cur.fetchone()
        if prior is None:
            raise HTTPException(409, detail="Idempotency record is unavailable; retry with a new key")
        if prior["content_sha256"] != content_sha256:
            raise HTTPException(409, detail="Idempotency key was already used for different content")
        return {
            "ok": True,
            "replayed": True,
            "import_id": prior["id"],
            "content_sha256": content_sha256,
            "counts": prior["result_summary"] or {"assets": 0, "relationships": 0},
            "warnings": warnings,
            "evidence_classification": _STATIC_CLASSIFICATION,
        }

    import_id = inserted["id"]
    event_id = f"upload:{workspace_id}:{content_sha256}"
    cur.execute(
        """
        INSERT INTO raw_event (event_id, payload, payload_hash, source_system)
        VALUES (%s, %s, %s, 'upload') ON CONFLICT (event_id) DO NOTHING
        """,
        (event_id, Json(content), content_sha256),
    )

    ids: dict[str, str] = {}
    for asset in payload.assets:
        database_name, schema_name = _split_namespace(asset.namespace)
        cur.execute(
            """
            INSERT INTO dataset (source_system, namespace, database_name, schema_name, name,
                asset_type, description, tags)
            VALUES ('upload', %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (workspace_id, source_system, namespace, database_name, schema_name, name, asset_type)
            DO UPDATE SET description=COALESCE(EXCLUDED.description, dataset.description),
                          tags=CASE WHEN cardinality(EXCLUDED.tags) > 0 THEN EXCLUDED.tags ELSE dataset.tags END
            RETURNING id::text AS id
            """,
            (
                asset.namespace,
                database_name,
                schema_name,
                asset.name,
                asset.type.upper(),
                asset.description,
                asset.tags,
            ),
        )
        ids[asset.id] = cur.fetchone()["id"]

    edge_count = 0
    for index, edge in enumerate(payload.relationships):
        evidence_key = _evidence_key(workspace_id, content_sha256, index, edge)
        cur.execute(
            """
            INSERT INTO evidence (evidence_id, evidence_type, source_system, granularity,
                operator, parser_status, diagnostics, raw_event_id)
            VALUES (%s, 'STATIC_DEPENDENCY', 'upload', 'DATASET', %s, 'SUPPORTED', %s, %s)
            ON CONFLICT (workspace_id, evidence_id) DO NOTHING
            RETURNING id::text AS id
            """,
            (
                evidence_key,
                edge.type,
                Json({"provenance": edge.provenance or _STATIC_CLASSIFICATION}),
                event_id,
            ),
        )
        evidence_row = cur.fetchone()
        if evidence_row is None:
            cur.execute("SELECT id::text AS id FROM evidence WHERE evidence_id=%s", (evidence_key,))
            evidence_row = cur.fetchone()

        operator_fp = hashlib.sha256(edge.type.encode()).hexdigest()
        query_fp = evidence_key
        cur.execute(
            """
            INSERT INTO lineage_edge (source_id, target_id, granularity, operator_fingerprint, query_fingerprint)
            VALUES (%s, %s, 'DATASET', %s, %s) ON CONFLICT DO NOTHING
            RETURNING id::text AS id
            """,
            (ids[edge.source_id], ids[edge.target_id], operator_fp, query_fp),
        )
        edge_row = cur.fetchone()
        if edge_row is None:
            cur.execute(
                """
                SELECT id::text AS id FROM lineage_edge WHERE source_id=%s AND target_id=%s
                AND granularity='DATASET' AND operator_fingerprint=%s AND query_fingerprint=%s
                """,
                (ids[edge.source_id], ids[edge.target_id], operator_fp, query_fp),
            )
            edge_row = cur.fetchone()
        cur.execute(
            """
            INSERT INTO edge_temporal_version (edge_id, valid_from, effective_time_status,
                transaction_from, evidence_id, source_system)
            SELECT %s, %s, 'UNKNOWN', %s, %s, 'upload'
            WHERE NOT EXISTS (SELECT 1 FROM edge_temporal_version WHERE edge_id=%s
                AND evidence_id=%s AND transaction_to IS NULL)
            """,
            (edge_row["id"], now, now, evidence_row["id"], edge_row["id"], evidence_row["id"]),
        )
        edge_count += 1

    summary = {"assets": len(payload.assets), "relationships": edge_count}
    cur.execute("UPDATE import_run SET result_summary=%s WHERE id=%s", (Json(summary), import_id))
    return {
        "ok": True,
        "replayed": False,
        "import_id": import_id,
        "content_sha256": content_sha256,
        "counts": summary,
        "warnings": warnings,
        "evidence_classification": _STATIC_CLASSIFICATION,
    }


@router.post("/commit")
def commit(payload: ImportEnvelope, user: dict = Depends(require_user)):
    """Persist one import for the verified user's workspace, idempotently."""
    warnings = _validate_graph(payload)
    content, content_sha256 = _canonical(payload)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT current_setting('kairos.workspace_id') AS workspace_id")
            workspace_id = cur.fetchone()["workspace_id"]
            if not workspace_id:
                # get_conn sets this scope; a missing value means auth context was lost.
                raise HTTPException(503, detail="Workspace context is unavailable")
            return _persist_import(
                cur, workspace_id, user["id"], payload, content, content_sha256, warnings
            )
