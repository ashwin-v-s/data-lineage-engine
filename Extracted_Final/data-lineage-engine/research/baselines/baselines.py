"""Baselines B1 to B5 (Pack Section 23). B4 is FourStateEngine(enable_refutation=False).

Same boundary as the engine: never import contracts.truth or research.ground_truth.
"""
from __future__ import annotations

from typing import Tuple

from contracts.evidence import Prediction, PredictorInput
from contracts.types import EvidenceType, ParserStatus, PredictedState
from research.reasoning.engine import (
    FourStateEngine,
    _pred,
    _run_sig,
    _sig,
    guard_inputs,
    index_runtime,
    index_static,
)


class B1StaticOnly:
    """B1: static candidates are the result. Runtime evidence is ignored."""

    version = "b1-0.1.0"

    def infer(self, inp: PredictorInput) -> Tuple[Prediction, ...]:
        guard_inputs(inp)
        st = index_static(inp.static_evidence)
        out = []
        for k in inp.keys:
            cands = [s for s in st.get(_sig(k), []) if s.parser_status != ParserStatus.UNSUPPORTED]
            if cands:
                out.append(_pred(k, PredictedState.POSSIBLE, "B1", "Static candidate; runtime evidence ignored.",
                                 [s.evidence_id for s in cands], version=self.version))
            else:
                out.append(_pred(k, PredictedState.UNKNOWN, "B1", "No static candidate.", version=self.version))
        return tuple(out)


class B2NegativeAssumption:
    """B2: positive runtime evidence -> OBSERVED, otherwise REFUTED_FOR_RUN.

    Deliberately defined negative-assumption baseline. Do not claim it represents every real tool.
    """

    version = "b2-0.1.0"

    def infer(self, inp: PredictorInput) -> Tuple[Prediction, ...]:
        guard_inputs(inp)
        rt = index_runtime(inp.runtime_evidence)
        out = []
        for k in inp.keys:
            pos = [r for r in rt.get(_run_sig(k), []) if r.evidence_type == EvidenceType.RUNTIME_POSITIVE]
            if pos:
                out.append(_pred(k, PredictedState.OBSERVED, "B2", "Positive runtime evidence.",
                                 [r.evidence_id for r in pos], version=self.version))
            else:
                out.append(_pred(k, PredictedState.REFUTED_FOR_RUN, "B2",
                                 "Negative assumption: no positive evidence is treated as absence.", version=self.version))
        return tuple(out)


class B3DeterministicUnion:
    """B3: runtime positive -> OBSERVED; else any static candidate -> POSSIBLE; else UNKNOWN."""

    version = "b3-0.1.0"

    def infer(self, inp: PredictorInput) -> Tuple[Prediction, ...]:
        guard_inputs(inp)
        st, rt = index_static(inp.static_evidence), index_runtime(inp.runtime_evidence)
        out = []
        for k in inp.keys:
            pos = [r for r in rt.get(_run_sig(k), []) if r.evidence_type == EvidenceType.RUNTIME_POSITIVE]
            if pos:
                out.append(_pred(k, PredictedState.OBSERVED, "B3", "Positive runtime evidence.",
                                 [r.evidence_id for r in pos], version=self.version))
            elif st.get(_sig(k)):
                out.append(_pred(k, PredictedState.POSSIBLE, "B3", "Static candidate (parser status not consulted).",
                                 [s.evidence_id for s in st[_sig(k)]], version=self.version))
            else:
                out.append(_pred(k, PredictedState.UNKNOWN, "B3", "Nothing to go on.", version=self.version))
        return tuple(out)


def B4ThreeState() -> FourStateEngine:
    """B4: the proposed rules without the active REFUTED_FOR_RUN state."""
    return FourStateEngine(enable_refutation=False)


class B5CoverageGatedRuntime:
    """B5: positive -> OBSERVED; complete negative evaluation -> REFUTED_FOR_RUN; otherwise UNKNOWN. No static semantics."""

    version = "b5-0.1.0"

    def infer(self, inp: PredictorInput) -> Tuple[Prediction, ...]:
        guard_inputs(inp)
        rt = index_runtime(inp.runtime_evidence)
        out = []
        for k in inp.keys:
            evs = rt.get(_run_sig(k), [])
            pos = [r for r in evs if r.evidence_type == EvidenceType.RUNTIME_POSITIVE]
            neg = [r for r in evs if r.evidence_type == EvidenceType.RUNTIME_NEGATIVE_EVALUATION
                   and r.coverage.is_complete_for(k)]
            if pos:
                out.append(_pred(k, PredictedState.OBSERVED, "B5", "Positive runtime evidence.",
                                 [r.evidence_id for r in pos], version=self.version))
            elif neg:
                out.append(_pred(k, PredictedState.REFUTED_FOR_RUN, "B5", "Complete negative evaluation.",
                                 [r.evidence_id for r in neg], neg[0].coverage, version=self.version))
            else:
                out.append(_pred(k, PredictedState.UNKNOWN, "B5", "Neither positive nor complete negative evidence.",
                                 version=self.version))
        return tuple(out)


ALL_BASELINES = {
    "B1": B1StaticOnly,
    "B2": B2NegativeAssumption,
    "B3": B3DeterministicUnion,
    "B4": B4ThreeState,
    "B5": B5CoverageGatedRuntime,
}
