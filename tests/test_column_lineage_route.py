"""Offline regression tests for GET /api/v1/column-lineage.

The route returns explicit column relationships, but its projection referenced
`le.` and `etv.` aliases that were declared only inside an `EXISTS (...)` subquery
(and were therefore out of scope). These tests pin two things:

1. every `alias.` reference in the statement's SELECT list is declared by a
   FROM/JOIN clause *outside* any subquery;
2. the response mapping built from the selected columns is unchanged.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.app.api.routes import lineage as lineage_module


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.executed_sql = sql
        self.params = params

    def fetchall(self):
        return list(self.rows)


class _Connection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_args, **_kwargs):
        return self.cursor_instance


def _strip_parenthesised(sql: str) -> str:
    """Return the statement with each parenthesised group replaced by a token.

    Subqueries keep their enclosing clause (and therefore their trailing alias)
    visible, while aliases declared *inside* the group are removed.
    """
    kept, depth = [], 0
    for char in sql:
        if char == "(":
            if depth == 0:
                kept.append(" _subquery_ ")
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            kept.append(char)
    return "".join(kept)


def _declared_aliases(sql: str) -> set[str]:
    """Table aliases introduced by top-level FROM/JOIN clauses."""
    top_level = _strip_parenthesised(sql)
    pattern = r"\b(?:FROM|JOIN)\s+(?:LATERAL\s+)?([A-Za-z_][\w.]*)\s+(?:AS\s+)?([A-Za-z_]\w*)"
    return {match.group(2).lower() for match in re.finditer(pattern, top_level, re.IGNORECASE)}


def _projected_qualifiers(sql: str) -> set[str]:
    """Qualifiers (the `x` in `x.column`) used by the statement's SELECT list."""
    select_list = _strip_parenthesised(sql).split("FROM", 1)[0]
    return {match.group(1).lower() for match in re.finditer(r"\b([a-z_]\w*)\.", select_list, re.IGNORECASE)}


def test_projection_only_references_aliases_declared_in_the_from_clause(monkeypatch):
    cursor = _Cursor(rows=[])
    monkeypatch.setattr(lineage_module, "get_conn", lambda: _Connection(cursor))

    lineage_module.get_column_lineage(user={"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"})

    scope_missing = _projected_qualifiers(cursor.executed_sql) - _declared_aliases(cursor.executed_sql)
    assert scope_missing == set(), (
        "column-lineage projection references aliases that no top-level FROM/JOIN declares: "
        f"{sorted(scope_missing)}"
    )
    # the edge/temporal join must still be present, not dropped with the subquery
    assert "JOIN LATERAL" in cursor.executed_sql.upper()
    assert "edge_temporal_version" in cursor.executed_sql


def test_mappings_expose_edge_metadata_from_the_joined_edge_version(monkeypatch):
    valid_from = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    recorded_from = datetime(2026, 11, 10, 8, 5, tzinfo=timezone.utc)
    row = {
        "evidence_id": "2bb775fc-d00a-4403-9a49-e1b26bef72ea",
        "evidence_type": "RUNTIME_POSITIVE",
        "evidence_ref": "evt-1",
        "run_id": "run_999",
        "source_column_id": "11111111-1111-4111-8111-111111111111",
        "target_column_id": "22222222-2222-4222-8222-222222222222",
        "source_asset": "analytics.public.orders",
        "source_column": "order_id",
        "target_asset": "analytics.public.revenue_daily",
        "target_column": "order_id",
        "edge_id": "33333333-3333-4333-8333-333333333333",
        "valid_from": valid_from,
        "valid_to": None,
        "transaction_from": recorded_from,
        "transaction_to": None,
        "diagnostics": {"adapter": "kairos.openlineage"},
    }
    cursor = _Cursor(rows=[row])
    monkeypatch.setattr(lineage_module, "get_conn", lambda: _Connection(cursor))

    body = lineage_module.get_column_lineage(
        valid_as_of="2026-11-15T00:00:00Z",
        recorded_as_of="2026-11-15T00:00:00Z",
        user={"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"},
    )

    assert body["ok"] is True
    assert body["counts"] == {"total": 1, "undated_valid_time": 0}
    mapping = body["mappings"][0]
    assert mapping["source_asset"] == "analytics.public.orders"
    assert mapping["target_asset"] == "analytics.public.revenue_daily"
    assert mapping["source_asset_id"] == row["source_column_id"]
    assert mapping["target_asset_id"] == row["target_column_id"]
    assert mapping["mapping_type"] == "RUNTIME_POSITIVE"
    assert mapping["evidence_ref"] == "evt-1"
    assert mapping["run_id"] == "run_999"
    assert mapping["valid_from"] == valid_from.isoformat()
    assert mapping["recorded_from"] == recorded_from.isoformat()
    assert mapping["metadata"] == {"adapter": "kairos.openlineage"}
    assert cursor.params == {"valid": "2026-11-15T00:00:00Z", "recorded": "2026-11-15T00:00:00Z"}
