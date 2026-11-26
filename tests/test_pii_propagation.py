"""Semantics of the inherited-PII lineage walk (no database).

The route persists whatever this function returns, so these tests are the
authority for what may and may not be inherited.
"""
from __future__ import annotations

from backend.app.services.pii_propagation import derive_inherited_columns


def _edge(edge_id: str, source: str, target: str) -> dict[str, str]:
    return {"edge_id": edge_id, "source_column_id": source, "target_column_id": target}


def test_source_classification_inherits_one_hop():
    proposals = derive_inherited_columns(
        {"raw.email": {"classification": "PII_SOURCE"}},
        [_edge("e1", "raw.email", "stg.masked_email")],
        classified_columns=["raw.email"],
        depth=1,
    )
    assert [item["column_id"] for item in proposals] == ["stg.masked_email"]
    assert proposals[0]["edge_ids"] == ["e1"]
    assert proposals[0]["depth"] == 1
    assert proposals[0]["seed_classification"] == "PII_SOURCE"


def test_propagation_is_bounded_by_depth():
    edges = [
        _edge("e1", "a", "b"),
        _edge("e2", "b", "c"),
        _edge("e3", "c", "d"),
    ]
    one_hop = derive_inherited_columns({"a": {"classification": "PII_SOURCE"}}, edges, [], depth=1)
    two_hops = derive_inherited_columns({"a": {"classification": "PII_SOURCE"}}, edges, [], depth=2)
    assert {item["column_id"] for item in one_hop} == {"b"}
    assert {item["column_id"] for item in two_hops} == {"b", "c"}


def test_a_steward_classification_is_never_overwritten_and_stops_the_walk():
    edges = [_edge("e1", "a", "b"), _edge("e2", "b", "c")]
    proposals = derive_inherited_columns(
        {"a": {"classification": "PII_SOURCE"}},
        edges,
        classified_columns=["a", "b"],
        depth=3,
    )
    # b already has a decision, so neither b nor the path through b is claimed.
    assert proposals == []


def test_masked_cleared_and_unknown_never_seed_propagation():
    for classification in ("PII_MASKED", "PII_CLEARED", "PII_POTENTIAL", "UNKNOWN"):
        proposals = derive_inherited_columns(
            {"a": {"classification": classification}},
            [_edge("e1", "a", "b")],
            [],
            depth=2,
        )
        assert proposals == [], classification


def test_inherited_columns_can_continue_propagating():
    proposals = derive_inherited_columns(
        {"a": {"classification": "PII_INHERITED"}},
        [_edge("e1", "a", "b")],
        classified_columns=["a"],
        depth=1,
    )
    assert [item["column_id"] for item in proposals] == ["b"]


def test_cycles_are_visited_once_and_never_propose_the_seed():
    edges = [_edge("e1", "a", "b"), _edge("e2", "b", "a")]
    proposals = derive_inherited_columns({"a": {"classification": "PII_SOURCE"}}, edges, [], depth=4)
    assert [item["column_id"] for item in proposals] == ["b"]


def test_missing_edge_ids_are_ignored():
    proposals = derive_inherited_columns(
        {"a": {"classification": "PII_SOURCE"}},
        [{"edge_id": "", "source_column_id": "a", "target_column_id": "b"}],
        [],
        depth=2,
    )
    # An inheritance row must be auditable; an edge with no id cannot justify it.
    assert proposals == []


def test_empty_inputs_return_nothing():
    assert derive_inherited_columns({}, [_edge("e1", "a", "b")], [], depth=3) == []
    assert derive_inherited_columns({"a": {"classification": "PII_SOURCE"}}, [], [], depth=3) == []
    assert derive_inherited_columns({"a": {"classification": "PII_SOURCE"}}, [_edge("e1", "a", "b")], [], depth=0) == []
