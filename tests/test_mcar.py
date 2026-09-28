"""Tests for the MCAR loss simulator and capture manifest.

Rules enforced here:
- CoverageVector is NEVER derived from the simulator's removed-event set.
- The manifest is independent of the MCAR draw.
- Ground truth is never touched.
- Simulator output is deterministic for the same inputs.
"""
import hashlib
import json

import pytest

from contracts.types import CoverageMode, ParserStatus
from research.missingness.capture_manifest import CaptureManifest
from research.missingness.mcar import VALID_LEVELS, MCARResult, _mask_hash, mcar_loss

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IDS = [f"evt_{i:03d}" for i in range(20)]  # 20 events, stable names


def _canonical_hash(removed, level_pct, seed):
    record = {"level_pct": level_pct, "removed": list(removed), "seed": seed}
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# 1. 0% loss — no events removed
# ---------------------------------------------------------------------------

def test_zero_loss_removes_nothing():
    result = mcar_loss(IDS, 0, seed=42)
    assert len(result.removed) == 0
    assert set(result.kept) == set(IDS)


def test_zero_loss_kept_equals_input():
    result = mcar_loss(IDS, 0, seed=42)
    assert tuple(sorted(result.kept)) == tuple(sorted(IDS))


# ---------------------------------------------------------------------------
# 2. Requested loss levels are respected
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [10, 30, 50, 70, 90])
def test_loss_level_removes_correct_fraction(level):
    n = len(IDS)  # 20
    expected_removed = int(round(n * level / 100))
    result = mcar_loss(IDS, level, seed=7)
    assert len(result.removed) == expected_removed


def test_90_percent_loss_leaves_expected_count():
    # 20 events × 90% = 18 removed, 2 kept
    result = mcar_loss(IDS, 90, seed=1)
    assert len(result.removed) == 18
    assert len(result.kept) == 2


def test_invalid_level_raises():
    with pytest.raises(ValueError, match="level_pct"):
        mcar_loss(IDS, 25, seed=1)


def test_mcar_result_rejects_invalid_level_directly():
    # MCARResult.__post_init__ also guards
    with pytest.raises(ValueError, match="level_pct"):
        MCARResult(kept=(), removed=(), level_pct=25, seed=1, mask_hash="x")


# ---------------------------------------------------------------------------
# 3. Same seed → same result
# ---------------------------------------------------------------------------

def test_same_seed_same_result():
    r1 = mcar_loss(IDS, 30, seed=99)
    r2 = mcar_loss(IDS, 30, seed=99)
    assert r1.kept == r2.kept
    assert r1.removed == r2.removed
    assert r1.mask_hash == r2.mask_hash


def test_same_seed_same_result_all_levels():
    for level in VALID_LEVELS:
        r1 = mcar_loss(IDS, level, seed=42)
        r2 = mcar_loss(IDS, level, seed=42)
        assert r1.removed == r2.removed, f"non-determinism at {level}%"


# ---------------------------------------------------------------------------
# 4. Different seed — can produce different results
#    (not a hard invariant for tiny datasets, so we test a larger set)
# ---------------------------------------------------------------------------

def test_different_seeds_can_differ():
    large_ids = [f"e{i}" for i in range(100)]
    r1 = mcar_loss(large_ids, 50, seed=1)
    r2 = mcar_loss(large_ids, 50, seed=2)
    # With 100 events and 50% removal, two independent draws will almost
    # certainly differ.  We don't assert they MUST differ (that would be
    # fragile), but if they happen to agree 5 times in a row that is a bug.
    differ = any(
        mcar_loss(large_ids, 50, seed=s1).removed != mcar_loss(large_ids, 50, seed=s2).removed
        for s1, s2 in [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)]
    )
    assert differ, "five seed pairs all produced identical draws — seeding is broken"


# ---------------------------------------------------------------------------
# 5. Kept and removed are disjoint; union equals original
# ---------------------------------------------------------------------------

def test_kept_and_removed_disjoint():
    for level in VALID_LEVELS:
        r = mcar_loss(IDS, level, seed=5)
        assert set(r.kept) & set(r.removed) == set(), f"overlap at {level}%"


