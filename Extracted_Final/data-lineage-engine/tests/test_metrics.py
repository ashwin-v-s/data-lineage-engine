import pytest

from contracts.evidence import Prediction
from contracts.truth import TruthLabel as T
from contracts.types import DependencyKey, Granularity, PredictedState as S
from research.metrics.metrics import NA, evaluate


def mk(i, state, src="s", run=None):
    return Prediction(DependencyKey(run or f"r{i}", src, "t", Granularity.COLUMN), state, (), None, "v", "X", "")


def build(pairs):
    preds = [mk(i, s) for i, (s, _) in enumerate(pairs)]
    truth = {p.key: t for p, (_, t) in zip(preds, pairs)}
    return preds, truth


def test_hand_computed_confusion_and_rates():
    preds, truth = build([
        (S.OBSERVED, T.PROPAGATED), (S.OBSERVED, T.PROPAGATED), (S.OBSERVED, T.NOT_PROPAGATED),
        (S.POSSIBLE, T.PROPAGATED), (S.POSSIBLE, T.NOT_PROPAGATED),
        (S.REFUTED_FOR_RUN, T.PROPAGATED), (S.REFUTED_FOR_RUN, T.NOT_PROPAGATED),
        (S.UNKNOWN, T.PROPAGATED), (S.UNKNOWN, T.NOT_PROPAGATED),
    ])
    r = evaluate(preds, truth)
    assert (r["N"], r["N_P"], r["N_N"]) == (9, 5, 4)
    assert r["false_refutation"] == pytest.approx(1 / 5)
    assert r["false_observation"] == pytest.approx(1 / 4)
    assert r["correct_refutation"] == pytest.approx(1 / 4)
    assert r["precision_strict"] == pytest.approx(2 / 3)
    assert r["recall_strict"] == pytest.approx(2 / 5)
    assert r["recall_lenient"] == pytest.approx(3 / 5)
    assert r["fnr_strict"] == pytest.approx(1 - 2 / 5)
    assert r["unknown_rate"] == pytest.approx(2 / 9)
    assert r["possible_rate"] == pytest.approx(2 / 9)
    assert r["possible_precision"] == pytest.approx(1 / 2)
    # commitments: correct = OBS,P (2) + REF,N (1); wrong = OBS,N (1) + REF,P (1)
    assert r["correct_commitment"] == pytest.approx(3 / 9)
    assert r["wrong_commitment"] == pytest.approx(2 / 9)
    assert r["non_committal"] == pytest.approx(4 / 9)
    assert r["committed_accuracy"] == pytest.approx(3 / 5)
    assert r["correct_commitment"] + r["wrong_commitment"] + r["non_committal"] == pytest.approx(1.0)


def test_zero_denominators_are_na_not_zero():
    preds, truth = build([(S.OBSERVED, T.PROPAGATED)])
    r = evaluate(preds, truth)
    assert r["N_N"] == 0
    assert r["false_observation"] is NA and r["fpr_strict"] is NA and r["correct_refutation"] is NA
    assert r["false_refutation"] == 0.0  # denominator N_P = 1, no false refutations: a real zero
    empty = evaluate([], {})
    assert empty["false_refutation"] is NA and empty["committed_accuracy"] is NA and empty["query_exact_strict"] is NA


def test_unscored_and_unpredicted_are_reported_not_hidden():
    preds, truth = build([(S.OBSERVED, T.PROPAGATED)])
    extra = mk(99, S.OBSERVED)
    missing = DependencyKey("rX", "s", "t", Granularity.COLUMN)
    truth[missing] = T.PROPAGATED
    r = evaluate(preds + [extra], truth)
    assert r["unscored_predictions"] == 1 and r["unpredicted_truth"] == 1


def test_query_answer_accuracy():
    def p(src, st):
        return Prediction(DependencyKey("r", src, "t", Granularity.COLUMN), st, (), None, "v", "X", "")

    preds = [p("a", S.OBSERVED), p("b", S.POSSIBLE), p("c", S.REFUTED_FOR_RUN)]
    truth = {q.key: t for q, t in zip(preds, [T.PROPAGATED, T.PROPAGATED, T.NOT_PROPAGATED])}
    r = evaluate(preds, truth)
    assert r["query_exact_strict"] == 0.0 and r["query_jaccard_strict"] == pytest.approx(1 / 2)
    assert r["query_exact_lenient"] == 1.0 and r["query_jaccard_lenient"] == 1.0
