"""Additional loss mechanisms beyond MCAR.

Pack Section 22, mechanisms 2–6.  Status: PROVISIONAL, NOT VALIDATED.

D-09 decision (same as mcar.py): CoverageVector comes from the CaptureManifest,
NOT from any simulator.  These simulators only decide which event IDs survive.

Loss mechanisms implemented here:
  - OPERATOR:     Remove all events for a chosen operator type.
  - DATASET:      Remove all events touching a chosen source or target dataset.
  - BRANCH:       Remove events from conditional-branch constructs (CASE_WHEN).
  - COMPLETE_RUN: Remove ALL events for a chosen run_id.
  - CORRELATED:   Remove events whose IDs share a common prefix (simulates
                  correlated failure — same service/component drops together).

Each function follows the same interface as mcar_loss:
  - Input: event_ids, level_pct (controls HOW MANY items are affected), seed
  - Output: LossResult (kept, removed, level_pct, seed, mask_hash, mechanism)
  - Same inputs + same seed → same result (deterministic)
  - Never alters ground truth
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

from research.missingness.mcar import VALID_LEVELS, _mask_hash


# ---------------------------------------------------------------------------
# Generic result type shared by all mechanisms
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LossResult:
    """Output of any loss simulator.

    Extends MCARResult with a mechanism field so artifacts can record which
    simulator was used.
    """
    kept: Tuple[str, ...]
    removed: Tuple[str, ...]
    level_pct: int
    seed: int
    mask_hash: str
    mechanism: str

    def __post_init__(self) -> None:
        if self.level_pct not in VALID_LEVELS:
            raise ValueError(
                f"level_pct must be one of {sorted(VALID_LEVELS)}, got {self.level_pct}"
            )


def _make_result(
    all_ids: Sequence[str],
    removed_set: FrozenSet[str],
    level_pct: int,
    seed: int,
    mechanism: str,
) -> LossResult:
    """Build a LossResult from a set of removed IDs."""
    removed = tuple(sorted(removed_set))
    kept = tuple(i for i in sorted(all_ids) if i not in removed_set)
    mh = _mask_hash(removed, level_pct, seed)
    return LossResult(
        kept=kept,
        removed=removed,
        level_pct=level_pct,
        seed=seed,
        mask_hash=mh,
        mechanism=mechanism,
    )


# ---------------------------------------------------------------------------
# 2. OPERATOR loss — remove all events for a sampled operator type
# ---------------------------------------------------------------------------

def operator_loss(
    event_ids: Sequence[str],
    level_pct: int,
    seed: int,
    operator_extractor: Optional[Callable[[str], str]] = None,
) -> LossResult:
    """Remove events belonging to operator types sampled at `level_pct` rate.

    `operator_extractor(event_id)` returns the operator tag for an event ID.
    If not supplied, the mechanism uses a simple prefix split on ':' (e.g.
    "op:case_when:ev001" → operator tag "op:case_when").

    At level_pct=50, roughly half the distinct operator types are dropped.
    All events for a dropped operator type are removed together (correlated
    within an operator, MCAR across operators).
    """
    if level_pct not in VALID_LEVELS:
        raise ValueError(f"level_pct must be one of {sorted(VALID_LEVELS)}, got {level_pct}")

    ids = sorted(event_ids)

    def _default_extractor(eid: str) -> str:
        parts = eid.split(":")
        return ":".join(parts[:2]) if len(parts) >= 2 else eid

    extract = operator_extractor or _default_extractor

    # Group events by operator
    by_operator: Dict[str, List[str]] = {}
    for eid in ids:
        op = extract(eid)
        by_operator.setdefault(op, []).append(eid)

    operators = sorted(by_operator.keys())
    n_drop = int(round(len(operators) * level_pct / 100))

    rng = random.Random(seed)
    dropped_ops = frozenset(rng.sample(operators, n_drop)) if n_drop > 0 else frozenset()

    removed_set: FrozenSet[str] = frozenset(
        eid for op, eids in by_operator.items() if op in dropped_ops for eid in eids
    )
    return _make_result(ids, removed_set, level_pct, seed, "operator")


# ---------------------------------------------------------------------------
# 3. DATASET loss — remove all events touching a sampled dataset
# ---------------------------------------------------------------------------

def dataset_loss(
    event_ids: Sequence[str],
    level_pct: int,
    seed: int,
    dataset_extractor: Optional[Callable[[str], str]] = None,
) -> LossResult:
    """Remove events associated with datasets sampled at `level_pct` rate.

    `dataset_extractor(event_id)` returns the dataset name for an event ID.
    Default: split on '.' and take the first part (e.g. "orders.ev01" → "orders").

    At level_pct=30, roughly 30% of distinct datasets are dropped.
    All events for a dropped dataset are removed together.
    """
    if level_pct not in VALID_LEVELS:
        raise ValueError(f"level_pct must be one of {sorted(VALID_LEVELS)}, got {level_pct}")

    ids = sorted(event_ids)

    def _default_extractor(eid: str) -> str:
        return eid.split(".")[0]

    extract = dataset_extractor or _default_extractor

    by_dataset: Dict[str, List[str]] = {}
    for eid in ids:
        ds = extract(eid)
        by_dataset.setdefault(ds, []).append(eid)

    datasets = sorted(by_dataset.keys())
    n_drop = int(round(len(datasets) * level_pct / 100))

    rng = random.Random(seed)
    dropped = frozenset(rng.sample(datasets, n_drop)) if n_drop > 0 else frozenset()

    removed_set: FrozenSet[str] = frozenset(
        eid for ds, eids in by_dataset.items() if ds in dropped for eid in eids
    )
    return _make_result(ids, removed_set, level_pct, seed, "dataset")


# ---------------------------------------------------------------------------
# 4. BRANCH loss — remove events from conditional-branch constructs
# ---------------------------------------------------------------------------

def branch_loss(
    event_ids: Sequence[str],
    level_pct: int,
    seed: int,
    branch_tag: str = "case_when",
) -> LossResult:
    """Remove events tagged as conditional-branch constructs at `level_pct` rate.

    Events matching `branch_tag` in their ID are candidates for removal.
    `level_pct` controls what fraction of matching events are removed (MCAR
    within the matching set).

    This simulates capture gaps specific to conditional logic — a common
    weak point in static SQL lineage tools.
    """
    if level_pct not in VALID_LEVELS:
        raise ValueError(f"level_pct must be one of {sorted(VALID_LEVELS)}, got {level_pct}")

    ids = sorted(event_ids)
    branch_ids = [eid for eid in ids if branch_tag.lower() in eid.lower()]
    non_branch_ids = [eid for eid in ids if branch_tag.lower() not in eid.lower()]

    n_remove = int(round(len(branch_ids) * level_pct / 100))
    rng = random.Random(seed)
    removed_set: FrozenSet[str] = (
        frozenset(rng.sample(branch_ids, n_remove)) if n_remove > 0 else frozenset()
    )
    return _make_result(ids, removed_set, level_pct, seed, "branch")


# ---------------------------------------------------------------------------
# 5. COMPLETE_RUN loss — remove ALL events for a sampled run
# ---------------------------------------------------------------------------

def complete_run_loss(
    event_ids: Sequence[str],
    level_pct: int,
    seed: int,
    run_extractor: Optional[Callable[[str], str]] = None,
) -> LossResult:
    """Remove all events for runs sampled at `level_pct` rate.

    `run_extractor(event_id)` returns the run_id for an event.
    Default: split on '-' and take the first two parts (e.g. "run-A-ev01" → "run-A").

    This simulates complete capture failure for a subset of runs —
    the entire pipeline log for a run goes missing.
    """
    if level_pct not in VALID_LEVELS:
        raise ValueError(f"level_pct must be one of {sorted(VALID_LEVELS)}, got {level_pct}")

    ids = sorted(event_ids)

    def _default_extractor(eid: str) -> str:
        parts = eid.split("-")
        return "-".join(parts[:2]) if len(parts) >= 2 else eid

    extract = run_extractor or _default_extractor

    by_run: Dict[str, List[str]] = {}
    for eid in ids:
        run = extract(eid)
        by_run.setdefault(run, []).append(eid)

    runs = sorted(by_run.keys())
    n_drop = int(round(len(runs) * level_pct / 100))

    rng = random.Random(seed)
    dropped = frozenset(rng.sample(runs, n_drop)) if n_drop > 0 else frozenset()

    removed_set: FrozenSet[str] = frozenset(
        eid for run, eids in by_run.items() if run in dropped for eid in eids
    )
    return _make_result(ids, removed_set, level_pct, seed, "complete_run")


# ---------------------------------------------------------------------------
# 6. CORRELATED loss — remove events sharing a common prefix
# ---------------------------------------------------------------------------

def correlated_loss(
    event_ids: Sequence[str],
    level_pct: int,
    seed: int,
    prefix_length: int = 4,
) -> LossResult:
    """Remove events whose IDs share a common prefix (correlated failure).

    This simulates a service/component failure that drops all events from
    the same source component at once (e.g. all events from "ev_s" prefix).

    `prefix_length`: number of characters used as the correlation key.
    At level_pct=30, roughly 30% of distinct prefixes are dropped.
    All events sharing a dropped prefix are removed together.
    """
    if level_pct not in VALID_LEVELS:
        raise ValueError(f"level_pct must be one of {sorted(VALID_LEVELS)}, got {level_pct}")

    ids = sorted(event_ids)

    by_prefix: Dict[str, List[str]] = {}
    for eid in ids:
        prefix = eid[:prefix_length]
        by_prefix.setdefault(prefix, []).append(eid)

    prefixes = sorted(by_prefix.keys())
    n_drop = int(round(len(prefixes) * level_pct / 100))

    rng = random.Random(seed)
    dropped = frozenset(rng.sample(prefixes, n_drop)) if n_drop > 0 else frozenset()

    removed_set: FrozenSet[str] = frozenset(
        eid for prefix, eids in by_prefix.items() if prefix in dropped for eid in eids
    )
    return _make_result(ids, removed_set, level_pct, seed, "correlated")


# ---------------------------------------------------------------------------
# Registry — all mechanisms by name
# ---------------------------------------------------------------------------

ALL_LOSS_MECHANISMS: Dict[str, Callable] = {
    "operator": operator_loss,
    "dataset": dataset_loss,
    "branch": branch_loss,
    "complete_run": complete_run_loss,
    "correlated": correlated_loss,
}