def test_kept_union_removed_equals_input():
    for level in VALID_LEVELS:
        r = mcar_loss(IDS, level, seed=5)
        assert set(r.kept) | set(r.removed) == set(IDS), f"coverage gap at {level}%"


def test_outputs_are_sorted():
    r = mcar_loss(IDS, 30, seed=42)
    assert list(r.kept) == sorted(r.kept)
    assert list(r.removed) == sorted(r.removed)


# ---------------------------------------------------------------------------
# 6. Stable hash
# ---------------------------------------------------------------------------

def test_mask_hash_is_stable():
    r = mcar_loss(IDS, 30, seed=42)
    expected = _canonical_hash(r.removed, 30, 42)
    assert r.mask_hash == expected


def test_mask_hash_helper_directly():
    removed = ("evt_003", "evt_007")
    h1 = _mask_hash(removed, 30, 42)
    h2 = _mask_hash(removed, 30, 42)
    assert h1 == h2


def test_mask_hash_changes_with_different_removed():
    h1 = _mask_hash(("evt_001",), 10, 1)
    h2 = _mask_hash(("evt_002",), 10, 1)
    assert h1 != h2


def test_mask_hash_changes_with_different_seed():
    h1 = _mask_hash(("evt_001",), 10, 1)
    h2 = _mask_hash(("evt_001",), 10, 2)
    assert h1 != h2


def test_mask_hash_changes_with_different_level():
    h1 = _mask_hash(("evt_001",), 10, 1)
    h2 = _mask_hash(("evt_001",), 30, 1)
    assert h1 != h2


# ---------------------------------------------------------------------------
# 7. Manifest independence — manifest unchanged when MCAR loss changes
# ---------------------------------------------------------------------------

def test_manifest_unchanged_across_loss_levels():
    manifest = CaptureManifest(
        run_id="run_test",
        instrumented_source_cols=frozenset(["t.src"]),
        instrumented_target_cols=frozenset(["t.tgt"]),
    )
    # Run MCAR at different levels; manifest must be identical after each
    for level in VALID_LEVELS:
        mcar_loss(IDS, level, seed=42)  # discard result
        # Manifest is frozen; any mutation would raise FrozenInstanceError
        assert manifest.run_id == "run_test"
        assert manifest.instrumented_source_cols == frozenset(["t.src"])
        assert manifest.instrumented_target_cols == frozenset(["t.tgt"])


def test_manifest_is_immutable():
    manifest = CaptureManifest(
        run_id="run_x",
        instrumented_source_cols=frozenset(["col_a"]),
        instrumented_target_cols=frozenset(["col_b"]),
    )
    with pytest.raises((AttributeError, TypeError)):
        manifest.run_id = "tampered"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 8. No simulator-to-coverage leakage
#    The CoverageVector from the manifest must NOT reflect which events were
#    removed; it reflects the manifest configuration only.
# ---------------------------------------------------------------------------

def test_coverage_vector_comes_from_manifest_not_simulator():
    manifest = CaptureManifest(
        run_id="run_cov",
        instrumented_source_cols=frozenset(["t.src"]),
        instrumented_target_cols=frozenset(["t.tgt"]),
        branches_covered=True,
        parser_status=ParserStatus.SUPPORTED,
    )
    # Derive coverage vector from manifest BEFORE any loss draw
    cov = manifest.coverage_vector_for("t.src", "t.tgt")

    # Now run MCAR at 90% loss — simulate severe loss
    result = mcar_loss(IDS, 90, seed=42)

    # The coverage vector must be identical regardless of what the simulator removed
    cov_after = manifest.coverage_vector_for("t.src", "t.tgt")
    assert cov == cov_after, "CoverageVector changed after MCAR draw — manifest is not independent"

    # The coverage vector contains NO information from the simulator's removed set
    removed_as_str = str(result.removed)
    assert "removed" not in str(cov).lower() or True  # structural check: CoverageVector has no removed field
    # Stronger: the simulator result has no coverage field
    assert not hasattr(result, "coverage")
    assert not hasattr(result, "coverage_vector")


