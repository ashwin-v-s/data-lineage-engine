"""In-memory stand-in for the PostgreSQL cursor used by OpenLineage ingestion.

The ingestion service is intentionally written against a psycopg2 cursor, so the
tests supply a cursor that understands the handful of statements the service
issues. Rows are kept in dictionaries, which makes idempotency, identity
matching and edge reuse observable without a database.

This module is imported by tests only; pytest does not collect it.
"""
from __future__ import annotations

from contextlib import contextmanager


class FakeCursor:
    def __init__(self) -> None:
        self.rowcount = 1
        self.executed: list[tuple[str, tuple | None]] = []
        self.raw_events: dict[str, str] = {}
        self.jobs: dict[tuple[str, str], str] = {}
        self.runs: dict[str, dict] = {}
        self.datasets: dict[tuple[str, str], str] = {}
        self.edges: list[dict] = []
        self.evidence: dict[str, str] = {}
        self.temporal: set[tuple[str, str]] = set()
        self._counter = 0
        self._result = None

    # -- helpers ---------------------------------------------------------
    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def executed_sql(self) -> list[str]:
        return [text for text, _params in self.executed]

    def count_sql(self, needle: str) -> int:
        needle = needle.lower()
        return sum(1 for text in self.executed_sql() if needle in text)

    # -- cursor API ------------------------------------------------------
    def execute(self, sql, params=None):
        text = " ".join(str(sql).split()).lower()
        self.executed.append((text, params))
        self.rowcount = 1
        self._result = None

        if "current_setting('kairos.workspace_id'" in text:
            self._result = {"workspace_id": "11111111-1111-4111-8111-111111111111"}
        elif text.startswith("insert into raw_event"):
            event_id = params[0]
            if event_id in self.raw_events:
                self.rowcount = 0
            else:
                self.raw_events[event_id] = params[1]
        elif text.startswith("insert into job"):
            key = (params[0], params[1])
            self.jobs.setdefault(key, self._next_id("job"))
            self._result = {"id": self.jobs[key]}
        elif text.startswith("insert into execution_run"):
            run_id, job_id, status = params[0], params[1], params[2]
            existing = self.runs.get(run_id)
            if existing and existing["status"] in {"completed", "failed"} and status == "running":
                status = existing["status"]
            self.runs[run_id] = {
                "job_id": job_id,
                "status": status,
                "started_at": params[3] if existing is None else existing.get("started_at") or params[3],
                "completed_at": params[4] or (existing or {}).get("completed_at"),
            }
            self._result = {"id": f"run-row-{run_id}"}
        elif "from dataset where name" in text:
            key = (params[1], params[0])  # (schema_name, name)
            self._result = {"id": self.datasets[key]} if key in self.datasets else None
        elif text.startswith("insert into dataset"):
            key = (params[2], params[3])  # (schema_name, name)
            self.datasets.setdefault(key, self._next_id("ds"))
            self._result = {"id": self.datasets[key]}
        elif text.startswith("insert into evidence"):
            evidence_id = params[0]
            if evidence_id in self.evidence:
                self.rowcount = 0
            else:
                self.evidence[evidence_id] = self._next_id("ev")
                self._result = {"id": self.evidence[evidence_id]}
        elif "pg_advisory_xact_lock" in text:
            self._result = None
        elif "from lineage_edge where" in text:
            source_id, target_id, operator = params[0], params[1], params[2]
            match = next(
                (
                    edge for edge in self.edges
                    if edge["source"] == source_id
                    and edge["target"] == target_id
                    and edge["operator"] == operator
                ),
                None,
            )
            self._result = {"id": match["id"]} if match else None
        elif text.startswith("insert into lineage_edge"):
            edge = {
                "id": self._next_id("edge"),
                "source": params[0],
                "target": params[1],
                "operator": params[2],
            }
            self.edges.append(edge)
            self._result = {"id": edge["id"]}
        elif "from edge_temporal_version where edge_id" in text:
            key = (params[0], params[1])
            self._result = {"present": 1} if key in self.temporal else None
        elif text.startswith("insert into edge_temporal_version"):
            self.temporal.add((params[0], params[3]))
        elif "from evidence where evidence_id" in text:
            evidence_id = params[0]
            self._result = {"id": self.evidence[evidence_id]} if evidence_id in self.evidence else None

    def fetchone(self):
        return self._result

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class FakeConn:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = 0
        self.rolled_back = 0

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def make_get_conn(cursor: FakeCursor):
    """Return a context-manager factory suitable for patching get_conn."""

    @contextmanager
    def _get_conn():
        yield FakeConn(cursor)

    return _get_conn
