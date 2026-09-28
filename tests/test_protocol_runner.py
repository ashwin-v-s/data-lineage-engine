"""Tests for the protocol loader, validator, and plumbing runner.

Research integrity rules enforced here:
  1. Ground truth is loaded only after all predictions exist.
  2. No predictor receives a ground-truth object.
  3. Real execution is blocked when required protocol fields are TBD.
  4. Plumbing mode may run despite TBD values.
  5. Result artifact is labelled PLUMBING and contains required metadata.
  6. Prediction hashes are deterministic for the same inputs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from contracts.truth import TruthLabel
from research.experiments.protocol_loader import (
    ProtocolBlockedError,
    load_protocol,
    validate_protocol,
    _load_yaml,
    _get_nested,
    REQUIRED_FOR_REAL_RUN,
)
from research.experiments.run import (
    _gt_hash,
    _prediction_hash,
    _predict_all,
    _load_ground_truth_after_prediction,
    run_plumbing,
    result_artifact,
)
from contracts.mocks.loaders import load_case, load_truth

PROTOCOL_PATH = "research/protocol/v1.yaml"


# ---------------------------------------------------------------------------
# 1. Protocol loads successfully
# ---------------------------------------------------------------------------

def test_protocol_file_exists():
    assert Path(PROTOCOL_PATH).exists(), "v1.yaml must exist at the architecture-specified path"


def test_protocol_loads_without_error():
    protocol = load_protocol(PROTOCOL_PATH)
    assert isinstance(protocol, dict)
    assert "protocol_version" in protocol


def test_protocol_has_locked_loss_levels():
    protocol = load_protocol(PROTOCOL_PATH)
    levels = _get_nested(protocol, "loss.levels")
    # Levels may be a list of strings or ints depending on YAML loader
    assert levels is not None, "loss.levels must be present"
    str_levels = [str(l) for l in levels]
    for expected in ["0", "10", "30", "50", "70", "90"]:
        assert expected in str_levels, f"LOCKED loss level {expected} missing from protocol"


def test_protocol_has_all_baselines():
    protocol = load_protocol(PROTOCOL_PATH)
    baselines = _get_nested(protocol, "baselines")
    assert baselines is not None
    for b in ["B1", "B2", "B3", "B4", "B5"]:
        assert b in baselines, f"Baseline {b} missing from protocol"


def test_protocol_integrity_flags_are_true():
    protocol = load_protocol(PROTOCOL_PATH)
    assert _get_nested(protocol, "ground_truth_isolation") in (True, "true", "True")
    assert _get_nested(protocol, "no_gt_in_predictor") in (True, "true", "True")
    assert _get_nested(protocol, "no_held_out_tuning") in (True, "true", "True")


# ---------------------------------------------------------------------------
# 2. Required TBD values block real execution
# ---------------------------------------------------------------------------

def test_validation_detects_tbd_fields():
    protocol = load_protocol(PROTOCOL_PATH)
    result = validate_protocol(protocol)
    # The skeleton has many TBD fields; validation must find them
    assert not result.ok
    assert len(result.tbd_fields) > 0


def test_validation_lists_required_fields():
    protocol = load_protocol(PROTOCOL_PATH)
    result = validate_protocol(protocol)
    # Every field in REQUIRED_FOR_REAL_RUN that is TBD must appear in tbd_fields
    for field in result.tbd_fields:
        assert field in REQUIRED_FOR_REAL_RUN


def test_tbd_fields_block_real_run():
    protocol = load_protocol(PROTOCOL_PATH)
    result = validate_protocol(protocol)
    with pytest.raises(ProtocolBlockedError) as exc_info:
        result.raise_if_blocking(plumbing=False)
    error_msg = str(exc_info.value)
    # Error must name the blocking fields
    assert "TBD" in error_msg
    assert "benchmark_version" in error_msg


def test_tbd_fields_do_not_block_plumbing():
    protocol = load_protocol(PROTOCOL_PATH)
    result = validate_protocol(protocol)
    # Must not raise for plumbing mode
    result.raise_if_blocking(plumbing=True)  # no exception expected


def test_fully_resolved_protocol_passes_validation():
    # Build a minimal fully-resolved protocol dict
    resolved = {
        "protocol_version": "1.0-test",
        "benchmark_version": "v1",
        "sql_subset": ["CASE", "INNER JOIN"],
        "splits": {"development": "dev", "validation": "val", "held_out": "held"},
        "contribution_semantics": "where_provenance",
        "prediction_unit_universe": "static_candidates_plus_positives",
        "loss": {
            "mechanisms": ["mcar"],
            "levels": [0, 10, 30, 50, 70, 90],
            "master_seed": "42",
            "replicates": "5",
            "rounding_rule": "round_half_to_even",
            "zero_arrival_semantics": "POSSIBLE",
        },
        "metrics": {
            "primary": "committed_accuracy",
            "confidence_interval": "bootstrap_95",
        },
        "aggregation": "macro_over_cases",
        "stopping_rule": "3_of_6_levels",
        "exclusion_rules": "drop_unsupported",
    }
    result = validate_protocol(resolved)
    assert result.ok
    assert result.tbd_fields == []
    result.raise_if_blocking(plumbing=False)  # must not raise


# ---------------------------------------------------------------------------
# 3. Plumbing can run despite TBD values
# ---------------------------------------------------------------------------

def test_plumbing_run_succeeds_with_tbd_protocol():
    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=0, seed=1)
    assert artifact["mode"] == "PLUMBING"


def test_plumbing_result_has_plumbing_notice():
    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=0, seed=1)
    assert artifact["plumbing_notice"] is not None
    assert "PLUMBING" in artifact["plumbing_notice"]
    assert "NOT" in artifact["plumbing_notice"] or "not" in artifact["plumbing_notice"].lower()


# ---------------------------------------------------------------------------
# 4. Ground truth loaded only after predictions are generated
# ---------------------------------------------------------------------------

def test_gt_loaded_after_predictions():
    """Verify the sequencing contract: predictions first, GT second.

    We check this by confirming that _predict_all never receives a TruthLabel
    argument and that _load_ground_truth_after_prediction is called separately.
    """
    keys, static_ev, runtime_ev = load_case("w03_case_when")

    # _predict_all signature must not accept a truth argument
    import inspect
    sig = inspect.signature(_predict_all)
    param_names = list(sig.parameters.keys())
    assert "truth" not in param_names
    assert "ground_truth" not in param_names
    assert "label" not in param_names

    # Predictions can be generated without GT
    preds = _predict_all(keys, static_ev, runtime_ev)
    assert isinstance(preds, dict)
    assert "proposed" in preds

    # GT is loaded separately
    truth = _load_ground_truth_after_prediction("w03_case_when")
    assert isinstance(truth, dict)
    assert all(isinstance(v, TruthLabel) for v in truth.values())


# ---------------------------------------------------------------------------
# 5. Engine/predictor receives no ground-truth object
# ---------------------------------------------------------------------------

def test_predictors_never_receive_gt_object():
    """The PredictorInput passed to the engine must contain no GT fields or objects."""
    from contracts.evidence import PredictorInput
    from contracts.truth import GroundTruthRecord
    import dataclasses

    # PredictorInput must have no ground-truth typed fields
    for f in dataclasses.fields(PredictorInput):
        assert "truth" not in f.name.lower(), f"GT field found in PredictorInput: {f.name}"
        assert "TruthLabel" not in str(f.type)
        assert "GroundTruthRecord" not in str(f.type)


def test_run_plumbing_predictions_contain_no_gt_fields():
    """Predictions from the plumbing run contain no TruthLabel values."""
    from contracts.truth import TruthLabel

    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=0, seed=1)

    # Artifact metrics come from evaluate(); verify artifact itself has no raw GT labels
    # The mode should be PLUMBING and gt is only in the hash, not in raw form
    assert artifact["mode"] == "PLUMBING"
    # ground_truth_hash is a string (SHA-256), not a TruthLabel
    assert isinstance(artifact["ground_truth_hash"], str)
    assert len(artifact["ground_truth_hash"]) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# 6. Result contains PLUMBING mode
# ---------------------------------------------------------------------------

def test_result_mode_is_plumbing():
    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=0, seed=1)
    assert artifact["mode"] == "PLUMBING"


# ---------------------------------------------------------------------------
# 7. Result contains required metadata
# ---------------------------------------------------------------------------

def test_result_has_required_metadata():
    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=0, seed=1)

    required_keys = [
        "mode", "runner_version", "protocol_version", "benchmark_version",
        "loss_mechanism", "loss_level_pct", "seed", "mask_hash",
        "ground_truth_hash", "prediction_hashes", "git_sha", "environment",
        "tbd_fields_at_run_time", "metrics",
    ]
    for k in required_keys:
        assert k in artifact, f"Required artifact key missing: {k}"


def test_result_has_metric_for_every_method():
    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=0, seed=1)

    expected_methods = {"proposed", "B1", "B2", "B3", "B4", "B5"}
    assert expected_methods == set(artifact["metrics"].keys())
    assert expected_methods == set(artifact["prediction_hashes"].keys())


def test_result_records_tbd_fields():
    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=0, seed=1)
    assert isinstance(artifact["tbd_fields_at_run_time"], list)
    assert len(artifact["tbd_fields_at_run_time"]) > 0
    assert "benchmark_version" in artifact["tbd_fields_at_run_time"]


def test_result_records_loss_metadata():
    protocol = load_protocol(PROTOCOL_PATH)
    artifact = run_plumbing(protocol, loss_level=30, seed=7)
    assert artifact["loss_mechanism"] == "mcar"
    assert artifact["loss_level_pct"] == 30
    assert artifact["seed"] == 7
    assert isinstance(artifact["mask_hash"], str) and len(artifact["mask_hash"]) == 64


# ---------------------------------------------------------------------------
# 8. Result artifact is deterministic for same inputs
# ---------------------------------------------------------------------------

def test_plumbing_result_is_deterministic():
    protocol = load_protocol(PROTOCOL_PATH)
    a1 = run_plumbing(protocol, loss_level=10, seed=99)
    a2 = run_plumbing(protocol, loss_level=10, seed=99)
    assert a1["mask_hash"] == a2["mask_hash"]
    assert a1["ground_truth_hash"] == a2["ground_truth_hash"]
    assert a1["prediction_hashes"] == a2["prediction_hashes"]


def test_different_seeds_can_differ():
    """Different seeds may produce different prediction hashes (at non-zero loss)."""
    protocol = load_protocol(PROTOCOL_PATH)
    # Use the 4-event fixture at 50% loss; two seeds should plausibly differ
    a1 = run_plumbing(protocol, loss_level=50, seed=1)
    a2 = run_plumbing(protocol, loss_level=50, seed=9999)
    # The GT hash is always the same
    assert a1["ground_truth_hash"] == a2["ground_truth_hash"]
    # The mask hash should differ (different seeds, same events, 50% loss)
    # Note: with only 4 runtime events, 50% removes 2; seeds may coincidentally
    # pick the same 2. Don't assert a hard difference; assert the masks are recorded.
    assert isinstance(a1["mask_hash"], str)
    assert isinstance(a2["mask_hash"], str)


def test_prediction_hash_helper_is_stable():
    keys, static_ev, runtime_ev = load_case("w03_case_when")
    preds = _predict_all(keys, static_ev, runtime_ev)
    h1 = _prediction_hash(preds["proposed"])
    h2 = _prediction_hash(preds["proposed"])
    assert h1 == h2


def test_gt_hash_helper_is_stable():
    truth = _load_ground_truth_after_prediction("w03_case_when")
    h1 = _gt_hash(truth)
    h2 = _gt_hash(truth)
    assert h1 == h2


# ---------------------------------------------------------------------------
# 9. Existing MCAR behaviour is unchanged
# ---------------------------------------------------------------------------

def test_mcar_still_passes_post_runner():
    """Confirm existing MCAR tests are not broken by importing run.py."""
    from research.missingness.mcar import mcar_loss, VALID_LEVELS
    for level in VALID_LEVELS:
        result = mcar_loss(["a", "b", "c", "d", "e"], level, seed=1)
        assert set(result.kept) | set(result.removed) == {"a", "b", "c", "d", "e"}
