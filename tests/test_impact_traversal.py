"""Impact traversal semantics: depth, direction and evidence-state filtering.

The route is written against a psycopg2 cursor, so this test supplies a cursor
that answers the four statements the traversal issues (root lookup, one hop
query per depth, the edge-evidence aggregate, and dataset labels) from an
in-memory graph. It therefore verifies the grouping, direction and filtering
decisions rather than the SQL planner.

Graph (all DATASET granularity)::

    A --RUNTIME_POSITIVE--> B --STATIC_DEPENDENCY--> C --RUNTIME_POSITIVE--> D
    A --(no evidence)-----> E
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.api.routes import lineage as lineage_module

A = "00000000-0000-4000-8000-00000000000a"
B = "00000000-0000-4000-8000-00000000000b"
C = "00000000-0000-4000-8000-00000000000c"
D = "00000000-0000-4000-8000-00000000000d"
E = "00000000-0000-4000-8000-00000000000e"

DATASETS = {
    A: {"id": A, "name": "orders", "type": "table", "schema_name": "public",
        "database_name": "analytics", "source_system": "postgres"},
    B: {"id": B, "name": "orders_clean", "type": "view", "schema_name": "public",
        "database_name": "analytics", "source_system": "postgres"},
    C: {"id": C, "name": "revenue_daily", "type": "table", "schema_name": "public",
        "database_name": "analytics", "source_system": "postgres"},
    D: {"id": D, "name": "revenue_export", "type": "table", "schema_name": "public",
        "database_name": "analytics", "source_system": "postgres"},
    E: {"id": E, "name": "orphan_export", "type": "table", "schema_name": "public",
        "database_name": "analytics", "source_system": "postgres"},
}

EDGES = [
    {"edge_id": "edge-ab", "source": A, "target": B, "granularity": "DATASET"},
    {"edge_id": "edge-bc", "source": B, "target": C, "granularity": "DATASET"},
    {"edge_id": "edge-cd", "source": C, "target": D, "granularity": "DATASET"},
    {"edge_id": "edge-ae", "source": A, "target": E, "granularity": "DATASET"},
]

EVIDENCE = {
    "edge-ab": [{"edge_id": "edge-ab", "evidence_type": "RUNTIME_POSITIVE",
                 "source_system": "openlineage", "coverage": {"run_covered": True},
                 "parser_status": "ok", "run_id": "run_999", "event_time": None,
                 "diagnostics": None}],
    "edge-bc": [{"edge_id": "edge-bc", "evidence_type": "STATIC_DEPENDENCY",
                 "source_system": "dbt", "coverage": None, "parser_status": "ok",
                 "run_id": None, "event_time": None, "diagnostics": None}],
    "edge-cd": [{"edge_id": "edge-cd", "evidence_type": "RUNTIME_POSITIVE",
                 "source_system": "openlineage", "coverage": {"run_covered": True},
                 "parser_status": "ok", "run_id": "run_998", "event_time": None,
                 "diagnostics": None}],
}


class _Cursor:
    def __init__(self):
        self._rows: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        query = " ".join(str(sql).split())
        params = params or ()
        if "SELECT DISTINCT le.id::text AS edge_id" in query:
            frontier = set(params[0])
            for value in params[1:]:
                if isinstance(value, list):
                    frontier |= set(value)
            self._rows = [
                edge for edge in EDGES
                if edge["source"] in frontier or edge["target"] in frontier
            ]
        elif "JOIN evidence e ON e.id = etv.evidence_id" in query:
            edge_ids = list(params[0])
            self._rows = [row for edge_id in edge_ids for row in EVIDENCE.get(edge_id, [])]
        elif "FROM dataset" in query and "id = ANY" in query:
            wanted = list(params[0])
            self._rows = [DATASETS[dataset] for dataset in wanted if dataset in DATASETS]
        elif "FROM dataset" in query and "id = %s::uuid" in query:
            dataset = params[0]
            self._rows = [DATASETS[dataset]] if dataset in DATASETS else []
        else:
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Connection:
    def __init__(self):
        self.cur = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_args, **_kwargs):
        return self.cur


def _impact(monkeypatch, asset_id, **overrides):
    monkeypatch.setattr(lineage_module, "get_conn", _Connection)
    options = {"depth": 3, "granularity": "DATASET", "direction": "downstream",
               "evidence_state": "all"}
    options.update(overrides)
    return lineage_module.get_downstream_impact(
        asset_id=asset_id, as_of=None, recorded_as_of=None, **options
    )


def _by_depth(result):
    return {level["depth"]: [asset["name"] for asset in level["assets"]]
            for level in result["levels"]}


def _states(result):
    return {asset["name"]: asset["state"]
            for level in result["levels"] for asset in level["assets"]}


def test_downstream_traversal_groups_by_hop_and_labels_each_hop(monkeypatch):
    result = _impact(monkeypatch, A)

    assert result["direction"] == "downstream"
    assert result["depth"] == 3
    assert _by_depth(result) == {1: ["orders_clean", "orphan_export"],
                                 2: ["revenue_daily"],
                                 3: ["revenue_export"]}
    assert _states(result) == {
        "orders_clean": "OBSERVED",
        "orphan_export": "UNKNOWN",
        "revenue_daily": "POSSIBLE",
        "revenue_export": "OBSERVED",
    }
    assert result["total_affected"] == 4
    assert result["state_counts"] == {
        "OBSERVED": 2, "POSSIBLE": 1, "REFUTED_FOR_RUN": 0, "UNKNOWN": 1,
    }


def test_depth_limits_how_far_the_walk_goes(monkeypatch):
    result = _impact(monkeypatch, A, depth=1)

    assert _by_depth(result) == {1: ["orders_clean", "orphan_export"]}
    assert result["total_affected"] == 2


def test_upstream_walks_the_other_way(monkeypatch):
    result = _impact(monkeypatch, C, direction="upstream")

    assert _by_depth(result) == {1: ["orders_clean"], 2: ["orders"]}
    assert _states(result) == {"orders_clean": "POSSIBLE", "orders": "OBSERVED"}


def test_evidence_state_filter_hides_hops_and_stops_traversal_through_them(monkeypatch):
    result = _impact(monkeypatch, A, evidence_state="OBSERVED")

    # B is observed, but B -> C only has declared evidence, so C and D are not
    # reachable: the walk must not pass through a hop the filter hides.
    assert _by_depth(result) == {1: ["orders_clean"]}
    assert result["total_affected"] == 1
    assert result["evidence_state"] == "OBSERVED"
    assert result["state_counts"] == {
        "OBSERVED": 1, "POSSIBLE": 0, "REFUTED_FOR_RUN": 0, "UNKNOWN": 0,
    }


def test_unknown_is_reachable_only_when_it_is_not_filtered_out(monkeypatch):
    unknown = _impact(monkeypatch, A, evidence_state="UNKNOWN")
    possible = _impact(monkeypatch, B, evidence_state="POSSIBLE")

    assert _by_depth(unknown) == {1: ["orphan_export"]}
    # The filter applies to the first hop too: filtering A to POSSIBLE hides the
    # observed A -> B hop, so the report is empty rather than skipping ahead.
    assert _by_depth(_impact(monkeypatch, A, evidence_state="POSSIBLE")) == {}
    assert _by_depth(possible) == {1: ["revenue_daily"]}


def test_both_directions_include_upstream_and_downstream_of_the_root(monkeypatch):
    result = _impact(monkeypatch, B, direction="both", depth=1)

    assert sorted(_by_depth(result)[1]) == ["orders", "revenue_daily"]


def test_unknown_asset_is_not_silently_an_empty_report(monkeypatch):
    with pytest.raises(HTTPException) as excinfo:
        _impact(monkeypatch, "00000000-0000-4000-8000-00000000ffff")

    assert excinfo.value.status_code == 404
