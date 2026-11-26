"""Pure lineage walk for inherited PII classification.

The database layer supplies three read-only facts and this module decides which
columns may inherit a classification. Keeping the decision pure makes the
semantics testable without a database and keeps the SQL route thin.

Rules (deliberately conservative):

* Only ``PII_SOURCE`` and already-inherited columns seed a propagation. A
  cleared, masked, potential or unknown classification never spreads.
* Inheritance travels **downstream** over stored column-lineage edges only. No
  name, schema or table-level guess is ever turned into a column claim.
* A column that already has any classification is never overwritten. A steward
  decision outranks a derived one.
* A seed column is never proposed for itself, even if lineage contains a cycle.
* Proposals are bounded by ``depth`` hops and record the exact edge ids that
  justify them, so each inherited row is auditable to stored evidence.
"""
from __future__ import annotations

from collections import deque
from typing import Iterable, Mapping

PROPAGATING_CLASSIFICATIONS = frozenset({"PII_SOURCE", "PII_INHERITED"})


def derive_inherited_columns(
    seed_columns: Mapping[str, Mapping[str, str]],
    edges: Iterable[Mapping[str, str]],
    classified_columns: Iterable[str],
    depth: int = 3,
) -> list[dict[str, object]]:
    """Return the columns that should inherit a PII classification.

    ``seed_columns`` maps a column id to ``{"classification": ...}``.
    ``edges`` are stored column mappings with ``edge_id``, ``source_column_id``
    and ``target_column_id``. ``classified_columns`` is every column id that
    already carries any classification.

    The result is sorted by target column id, so repeated runs produce the same
    proposal order.
    """
    if depth < 1:
        return []

    seeds = {
        column_id: dict(values)
        for column_id, values in seed_columns.items()
        if values.get("classification") in PROPAGATING_CLASSIFICATIONS
    }
    if not seeds:
        return []

    existing = {str(column_id) for column_id in classified_columns if column_id}

    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        source = str(edge.get("source_column_id") or "")
        target = str(edge.get("target_column_id") or "")
        edge_id = str(edge.get("edge_id") or "")
        # An inherited claim is only acceptable when it can name the stored
        # lineage edge that justifies it.
        if not source or not target or not edge_id or source == target:
            continue
        adjacency.setdefault(source, []).append((target, edge_id))

    # First arrival wins, so the recorded path is the shortest justification.
    proposals: dict[str, dict[str, object]] = {}
    visited: set[str] = set(seeds)

    for seed_id in sorted(seeds):
        queue: deque[tuple[str, int, tuple[str, ...]]] = deque([(seed_id, 0, ())])
        while queue:
            column_id, hops, path = queue.popleft()
            if hops >= depth:
                continue
            for target, edge_id in adjacency.get(column_id, ()):
                if target in visited:
                    continue
                visited.add(target)
                next_path = (*path, edge_id)
                if target in existing:
                    # A steward decision stops propagation through this column:
                    # descendants are not reachable only through a skipped claim.
                    continue
                proposals[target] = {
                    "column_id": target,
                    "seed_column_id": seed_id,
                    "seed_classification": seeds[seed_id]["classification"],
                    "edge_ids": list(next_path),
                    "depth": hops + 1,
                }
                queue.append((target, hops + 1, next_path))

    return [proposals[column_id] for column_id in sorted(proposals)]
