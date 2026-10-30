"""Reverse-isolation regression test (M4 workstream Task 3).

The forward direction is tested in test_leakage.py:
  - The engine refuses ground-truth objects at runtime (LeakageError)
  - Reasoning/baseline modules do not import contracts.truth or research.ground_truth

This test closes the reverse gap:
  - Ground-truth modules must not import prediction/reasoning/baseline modules

A confirmed semantic gap: the original test suite checked only that predictors
cannot see ground truth. It did not check that ground-truth providers cannot
reach back into prediction code, which would create a circular dependency and
risk leaking prediction logic into truth construction.

Boundary enforced by scripts/check_import_boundaries.py RULES entry:
  ("research/ground_truth/", ["ingestion", "sqlglot",
   "research.reasoning", "research.baselines"])

This test mirrors that AST check at the file level so a violation is caught
even if the boundary script is not run.
"""
from pathlib import Path

# Modules that ground_truth must NEVER import — reverse isolation
FORBIDDEN_IMPORTS = {
    "sqlglot",
    "ingestion",
    "research.reasoning",
    "research.baselines",
    "backend",
    "frontend",
}


def test_ground_truth_does_not_import_prediction_modules():
    """Ground-truth code must not import prediction, ingestion, or product modules.

    This is the reverse side of the leakage boundary: if a ground-truth provider
    imports reasoning or baseline code, it can construct 'truth' from prediction
    logic, making the evaluation circular and invalid.
    """
    ground_truth_dir = Path("research/ground_truth")
    assert ground_truth_dir.exists(), "research/ground_truth/ directory must exist"

    violations = []
    for path in ground_truth_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IMPORTS:
            # Check both import styles
            if f"import {forbidden}" in source:
                violations.append(f"{path.name}: found 'import {forbidden}'")
            if f"from {forbidden}" in source:
                violations.append(f"{path.name}: found 'from {forbidden}'")

    assert not violations, (
        "Ground-truth modules must not import prediction/ingestion/product modules. "
        f"Violations: {violations}"
    )


def test_ground_truth_does_not_define_truth_labels_as_predictions():
    """Ground-truth TruthLabel values must not collide with PredictedState values.

    If truth labels (PROPAGATED, NOT_PROPAGATED) ever appear as prediction states,
    the leakage scanner would catch them at runtime, but a structural check here
    prevents the confusion from being introduced in the first place.
    """
    from contracts.types import PredictedState
    from contracts.truth import TruthLabel

    prediction_values = {s.value for s in PredictedState}
    truth_values = {t.value for t in TruthLabel}

    overlap = prediction_values & truth_values
    assert not overlap, (
        f"PredictedState and TruthLabel share values: {overlap}. "
        "These sets must be disjoint to prevent semantic confusion."
    )
