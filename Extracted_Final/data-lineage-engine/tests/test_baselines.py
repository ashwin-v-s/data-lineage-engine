from contracts.types import ParserStatus, PredictedState as S
from research.baselines.baselines import (
    B1StaticOnly, B2NegativeAssumption, B3DeterministicUnion, B4ThreeState, B5CoverageGatedRuntime,
)

from .helpers import inp, negative, positive, static


def state(engine, i):
    return engine.infer(i)[0].state


def test_b1_static_only_ignores_runtime():
    assert state(B1StaticOnly(), inp([static()], [positive()])) == S.POSSIBLE
    assert state(B1StaticOnly(), inp([], [positive()])) == S.UNKNOWN


def test_b2_negative_assumption_refutes_on_missing_evidence():
    assert state(B2NegativeAssumption(), inp([static()], [])) == S.REFUTED_FOR_RUN
    assert state(B2NegativeAssumption(), inp([static()], [positive()])) == S.OBSERVED


def test_b3_union_does_not_consult_parser_status():
    assert state(B3DeterministicUnion(), inp([static(ParserStatus.UNSUPPORTED)], [])) == S.POSSIBLE


def test_b4_three_state_never_refutes_and_respects_parser_status():
    assert state(B4ThreeState(), inp([static()], [negative()])) == S.POSSIBLE
    assert state(B4ThreeState(), inp([static(ParserStatus.UNSUPPORTED)], [])) == S.UNKNOWN


def test_b5_coverage_gated_needs_complete_negative_evaluation():
    assert state(B5CoverageGatedRuntime(), inp([static()], [negative()])) == S.REFUTED_FOR_RUN
    assert state(B5CoverageGatedRuntime(), inp([static()], [])) == S.UNKNOWN
    assert state(B5CoverageGatedRuntime(), inp([], [positive()])) == S.OBSERVED
