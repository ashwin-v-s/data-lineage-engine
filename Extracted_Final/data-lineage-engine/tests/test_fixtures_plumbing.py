"""PLUMBING only: tiny illustrative fixture, not a research result."""
import pytest

from contracts.evidence import PredictorInput
from contracts.mocks.loaders import load_case, load_truth
from contracts.mocks.providers import MockGroundTruthProvider, MockRuntimeEvidenceProvider, MockStaticLineageProvider
from contracts.types import PredictedState as S
from research.baselines.baselines import ALL_BASELINES
from research.metrics.metrics import evaluate
from research.reasoning.engine import FourStateEngine


@pytest.fixture(scope="module")
def case():
    keys, static, runtime = load_case("w03_case_when")
    truth = {r.key: r.label for r in load_truth("w03_case_when")}
    return PredictorInput(tuple(keys), tuple(static), tuple(runtime)), truth


def states(preds):
    return {(p.key.run_id, p.key.source_column_id.split(".")[1]): p.state for p in preds}


def test_fixtures_are_labelled_mock(case):
    keys, static, runtime = load_case("w03_case_when")
    assert all(s.is_mock for s in static) and all(r.is_mock for r in runtime)
    assert all(r.is_mock for r in load_truth("w03_case_when"))


def test_proposed_engine_states(case):
    inp, _ = case
    st = states(FourStateEngine().infer(inp))
    assert st[("run_A", "salary")] == S.OBSERVED
    assert st[("run_B", "salary")] == S.REFUTED_FOR_RUN      # complete negative evaluation
    assert st[("run_C", "salary")] == S.POSSIBLE              # evidence lost: never refuted
    assert st[("run_D", "salary")] == S.POSSIBLE
    assert st[("run_B", "country")] == S.OBSERVED
    assert st[("run_C", "country")] == S.POSSIBLE


def test_proposed_has_no_false_refutation_but_b2_does(case):
    inp, truth = case
    proposed = evaluate(FourStateEngine().infer(inp), truth)
    b2 = evaluate(ALL_BASELINES["B2"]().infer(inp), truth)
    assert proposed["false_refutation"] == 0.0
    assert b2["false_refutation"] == pytest.approx(3 / 6)     # lost evidence turned into refutations
    assert proposed["recall_lenient"] == 1.0 and proposed["committed_accuracy"] == 1.0


def test_mock_providers_return_labelled_canned_data():
    ev = MockRuntimeEvidenceProvider().normalize("run_A", [])
    assert len(ev.evidence) == 2 and all(e.is_mock for e in ev.evidence)
    gt = MockGroundTruthProvider().compute(None, "run_B")  # type: ignore[arg-type]
    assert len(gt.records) == 2 and all(r.is_mock for r in gt.records)
    assert MockStaticLineageProvider().extract("", None, "postgres").evidence  # type: ignore[arg-type]
