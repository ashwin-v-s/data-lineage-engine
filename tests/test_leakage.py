import ast
import dataclasses
import inspect
from pathlib import Path

import pytest

import research.baselines.baselines as baselines_mod
import research.reasoning.engine as engine_mod
from contracts.evidence import PredictorInput
from contracts.truth import GroundTruthRecord, TruthLabel
from research.baselines.baselines import ALL_BASELINES
from research.reasoning.engine import FourStateEngine, LeakageError
from scripts.check_import_boundaries import _modules, check

from .helpers import inp, key, static

ROOT = Path(__file__).resolve().parent.parent


def test_predictor_cannot_access_ground_truth():
    """Named in the contract. Fails if ground truth can reach any predictor."""
    # 1. type level: PredictorInput has no ground-truth typed or named fields
    for f in dataclasses.fields(PredictorInput):
        assert "truth" not in f.name.lower()
        assert "TruthLabel" not in str(f.type) and "GroundTruth" not in str(f.type)
    # 2. runtime: ground-truth objects or tokens in inputs are refused by the engine and every baseline
    rec = GroundTruthRecord(key(), TruthLabel.PROPAGATED, "mock", "0", "x", True)
    engines = [FourStateEngine()] + [c() for c in ALL_BASELINES.values()]
    for eng in engines:
        with pytest.raises(LeakageError):
            eng.infer(PredictorInput((key(),), (static(),), (rec,)))  # type: ignore[arg-type]
    # 3. modules do not import ground-truth code (AST, so comments and strings do not count)
    for mod in (engine_mod, baselines_mod):
        imported = _modules(ast.parse(inspect.getsource(mod)))
        assert not any(m.startswith(("contracts.truth", "research.ground_truth")) for m in imported)


def test_truth_label_string_anywhere_in_input_is_refused():
    bad = static()
    bad = dataclasses.replace(bad, diagnostics=("PROPAGATED",))
    with pytest.raises(LeakageError):
        FourStateEngine().infer(inp([bad], []))


def test_repository_import_boundaries_hold():
    assert check(ROOT) == []


def test_boundary_checker_detects_violations(tmp_path):
    (tmp_path / "research" / "reasoning").mkdir(parents=True)
    (tmp_path / "research" / "reasoning" / "bad.py").write_text("from contracts.truth import TruthLabel\n")
    (tmp_path / "research" / "ground_truth").mkdir(parents=True)
    (tmp_path / "research" / "ground_truth" / "bad2.py").write_text("import sqlglot\n")
    (tmp_path / "research" / "bad3.py").write_text("import backend.app\n")
    issues = check(tmp_path)
    assert len(issues) == 3
