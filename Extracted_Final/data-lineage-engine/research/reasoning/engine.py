"""Four-state reasoning engine (Pack Section 14, rules R0 to R5). Status: PROVISIONAL, NOT VALIDATED.

Hard boundary: this module must never import contracts.truth or research.ground_truth.
Inputs are scanned at runtime, and any ground-truth token raises LeakageError.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Dict, Iterable, List, Sequence, Tuple

from contracts.evidence import Prediction, PredictorInput, RuntimeEvidence, StaticEvidence
from contracts.types import (
    CoverageMode,
    DependencyKey,
    EvidenceType,
    Granularity,
    ParserStatus,
    PredictedState,
)

REASONING_VERSION = "0.1.0-plumbing"
_TRUTH_TOKENS = {"PROPAGATED", "NOT_PROPAGATED"}
_TRUTH_MODULE = "contracts.truth"


class LeakageError(Exception):
    """Raised when anything that looks like ground truth reaches a predictor."""


def _scan(obj: object, path: str = "input") -> None:
    if type(obj).__module__ == _TRUTH_MODULE:
        raise LeakageError(f"ground-truth type {type(obj).__name__} found at {path}")
    if isinstance(obj, Enum):
        if str(obj.value) in _TRUTH_TOKENS:
            raise LeakageError(f"ground-truth label {obj.value} found at {path}")
        return
    if isinstance(obj, str):
        if obj in _TRUTH_TOKENS:
            raise LeakageError(f"ground-truth label {obj} found at {path}")
        return
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            _scan(getattr(obj, f.name), f"{path}.{f.name}")
        return
    if isinstance(obj, (tuple, list, set, frozenset)):
        for i, x in enumerate(obj):
            _scan(x, f"{path}[{i}]")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _scan(k, f"{path}.key")
            _scan(v, f"{path}[{k!r}]")


def guard_inputs(inp: PredictorInput) -> None:
    """Refuse ground truth in any form. Also refuse evidence whose coverage mode is ground_truth."""
    _scan(inp)
    for ev in inp.runtime_evidence:
        if ev.coverage.coverage_mode == CoverageMode.GROUND_TRUTH:
            raise LeakageError(f"evidence {ev.evidence_id} has coverage_mode ground_truth")


def _sig(key: DependencyKey) -> Tuple[str, str, Granularity]:
    return (key.source_column_id, key.target_column_id, key.granularity)


def _run_sig(key: DependencyKey) -> Tuple[str, str, str, Granularity]:
    return (key.run_id, key.source_column_id, key.target_column_id, key.granularity)


def index_static(items: Iterable[StaticEvidence]) -> Dict[Tuple[str, str, Granularity], List[StaticEvidence]]:
    out: Dict[Tuple[str, str, Granularity], List[StaticEvidence]] = {}
    for s in items:
        if s.source_column_id and s.target_column_id:
            out.setdefault((s.source_column_id, s.target_column_id, s.granularity), []).append(s)
    return out


def index_runtime(items: Iterable[RuntimeEvidence]) -> Dict[Tuple[str, str, str, Granularity], List[RuntimeEvidence]]:
    out: Dict[Tuple[str, str, str, Granularity], List[RuntimeEvidence]] = {}
    for r in items:
        out.setdefault(_run_sig(r.key), []).append(r)
    return out


def _pred(key, state, rule, expl, ev_ids=(), cov=None, flags=(), version=REASONING_VERSION) -> Prediction:
    return Prediction(
        key=key, state=state, evidence_ids=tuple(ev_ids), coverage=cov,
        reasoning_version=version, rule_id=rule, explanation=expl, flags=tuple(flags),
    )


class FourStateEngine:
    """Rules, first match wins. R0 (temporal filtering) is applied upstream by the repository.

    enable_refutation=False turns this into baseline B4 (three-state: no REFUTED_FOR_RUN).
    """

    def __init__(self, enable_refutation: bool = True, version: str = REASONING_VERSION) -> None:
        self.enable_refutation = enable_refutation
        self.version = version if enable_refutation else version + "+no-refutation"

    def infer(self, inp: PredictorInput) -> Tuple[Prediction, ...]:
        guard_inputs(inp)
        static_ix = index_static(inp.static_evidence)
        runtime_ix = index_runtime(inp.runtime_evidence)
        return tuple(self._infer_one(k, static_ix.get(_sig(k), []), runtime_ix.get(_run_sig(k), [])) for k in inp.keys)

    def _infer_one(self, key: DependencyKey, static: Sequence[StaticEvidence], runtime: Sequence[RuntimeEvidence]) -> Prediction:
        v = self.version
        # R1: unresolved identity, or unsupported / ambiguous static semantics for this dependency
        if not key.source_column_id or not key.target_column_id:
            return _pred(key, PredictedState.UNKNOWN, "R1", "Source or target identity is unresolved.", version=v)
        unsupported = [s for s in static if s.parser_status == ParserStatus.UNSUPPORTED]
        if unsupported:
            note = ""
            if any(r.evidence_type == EvidenceType.RUNTIME_POSITIVE for r in runtime):
                note = " Positive runtime evidence exists but is not used to override unsupported static semantics."
            return _pred(key, PredictedState.UNKNOWN, "R1",
                         "Static semantics are unsupported or ambiguous for this dependency." + note,
                         [s.evidence_id for s in unsupported], version=v)
        candidates = list(static)
        positives = [r for r in runtime if r.evidence_type == EvidenceType.RUNTIME_POSITIVE]
        # R2: positive runtime evidence
        if positives:
            flags = () if candidates else ("CONFLICT_NO_STATIC_CANDIDATE",)
            expl = "At least one source value was observed to contribute to a target output in this run."
            if flags:
                expl += " Static analysis found no matching candidate: flagged as a conflict, evidence retained."
            return _pred(key, PredictedState.OBSERVED, "R2", expl,
                         [r.evidence_id for r in positives], positives[0].coverage, flags, v)
        # R3: complete negative evaluation, static candidate fully supported
        negatives = [r for r in runtime if r.evidence_type == EvidenceType.RUNTIME_NEGATIVE_EVALUATION
                     and r.coverage.is_complete_for(key)]
        fully_supported = bool(candidates) and all(
            s.parser_status == ParserStatus.SUPPORTED and not s.unsupported_constructs for s in candidates)
        if self.enable_refutation and fully_supported and negatives:
            return _pred(key, PredictedState.REFUTED_FOR_RUN, "R3",
                         "No propagation was established for this run under a declared complete negative evaluation.",
                         [r.evidence_id for r in negatives] + [s.evidence_id for s in candidates],
                         negatives[0].coverage, (), v)
        # R4: static candidate, evidence insufficient
        if candidates:
            return _pred(key, PredictedState.POSSIBLE, "R4",
                         "Static analysis permits this dependency, but there is no positive runtime evidence and no complete "
                         "negative evaluation for this run. Absence of an event is not evidence of absence.",
                         [s.evidence_id for s in candidates], None, (), v)
        # R5: nothing to go on
        return _pred(key, PredictedState.UNKNOWN, "R5", "Not a static candidate and no positive runtime evidence.", version=v)
