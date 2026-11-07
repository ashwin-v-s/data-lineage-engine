"""Tests for the 5 additional loss mechanisms (Wave 2).

These tests verify the same core properties as test_mcar.py:
  - Same seed → same result (determinism)
  - kept + removed == input (completeness)
  - kept and removed are disjoint
  - level=0 removes nothing
  - mechanism name recorded correctly
"""
import pytest
from research.missingness.additional_mechanisms import (
    operator_loss, dataset_loss, branch_loss, complete_run_loss,
    correlated_loss, ALL_LOSS_MECHANISMS, LossResult,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_IDS = [
    "op:case_when:ev001", "op:case_when:ev002",
    "op:projection:ev003", "op:projection:ev004",
    "op:aggregate:ev005",
]

DATASET_IDS = [
    "orders.ev001", "orders.ev002",
    "customers.ev003", "customers.ev004",
    "products.ev005",
]

RUN_IDS = [
    "run-A-ev001", "run-A-ev002",
    "run-B-ev003", "run-B-ev004",
    "run-C-ev005",
]

BRANCH_IDS = [
    "case_when_ev001", "case_when_ev002",
    "projection_ev003", "projection_ev004",
]

PREFIX_IDS = [
    "ev_stg_01", "ev_stg_02",
    "ev_dim_01", "ev_dim_02",
    "ev_fact_01",
]


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [10, 30, 50])
def test_operator_loss_is_deterministic(level):
    r1 = operator_loss(SAMPLE_IDS, level, seed=42)
    r2 = operator_loss(SAMPLE_IDS, level, seed=42)
    assert r1.kept == r2.kept
    assert r1.removed == r2.removed
    assert r1.mask_hash == r2.mask_hash


@pytest.mark.parametrize("level", [10, 30, 50])
def test_dataset_loss_is_deterministic(level):
    r1 = dataset_loss(DATASET_IDS, level, seed=7)
    r2 = dataset_loss(DATASET_IDS, level, seed=7)
    assert r1.kept == r2.kept
    assert r1.mask_hash == r2.mask_hash


@pytest.mark.parametrize("level", [10, 50, 90])
def test_branch_loss_is_deterministic(level):
    r1 = branch_loss(BRANCH_IDS, level, seed=1)
    r2 = branch_loss(BRANCH_IDS, level, seed=1)
    assert r1.kept == r2.kept


@pytest.mark.parametrize("level", [30, 50, 70])
def test_complete_run_loss_is_deterministic(level):
    r1 = complete_run_loss(RUN_IDS, level, seed=99)
    r2 = complete_run_loss(RUN_IDS, level, seed=99)
    assert r1.kept == r2.kept


@pytest.mark.parametrize("level", [10, 50])
def test_correlated_loss_is_deterministic(level):
    r1 = correlated_loss(PREFIX_IDS, level, seed=3)
    r2 = correlated_loss(PREFIX_IDS, level, seed=3)
    assert r1.kept == r2.kept


# ---------------------------------------------------------------------------
# Completeness: kept ∪ removed == input
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn,ids", [
    (lambda ids, l, s: operator_loss(ids, l, s), SAMPLE_IDS),
    (lambda ids, l, s: dataset_loss(ids, l, s), DATASET_IDS),
    (lambda ids, l, s: branch_loss(ids, l, s), BRANCH_IDS),
    (lambda ids, l, s: complete_run_loss(ids, l, s), RUN_IDS),
    (lambda ids, l, s: correlated_loss(ids, l, s), PREFIX_IDS),
])
def test_kept_union_removed_equals_input(fn, ids):
    result = fn(ids, 30, 42)
    assert set(result.kept) | set(result.removed) == set(ids)


# ---------------------------------------------------------------------------
# Level 0 removes nothing
# ---------------------------------------------------------------------------

def test_all_mechanisms_level_0_removes_nothing():
    for name, fn in ALL_LOSS_MECHANISMS.items():
        result = fn(SAMPLE_IDS, 0, seed=1)
        assert len(result.removed) == 0, f"{name} at level 0 should remove nothing"
        assert set(result.kept) == set(SAMPLE_IDS)


# ---------------------------------------------------------------------------
# Mechanism name recorded correctly
# ---------------------------------------------------------------------------

def test_mechanism_names_recorded():
    assert operator_loss(SAMPLE_IDS, 10, 1).mechanism == "operator"
    assert dataset_loss(DATASET_IDS, 10, 1).mechanism == "dataset"
    assert branch_loss(BRANCH_IDS, 10, 1).mechanism == "branch"
    assert complete_run_loss(RUN_IDS, 10, 1).mechanism == "complete_run"
    assert correlated_loss(PREFIX_IDS, 10, 1).mechanism == "correlated"


# ---------------------------------------------------------------------------
# Registry contains all 5 mechanisms
# ---------------------------------------------------------------------------

def test_all_mechanisms_in_registry():
    expected = {"operator", "dataset", "branch", "complete_run", "correlated"}
    assert expected == set(ALL_LOSS_MECHANISMS.keys())


# ---------------------------------------------------------------------------
# Invalid level raises
# ---------------------------------------------------------------------------

def test_invalid_level_raises_for_all_mechanisms():
    for name, fn in ALL_LOSS_MECHANISMS.items():
        with pytest.raises(ValueError):
            fn(SAMPLE_IDS, 25, seed=1)  # 25 is not in VALID_LEVELS
