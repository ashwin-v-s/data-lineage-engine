"""Evidence queries used by freshness and quality evaluation.

Ingestion time is deliberately excluded: receiving an event proves only that
Kairos ingested it, not that the source completed successfully. A qualifying
OpenLineage observation must be associated with a canonical completed run.
"""
from __future__ import annotations

from typing import Any


LAST_SUCCESSFUL_RUNTIME_ACTIVITY_SQL = """
SELECT er.completed_at AS last_activity,
       e.id AS evidence_id,
       e.run_id AS run_id,
       jsonb_build_object(
           'kind', 'SUCCESSFUL_RUNTIME_EVIDENCE',
           'source_system', e.source_system,
           'evidence_type', e.evidence_type,
           'run_id', e.run_id,
           'run_status', er.status,
           'completed_at', er.completed_at,
           'evidence_id', e.id::text,
           'event_time', e.event_time
       ) AS evidence_ref
FROM evidence e
JOIN execution_run er ON er.run_id = e.run_id
WHERE (e.source_dataset_id = %(dataset)s::uuid OR e.target_dataset_id = %(dataset)s::uuid)
  AND e.source_system = 'openlineage'
  AND e.evidence_type = 'RUNTIME_POSITIVE'
  AND er.status = 'completed'
  AND er.completed_at IS NOT NULL
ORDER BY er.completed_at DESC, e.id DESC
LIMIT 1
"""


def last_successful_runtime_activity(cur: Any, dataset_id: str):
    """Return latest positive evidence backed by a completed run, else None."""
    cur.execute(LAST_SUCCESSFUL_RUNTIME_ACTIVITY_SQL, {"dataset": dataset_id})
    return cur.fetchone()
