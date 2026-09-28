"""Minimal plumbing experiment runner.

Target: python research/experiments/run.py --protocol research/protocol/v1.yaml [--plumbing]

PLUMBING MODE (--plumbing):
  Runs the full pipeline on the w03_case_when mock fixture.
  Outputs are labelled mode=PLUMBING and must NEVER be reported as research findings.
  TBD protocol values are permitted.

REAL MODE (no --plumbing flag):
  Requires all TBD fields in the protocol to be resolved first.
  Not yet fully wired (benchmark + real ground truth not implemented).

Ground-truth isolation contract (LOCKED):
  Ground truth is loaded ONLY after all predictions have been generated.
  The GT object never enters the engine, any baseline, or coverage construction.
  The runner enforces this by sequencing: predict → collect all predictions → load GT → evaluate.

Pack Section 22: every result records the fields listed in result_artifact().
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure repo root is importable when run directly
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from contracts.evidence import Prediction, PredictorInput
from contracts.mocks.loaders import load_case, load_truth
from contracts.truth import TruthLabel
from contracts.types import DependencyKey
from research.baselines.baselines import ALL_BASELINES
from research.experiments.protocol_loader import (
    ProtocolBlockedError,
    load_protocol,
    validate_protocol,
)
from research.metrics.metrics import evaluate
from research.missingness.capture_manifest import CaptureManifest
from research.missingness.mcar import mcar_loss
from research.reasoning.engine import FourStateEngine, REASONING_VERSION

# Ground truth is intentionally imported ONLY here (in the evaluation step).
# It is never passed to any predictor.
from contracts.truth import GroundTruthRecord  # noqa: F401 — imported for type reference only

RUNNER_VERSION = "0.1.0-plumbing"
PLUMBING_FIXTURE = "w03_case_when"


# ---------------------------------------------------------------------------
# Step 1 — load and apply loss (prediction path, no GT)
# ---------------------------------------------------------------------------

def _build_plumbing_manifest(run_id: str) -> CaptureManifest:
    """Build a manifest for the w03_case_when fixture run.
    Coverage mirrors what the fixture's full runtime evidence covers.
    This manifest is constructed independently of the MCAR simulator.
    """
    return CaptureManifest(
        run_id=run_id,
        instrumented_source_cols=frozenset(["employees.country", "employees.salary"]),
        instrumented_target_cols=frozenset(["out.adjusted_salary"]),
    )


def _apply_loss(
    runtime_evidence: Sequence,
    level_pct: int,
    seed: int,
) -> Tuple[Sequence, str]:
    """Apply MCAR loss to runtime evidence.

    Returns (surviving_evidence, mask_hash).
    CoverageVector is derived from the manifest, NOT from the removed set.
    """
    if level_pct == 0:
        # No loss — return all evidence; hash is still computed for the artifact
        from research.missingness.mcar import _mask_hash
        return list(runtime_evidence), _mask_hash((), 0, seed)

    event_ids = [ev.evidence_id for ev in runtime_evidence]
    result = mcar_loss(event_ids, level_pct, seed)
    kept_set = set(result.kept)
    surviving = [ev for ev in runtime_evidence if ev.evidence_id in kept_set]
    return surviving, result.mask_hash


# ---------------------------------------------------------------------------
# Step 2 — predict (no GT allowed past this point until evaluation)
# ---------------------------------------------------------------------------

def _predict_all(
    keys: Sequence[DependencyKey],
    static_evidence: Sequence,
    surviving_runtime: Sequence,
) -> Dict[str, List[Prediction]]:
    """Run all predictors. Returns dict method_name -> predictions.

    Ground truth is NEVER passed here.
    """
    inp = PredictorInput(
        keys=tuple(keys),
        static_evidence=tuple(static_evidence),
        runtime_evidence=tuple(surviving_runtime),
    )
    results: Dict[str, List[Prediction]] = {}

    # Proposed method
    engine = FourStateEngine()
    results["proposed"] = list(engine.infer(inp))

    # Baselines B1–B5
    for name, cls in ALL_BASELINES.items():
        bl = cls()
        results[name] = list(bl.infer(inp))

    return results


# ---------------------------------------------------------------------------
# Step 3 — evaluate (GT loaded HERE, after all predictions exist)
# ---------------------------------------------------------------------------

def _load_ground_truth_after_prediction(fixture: str) -> Dict[DependencyKey, TruthLabel]:
    """Load ground truth. Called only after all predictions are complete."""
    records = load_truth(fixture)
    return {r.key: r.label for r in records}


def _evaluate_all(
    predictions_by_method: Dict[str, List[Prediction]],
    truth: Dict[DependencyKey, TruthLabel],
) -> Dict[str, Dict[str, Any]]:
    return {name: evaluate(preds, truth) for name, preds in predictions_by_method.items()}


# ---------------------------------------------------------------------------
# Result artifact
# ---------------------------------------------------------------------------

def _prediction_hash(predictions: List[Prediction]) -> str:
    """Stable hash of a prediction list for the result artifact."""
    canonical = json.dumps(
        sorted(
            [
                {
                    "run": p.key.run_id,
                    "src": p.key.source_column_id,
                    "tgt": p.key.target_column_id,
                    "state": p.state.value,
                    "rule": p.rule_id,
                }
                for p in predictions
            ],
            key=lambda d: (d["run"], d["src"], d["tgt"]),
        ),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _gt_hash(truth: Dict[DependencyKey, TruthLabel]) -> str:
    """Stable hash of the ground-truth mapping."""
    canonical = json.dumps(
        sorted(
            [
                {
                    "run": k.run_id,
                    "src": k.source_column_id,
                    "tgt": k.target_column_id,
                    "label": v.value,
                }
                for k, v in truth.items()
            ],
            key=lambda d: (d["run"], d["src"], d["tgt"]),
        ),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _git_sha() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "unavailable"
    except Exception:
        return "unavailable"


def result_artifact(
    *,
    mode: str,
    protocol_version: str,
    benchmark_version: str,
    loss_mechanism: str,
    loss_level: int,
    seed: int,
    mask_hash: str,
    gt_hash: str,
    predictions_by_method: Dict[str, List[Prediction]],
    metrics_by_method: Dict[str, Dict[str, Any]],
    tbd_fields: List[str],
) -> Dict[str, Any]:
    """Build the result artifact dict. PLUMBING outputs are explicitly labelled."""
    return {
        "mode": mode,                              # "PLUMBING" or "REAL"
        "runner_version": RUNNER_VERSION,
        "protocol_version": protocol_version,
        "benchmark_version": benchmark_version,
        "loss_mechanism": loss_mechanism,
        "loss_level_pct": loss_level,
        "seed": seed,
        "mask_hash": mask_hash,
        "ground_truth_hash": gt_hash,
        "prediction_hashes": {
            name: _prediction_hash(preds)
            for name, preds in predictions_by_method.items()
        },
        "git_sha": _git_sha(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "tbd_fields_at_run_time": tbd_fields,
        "metrics": metrics_by_method,
        "plumbing_notice": (
            "PLUMBING — outputs computed from mock fixture data. "
            "These numbers are NOT research findings."
        ) if mode == "PLUMBING" else None,
    }


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def _write_artifact(artifact: Dict[str, Any], output_path: str) -> Path:
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    mode = artifact.get("mode", "UNKNOWN").lower()
    level = artifact.get("loss_level_pct", 0)
    seed = artifact.get("seed", 0)
    fname = f"result_{mode}_mcar{level}_seed{seed}.json"
    dest = out_dir / fname
    dest.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_plumbing(protocol: Dict[str, Any], loss_level: int = 0, seed: int = 1) -> Dict[str, Any]:
    """Full plumbing pipeline on the w03_case_when fixture.

    GROUND TRUTH IS LOADED ONLY AFTER ALL PREDICTIONS ARE COMPLETE.
    """
    # 1. Load case (no GT)
    keys, static_ev, all_runtime_ev = load_case(PLUMBING_FIXTURE)

    # 2. Build capture manifest (independent of loss)
    # For the plumbing run, build one manifest per unique run_id in the fixture
    unique_runs = sorted({k.run_id for k in keys})

    # 3. Apply MCAR loss (per-run for the fixture; all events treated together for simplicity
    #    at 0% loss the result is always identical)
    all_event_ids = [ev.evidence_id for ev in all_runtime_ev]
    if loss_level == 0:
        from research.missingness.mcar import _mask_hash
        surviving_runtime = list(all_runtime_ev)
        mask_hash = _mask_hash((), 0, seed)
    else:
        loss_result = mcar_loss(all_event_ids, loss_level, seed)
        kept_set = set(loss_result.kept)
        surviving_runtime = [ev for ev in all_runtime_ev if ev.evidence_id in kept_set]
        mask_hash = loss_result.mask_hash

    # 4. PREDICT — GT is not loaded yet
    predictions_by_method = _predict_all(keys, static_ev, surviving_runtime)

    # 5. ONLY NOW load ground truth
    truth = _load_ground_truth_after_prediction(PLUMBING_FIXTURE)

    # 6. Evaluate
    metrics_by_method = _evaluate_all(predictions_by_method, truth)

    # 7. Build artifact
    validation = validate_protocol(protocol)
    artifact = result_artifact(
        mode="PLUMBING",
        protocol_version=protocol.get("protocol_version", "TBD"),
        benchmark_version=protocol.get("benchmark_version", "TBD"),
        loss_mechanism="mcar",
        loss_level=loss_level,
        seed=seed,
        mask_hash=mask_hash,
        gt_hash=_gt_hash(truth),
        predictions_by_method=predictions_by_method,
        metrics_by_method=metrics_by_method,
        tbd_fields=validation.tbd_fields,
    )

    # 8. Write
    output_path = protocol.get("output_path", "research/results/")
    _write_artifact(artifact, output_path)

    return artifact


def run_real(_protocol: Dict[str, Any]) -> None:
    """Placeholder for the real experiment pipeline.
    Will be wired when benchmarks, real GT provider, and storage are ready.
    """
    raise NotImplementedError(
        "Real experiment pipeline is not yet implemented. "
        "Run with --plumbing to execute the mock pipeline."
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kairos experiment runner (Pack Section 42)."
    )
    parser.add_argument(
        "--protocol",
        default="research/protocol/v1.yaml",
        help="Path to the protocol YAML file.",
    )
    parser.add_argument(
        "--plumbing",
        action="store_true",
        help="Run in plumbing mode (mock fixture, TBD values permitted).",
    )
    parser.add_argument(
        "--loss-level",
        type=int,
        default=0,
        choices=[0, 10, 30, 50, 70, 90],
        help="MCAR loss level percent (default: 0).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Random seed for the loss draw (default: 1).",
    )
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol)
    validation = validate_protocol(protocol)

    for w in validation.warnings:
        print(f"[WARN] {w}", file=sys.stderr)

    try:
        validation.raise_if_blocking(plumbing=args.plumbing)
    except ProtocolBlockedError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    if args.plumbing:
        print("[INFO] Running in PLUMBING mode — output is NOT a research finding.")
        artifact = run_plumbing(protocol, loss_level=args.loss_level, seed=args.seed)
        output_path = protocol.get("output_path", "research/results/")
        level = artifact["loss_level_pct"]
        seed = artifact["seed"]
        print(f"[INFO] Result written to {output_path}result_plumbing_mcar{level}_seed{seed}.json")
        print(f"[INFO] PLUMBING — proposed committed_accuracy = "
              f"{artifact['metrics']['proposed'].get('committed_accuracy')}")
        return 0
    else:
        run_real(protocol)
        return 0


if __name__ == "__main__":
    sys.exit(main())