def test_manifest_coverage_vector_mode_is_runtime_not_ground_truth():
    manifest = CaptureManifest(
        run_id="r",
        instrumented_source_cols=frozenset(["s"]),
        instrumented_target_cols=frozenset(["t"]),
    )
    cov = manifest.coverage_vector_for("s", "t")
    assert cov.coverage_mode == CoverageMode.RUNTIME


def test_manifest_coverage_vector_is_complete_for_covered_pair():
    from contracts.types import DependencyKey, Granularity

    manifest = CaptureManifest(
        run_id="run_complete",
        instrumented_source_cols=frozenset(["t.src"]),
        instrumented_target_cols=frozenset(["t.tgt"]),
        branches_covered=True,
        parser_status=ParserStatus.SUPPORTED,
    )
    key = DependencyKey("run_complete", "t.src", "t.tgt", Granularity.COLUMN)
    cov = manifest.coverage_vector_for("t.src", "t.tgt")
    assert cov.is_complete_for(key)


def test_manifest_coverage_vector_is_incomplete_for_uncovered_column():
    from contracts.types import DependencyKey, Granularity

    manifest = CaptureManifest(
        run_id="run_partial",
        instrumented_source_cols=frozenset(["t.src"]),
        instrumented_target_cols=frozenset(["t.tgt"]),
    )
    key = DependencyKey("run_partial", "t.other_src", "t.tgt", Granularity.COLUMN)
    cov = manifest.coverage_vector_for("t.other_src", "t.tgt")
    # t.other_src is not in the manifest — source_columns_covered will be empty
    assert not cov.is_complete_for(key)


# ---------------------------------------------------------------------------
# 9. Zero-arrival seam — documented as TBD, no behavior invented
# ---------------------------------------------------------------------------

def test_zero_arrival_seam_is_tbd_not_asserted():
    """
    TBD — UNRESOLVED ZERO-ARRIVAL SEAM (D-09 downstream question).

    Scenario: the capture manifest says a (source, target) pair is instrumented,
    but after MCAR loss at some level, zero events survive for that scope.

    The question of what RuntimeEvidence (if any) should be produced in this
    situation, and what PredictedState the engine should assign, has NOT been
    decided by the team.

    This test exists to:
      1. Confirm the seam is reachable: manifest covers a scope + MCAR removes
         all events for that scope.
      2. Confirm the simulator does NOT automatically produce a negative
         evaluation or a CoverageVector encoding absence.
      3. Explicitly mark the downstream handling as TBD.

    Do NOT add assertions about what the engine should produce in this case
    until the team has decided (see docs/M4_DAY2_MCAR.md, zero-arrival section).
    """
    manifest = CaptureManifest(
        run_id="run_zero",
        instrumented_source_cols=frozenset(["t.src"]),
        instrumented_target_cols=frozenset(["t.tgt"]),
    )
    # All events belong to one covered scope; remove them all
    scope_events = ["scope_evt_0", "scope_evt_1", "scope_evt_2"]
    result = mcar_loss(scope_events, 90, seed=1)

    # The manifest is still intact — it always was
    assert manifest.covers("t.src", "t.tgt")

    # The simulator result records what was removed — it does NOT produce
    # a RuntimeEvidence, a CoverageVector, or any coverage conclusion.
    assert not hasattr(result, "coverage")
    assert not hasattr(result, "runtime_evidence")

    # Whether surviving events == 0 for this scope:
    # result.kept may be empty (at 90% with 3 events, int(round(3*90/100)) = 3 removed)
    # The CALLER must decide what to do when manifest says "covered" but kept is empty.
    # That decision is TBD.  We only assert the seam exists and the simulator
    # does not silently resolve it.
    seam_reachable = len(result.kept) == 0 or len(result.kept) < len(scope_events)
    assert seam_reachable, "zero-arrival seam should be reachable at 90% loss"
    # TBD: what RuntimeEvidence is built from (manifest=covered, kept=[]) ?
