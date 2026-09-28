"""MCAR (Missing Completely At Random) loss simulator.

Pack Section 22, mechanism 1.  Status: PROVISIONAL, NOT VALIDATED.

D-09 decision: the CoverageVector seen by the reasoning engine comes from the
CaptureManifest, NOT from this simulator.  This module has no access to
CoverageVector and produces no coverage information.  It only decides which
event IDs survive the random draw.

Hard rules (LOCKED in Pack Section 22):
  - Ground truth is never altered.
  - Loss is reproducible: same event_ids + same level + same seed → same result.
  - Every result records removed IDs, kept IDs, mechanism, level, seed and
    the loss-mask hash.
  - Loss levels: 0, 10, 30, 50, 70, 90  (percent integers).

Rounding rule (D-18, PENDING team decision for the full protocol):
  This implementation uses  int(round(n * level / 100))  which gives Python's
  banker's-rounding "round half to even".  M4 owns D-18; record here if the
  team confirms a different rule before the protocol commit.

IMPORTANT — unresolved zero-arrival seam (see docs/M4_DAY2_MCAR.md):
  After MCAR loss the capture manifest may claim a scope is instrumented but
  zero events survived for that scope.  Whether this should produce a complete
  negative evaluation, POSSIBLE, or something else is NOT YET DECIDED.  This
  module takes no position on that question.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import FrozenSet, List, Sequence, Tuple

MCAR_MECHANISM = "MCAR"
VALID_LEVELS = frozenset({0, 10, 30, 50, 70, 90})


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MCARResult:
    """Output of one MCAR draw.

    kept      – event IDs that survive the loss draw (sorted).
    removed   – event IDs that were eliminated (sorted).
    level_pct – the requested loss percentage (0–100 integer from VALID_LEVELS).
    seed      – the seed used.
    mask_hash – SHA-256 of the canonical removal record; stable for the same
                removed IDs + level + seed.  Used as the loss-mask hash in
                result artifacts.

    The simulator produces ONLY this record.  CoverageVector construction is
    the responsibility of the capture-manifest layer, not this module.
    """

    kept: Tuple[str, ...]
    removed: Tuple[str, ...]
    level_pct: int
    seed: int
    mask_hash: str

    # Convenience checks kept out of __init__ so the type stays a plain value.
    def __post_init__(self) -> None:
        if self.level_pct not in VALID_LEVELS:
            raise ValueError(
                f"level_pct must be one of {sorted(VALID_LEVELS)}, got {self.level_pct}"
            )


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def mcar_loss(
    event_ids: Sequence[str],
    level_pct: int,
    seed: int,
) -> MCARResult:
    """Remove events uniformly at random, independently of event meaning.

    Args:
        event_ids: All eligible event IDs for this run/case.
        level_pct: Percentage of events to remove (must be in VALID_LEVELS).
        seed:      Integer seed.  Same inputs + same seed → same result.

    Returns:
        MCARResult with kept, removed, level_pct, seed, and mask_hash.

    Raises:
        ValueError: if level_pct is not in VALID_LEVELS.
    """
    if level_pct not in VALID_LEVELS:
        raise ValueError(
            f"level_pct must be one of {sorted(VALID_LEVELS)}, got {level_pct}"
        )

    # Canonical sort before any sampling — determinism requires a stable order.
    ids: List[str] = sorted(event_ids)
    n_total = len(ids)
    n_remove = int(round(n_total * level_pct / 100))

    rng = random.Random(seed)
    removed_set: FrozenSet[str] = frozenset(rng.sample(ids, n_remove)) if n_remove > 0 else frozenset()

    removed = tuple(sorted(removed_set))
    kept = tuple(i for i in ids if i not in removed_set)

    mask_hash = _mask_hash(removed, level_pct, seed)
    return MCARResult(kept=kept, removed=removed, level_pct=level_pct, seed=seed, mask_hash=mask_hash)


# ---------------------------------------------------------------------------
# Hash helper
# ---------------------------------------------------------------------------

def _mask_hash(removed: Tuple[str, ...], level_pct: int, seed: int) -> str:
    """Stable SHA-256 of the canonical removal record.

    Canonical form: JSON object with sorted keys, no extra whitespace.
    Same removed IDs + level + seed always gives the same hash.
    """
    record = {"level_pct": level_pct, "removed": list(removed), "seed": seed}
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
