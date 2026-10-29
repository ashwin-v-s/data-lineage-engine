"""Drive the plumbing protocol runner across the full locked loss-level matrix.

This script does NOT reimplement any research logic. It invokes the real runner
(`research/experiments/run.py`) as a subprocess once per (loss level, seed) cell
and consolidates the resulting artifacts into two files under research/results/:

  - summary.json : machine-readable, one entry per (loss level, seed, method)
  - summary.md   : human-readable, one table per loss level

Everything produced here is PLUMBING evidence derived from the w03_case_when
mock fixture. It is NOT a research finding and must not be reported as one.

Run from the repository root:

    python scripts/run_benchmark_matrix.py

Optional overrides:

    python scripts/run_benchmark_matrix.py --loss-levels 0,50 --seeds 1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Ensure the repo root is importable when this script is run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.experiments.protocol_loader import load_protocol  # noqa: E402

PROTOCOL_PATH = _REPO_ROOT / "research" / "protocol" / "v1.yaml"
RUNNER_PATH = _REPO_ROOT / "research" / "experiments" / "run.py"

# LOCKED loss-level matrix (Pack Section 22 / protocol `loss.levels`).
DEFAULT_LOSS_LEVELS: List[int] = [0, 10, 30, 50, 70, 90]
# At least three distinct seeds per level.
DEFAULT_SEEDS: List[int] = [1, 7, 42]

METHODS: List[str] = ["proposed", "B1", "B2", "B3", "B4", "B5"]

# Full key-metric set recorded per method in summary.json (everything the
# metrics module returns except the nested `confusion` mapping).
HEADLINE_METRICS: List[str] = [
    "N",
    "N_P",
    "N_N",
    "unscored_predictions",
    "unpredicted_truth",
    "precision_strict",
    "recall_strict",
    "fpr_strict",
    "fnr_strict",
    "query_exact_strict",
    "query_jaccard_strict",
    "precision_lenient",
    "recall_lenient",
    "fpr_lenient",
    "fnr_lenient",
    "query_exact_lenient",
    "query_jaccard_lenient",
    "false_refutation",
    "false_observation",
    "correct_refutation",
    "unknown_rate",
    "possible_rate",
    "possible_precision",
    "correct_commitment",
    "wrong_commitment",
    "non_committal",
    "committed_accuracy",
]

# Curated subset shown as the columns of the per-loss-level markdown tables.
MD_METRICS: List[str] = [
    "false_refutation",
    "false_observation",
    "precision_strict",
    "recall_strict",
    "fpr_strict",
    "fnr_strict",
    "precision_lenient",
    "recall_lenient",
    "committed_accuracy",
    "correct_commitment",
    "non_committal",
    "query_exact_strict",
    "query_jaccard_strict",
]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(value: Any) -> str:
    """Render a metric value for the markdown tables (NA for None)."""
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _mean(values: Sequence[Any]) -> Optional[float]:
    """Mean over the non-None values; None if no value is present."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


# ---------------------------------------------------------------------------
# Runner invocation
# ---------------------------------------------------------------------------

