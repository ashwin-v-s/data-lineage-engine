"""Pure metric functions (Pack Section 24). Zero denominators return NA (None), never zero.

Definitions are PROVISIONAL until the team confirms them. This module may import ground-truth
types: it runs AFTER prediction and never feeds anything back to a predictor.
"""
from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple

from contracts.evidence import Prediction
from contracts.truth import TruthLabel
from contracts.types import DependencyKey, PredictedState

NA = None
P, N = TruthLabel.PROPAGATED, TruthLabel.NOT_PROPAGATED
S = PredictedState
POSITIVE_MODES: Dict[str, Set[PredictedState]] = {
    "strict": {S.OBSERVED},
    "lenient": {S.OBSERVED, S.POSSIBLE},
}


def _div(a: float, b: float) -> Optional[float]:
    return NA if b == 0 else a / b


def confusion(preds: Iterable[Prediction], truth: Mapping[DependencyKey, TruthLabel]) -> Dict[Tuple[PredictedState, TruthLabel], int]:
    """Counts n(state, label) over units that have both a prediction and a truth label."""
    counts = {(s, t): 0 for s in PredictedState for t in TruthLabel}
    for p in preds:
        if p.key in truth:
            counts[(p.state, truth[p.key])] += 1
    return counts


def _query_answer(preds: Sequence[Prediction], truth: Mapping[DependencyKey, TruthLabel], positive: Set[PredictedState]):
    groups: Dict[tuple, Tuple[set, set]] = {}
    for p in preds:
        if p.key not in truth:
            continue
        g = (p.key.run_id, p.key.target_column_id, p.key.granularity)
        pred_set, true_set = groups.setdefault(g, (set(), set()))
        if p.state in positive:
            pred_set.add(p.key.source_column_id)
        if truth[p.key] == P:
            true_set.add(p.key.source_column_id)
    if not groups:
        return NA, NA
    exact = sum(1 for a, b in groups.values() if a == b) / len(groups)
    jac = [1.0 if not (a | b) else len(a & b) / len(a | b) for a, b in groups.values()]
    return exact, sum(jac) / len(jac)


def evaluate(preds: Sequence[Prediction], truth: Mapping[DependencyKey, TruthLabel]) -> Dict[str, object]:
    c = confusion(preds, truth)
    n = lambda st, lb: c[(st, lb)]  # noqa: E731
    n_p = sum(n(s, P) for s in S)
    n_n = sum(n(s, N) for s in S)
    total = n_p + n_n
    res: Dict[str, object] = {
        "N": total, "N_P": n_p, "N_N": n_n,
        "unscored_predictions": sum(1 for p in preds if p.key not in truth),
        "unpredicted_truth": len(set(truth) - {p.key for p in preds}),
        "confusion": {f"{s.value}|{t.value}": v for (s, t), v in c.items()},
    }
    for mode, pos in POSITIVE_MODES.items():
        tp = sum(n(s, P) for s in pos)
        fp = sum(n(s, N) for s in pos)
        res[f"precision_{mode}"] = _div(tp, tp + fp)
        res[f"recall_{mode}"] = _div(tp, n_p)
        res[f"fpr_{mode}"] = _div(fp, n_n)
        res[f"fnr_{mode}"] = _div(n_p - tp, n_p)
        exact, jac = _query_answer(preds, truth, pos)
        res[f"query_exact_{mode}"], res[f"query_jaccard_{mode}"] = exact, jac
    res["false_refutation"] = _div(n(S.REFUTED_FOR_RUN, P), n_p)
    res["false_observation"] = _div(n(S.OBSERVED, N), n_n)
    res["correct_refutation"] = _div(n(S.REFUTED_FOR_RUN, N), n_n)
    res["unknown_rate"] = _div(n(S.UNKNOWN, P) + n(S.UNKNOWN, N), total)
    res["possible_rate"] = _div(n(S.POSSIBLE, P) + n(S.POSSIBLE, N), total)
    res["possible_precision"] = _div(n(S.POSSIBLE, P), n(S.POSSIBLE, P) + n(S.POSSIBLE, N))
    correct = n(S.OBSERVED, P) + n(S.REFUTED_FOR_RUN, N)
    wrong = n(S.OBSERVED, N) + n(S.REFUTED_FOR_RUN, P)
    res["correct_commitment"] = _div(correct, total)
    res["wrong_commitment"] = _div(wrong, total)
    res["non_committal"] = _div(total - correct - wrong, total)
    res["committed_accuracy"] = _div(correct, correct + wrong)
    return res