def _invoke_runner(level: int, seed: int, results_dir: Path) -> Path:
    """Run the real runner once and return the produced artifact path."""
    cmd = [
        sys.executable,
        str(RUNNER_PATH),
        "--protocol",
        str(PROTOCOL_PATH.relative_to(_REPO_ROOT)),
        "--plumbing",
        "--loss-level",
        str(level),
        "--seed",
        str(seed),
    ]
    print(f"[matrix] ({level:>2}%, seed={seed}) -> {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True)
    if proc.stdout.strip():
        print(proc.stdout.rstrip(), flush=True)
    if proc.stderr.strip():
        print(proc.stderr.rstrip(), file=sys.stderr, flush=True)

    if proc.returncode != 0:
        raise SystemExit(
            f"[matrix] FAILED: runner exited with code {proc.returncode} "
            f"for loss_level={level} seed={seed}"
        )

    artifact_path = results_dir / f"result_plumbing_mcar{level}_seed{seed}.json"
    if not artifact_path.exists():
        raise SystemExit(
            f"[matrix] FAILED: runner reported success but artifact not found: {artifact_path}"
        )
    return artifact_path


# ---------------------------------------------------------------------------
# Summary construction
# ---------------------------------------------------------------------------

def _collect_runs(
    loss_levels: Sequence[int],
    seeds: Sequence[int],
    results_dir: Path,
) -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    for level in loss_levels:
        for seed in seeds:
            artifact_path = _invoke_runner(level, seed, results_dir)
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

            metrics_by_method = artifact.get("metrics", {})
            methods_summary: Dict[str, Dict[str, Any]] = {}
            for method in METHODS:
                m = metrics_by_method.get(method)
                if m is None:
                    raise SystemExit(
                        f"[matrix] FAILED: artifact {artifact_path.name} has no metrics for {method}"
                    )
                methods_summary[method] = {key: m.get(key) for key in HEADLINE_METRICS}

            runs.append(
                {
                    "loss_level_pct": artifact.get("loss_level_pct", level),
                    "seed": artifact.get("seed", seed),
                    "artifact_file": artifact_path.name,
                    "mask_hash": artifact.get("mask_hash"),
                    "ground_truth_hash": artifact.get("ground_truth_hash"),
                    "git_sha": artifact.get("git_sha"),
                    "metrics": methods_summary,
                }
            )
    return runs


def _build_summary_json(
    runs: List[Dict[str, Any]],
    loss_levels: Sequence[int],
    seeds: Sequence[int],
    protocol: Dict[str, Any],
    sample_artifact: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "summary_schema_version": "1.0",
        "generated_by": "scripts/run_benchmark_matrix.py",
        "mode": sample_artifact.get("mode"),
        "plumbing_notice": sample_artifact.get("plumbing_notice"),
        "protocol_path": str(PROTOCOL_PATH.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "protocol_version": protocol.get("protocol_version"),
        "benchmark_version": sample_artifact.get("benchmark_version"),
        "loss_mechanism": sample_artifact.get("loss_mechanism"),
        "loss_levels": list(loss_levels),
        "seeds": list(seeds),
        "methods": list(METHODS),
        "headline_metrics": list(HEADLINE_METRICS),
        "environment": sample_artifact.get("environment"),
        "git_sha": sample_artifact.get("git_sha"),
        "tbd_fields_at_run_time": sample_artifact.get("tbd_fields_at_run_time"),
        "runs": runs,
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _render_table(rows: List[str], metrics: Sequence[str], values: Dict[str, Dict[str, Any]]) -> str:
    header = "| method | " + " | ".join(metrics) + " |"
    sep = "|" + "---|" * (len(metrics) + 1)
    lines = [header, sep]
    for method in rows:
        cells = [_fmt(values[method].get(metric)) for metric in metrics]
        lines.append("| " + method + " | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _build_summary_md(
    runs: List[Dict[str, Any]],
    loss_levels: Sequence[int],
    seeds: Sequence[int],
    protocol: Dict[str, Any],
    sample_artifact: Dict[str, Any],
) -> str:
    notice = sample_artifact.get("plumbing_notice") or "PLUMBING"
    tbd = sample_artifact.get("tbd_fields_at_run_time") or []
    by_cell: Dict[Any, Dict[str, Any]] = {
        (r["loss_level_pct"], r["seed"]): r for r in runs
    }

    out: List[str] = []
    out.append("# Kairos Benchmark Matrix — PLUMBING Summary")
    out.append("")
    out.append("> **PLUMBING EVIDENCE ONLY.** " + str(notice))
    out.append("> These numbers are computed from the `w03_case_when` mock fixture with "
               "MCAR loss. They are **NOT research findings** and must not be reported as such.")
    out.append("")
    out.append("Generated by `scripts/run_benchmark_matrix.py`, which invokes the real runner "
               "(`research/experiments/run.py --plumbing`) as a subprocess.")
    out.append("")
    out.append("| Property | Value |")
    out.append("|---|---|")
    out.append(f"| Protocol file | `{str(PROTOCOL_PATH.relative_to(_REPO_ROOT)).replace(chr(92), '/')}` |")
    out.append(f"| Protocol version | `{protocol.get('protocol_version')}` |")
    out.append(f"| Benchmark version | `{sample_artifact.get('benchmark_version')}` |")
    out.append(f"| Mode | `{sample_artifact.get('mode')}` |")
    out.append(f"| Loss mechanism | `{sample_artifact.get('loss_mechanism')}` |")
    out.append(f"| Loss levels | {', '.join(str(l) for l in loss_levels)} |")
    out.append(f"| Seeds | {', '.join(str(s) for s in seeds)} |")
    out.append(f"| Python version | `{(sample_artifact.get('environment') or {}).get('python_version')}` |")
    out.append(f"| Platform | `{(sample_artifact.get('environment') or {}).get('platform')}` |")
    out.append(f"| git sha | `{sample_artifact.get('git_sha')}` |")
    out.append(f"| TBD fields at run time | {len(tbd)} — " + ", ".join(f"`{f}`" for f in tbd) + " |")
    out.append("")

    for level in loss_levels:
        out.append(f"## Loss level {level}%")
        out.append("")
        artifact_files = []
        per_method: Dict[str, Dict[str, Any]] = {m: {} for m in METHODS}
        for metric in MD_METRICS:
            for method in METHODS:
                per_method[method][metric] = _mean(
                    [by_cell[(level, s)]["metrics"][method].get(metric) for s in seeds]
                )
        for s in seeds:
            artifact_files.append(by_cell[(level, s)]["artifact_file"])
        out.append(
            f"Values are means over seeds [{', '.join(str(s) for s in seeds)}]. "
            f"Artifacts: {', '.join(f'`{f}`' for f in artifact_files)}."
        )
        out.append("")
        out.append(_render_table(METHODS, MD_METRICS, per_method))
        out.append("")

    out.append("## How to reproduce")
    out.append("")
    out.append("From the repository root:")
    out.append("")
    out.append("```bash")
    out.append("# Full matrix (all levels x all seeds):")
    out.append("python scripts/run_benchmark_matrix.py")
    out.append("")
    out.append("# Single cell, using the underlying runner directly:")
    out.append(
        "python research/experiments/run.py --protocol research/protocol/v1.yaml "
        "--plumbing --loss-level 0 --seed 1"
    )
    out.append("```")
    out.append("")
    out.append(
        "Each invocation writes `research/results/result_plumbing_mcar{level}_seed{seed}.json`; "
        "the matrix script consolidates all of them into `research/results/summary.json` and "
        "`research/results/summary.md`."
    )
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_int_list(raw: str, label: str, allowed: Optional[Sequence[int]] = None) -> List[int]:
    try:
        values = [int(v.strip()) for v in raw.split(",") if v.strip()]
    except ValueError as exc:
        raise SystemExit(f"[matrix] invalid --{label}: {raw!r} ({exc})")
    if not values:
        raise SystemExit(f"[matrix] --{label} must not be empty")
    if allowed is not None:
        bad = [v for v in values if v not in allowed]
        if bad:
            raise SystemExit(f"[matrix] invalid {label} values {bad}; allowed: {list(allowed)}")
    return values


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the plumbing benchmark matrix and consolidate the artifacts."
    )
    parser.add_argument(
        "--loss-levels",
        default=",".join(str(l) for l in DEFAULT_LOSS_LEVELS),
        help=f"Comma-separated loss levels (default: {DEFAULT_LOSS_LEVELS}).",
    )
    parser.add_argument(
        "--seeds",
        default=",".join(str(s) for s in DEFAULT_SEEDS),
        help=f"Comma-separated seeds (default: {DEFAULT_SEEDS}).",
    )
    args = parser.parse_args(argv)

    loss_levels = _parse_int_list(args.loss_levels, "loss-levels", allowed=DEFAULT_LOSS_LEVELS)
    seeds = _parse_int_list(args.seeds, "seeds")

    protocol = load_protocol(str(PROTOCOL_PATH))
    results_dir = (_REPO_ROOT / protocol.get("output_path", "research/results/")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    total = len(loss_levels) * len(seeds)
    print(f"[matrix] running {total} plumbing cell(s): "
          f"levels={loss_levels} seeds={seeds}", flush=True)

    runs = _collect_runs(loss_levels, seeds, results_dir)

    sample_artifact = json.loads(
        (results_dir / runs[0]["artifact_file"]).read_text(encoding="utf-8")
    )

    summary_json = _build_summary_json(runs, loss_levels, seeds, protocol, sample_artifact)
    summary_md = _build_summary_md(runs, loss_levels, seeds, protocol, sample_artifact)

    summary_json_path = results_dir / "summary.json"
    summary_md_path = results_dir / "summary.md"
    summary_json_path.write_text(json.dumps(summary_json, indent=2) + "\n", encoding="utf-8")
    summary_md_path.write_text(summary_md, encoding="utf-8")

    print(f"[matrix] wrote {summary_json_path}", flush=True)
    print(f"[matrix] wrote {summary_md_path}", flush=True)
    print(f"[matrix] done: {total} cell(s) OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
