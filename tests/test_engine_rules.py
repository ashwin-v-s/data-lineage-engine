import pytest

from contracts.evidence import RuntimeEvidence
from contracts.types import CoverageMode, EvidenceType, ParserStatus, PredictedState as S
from research.reasoning.engine import FourStateEngine, LeakageError

from .helpers import cov, inp, key, negative, positive, static

ENGINE = FourStateEngine()


def one(i):
    (p,) = ENGINE.infer(i)
    return p


def test_r1_unsupported_static_gives_unknown_even_with_positive_evidence():
    p = one(inp([static(ParserStatus.UNSUPPORTED)], [positive()]))
    assert (p.state, p.rule_id) == (S.UNKNOWN, "R1")


def test_r1_unresolved_identity_gives_unknown():
    k = key(src="")
    (p,) = ENGINE.infer(inp([static()], [], keys=[k]))
    assert (p.state, p.rule_id) == (S.UNKNOWN, "R1")


def test_r2_positive_evidence_gives_observed():
    p = one(inp([static()], [positive()]))
    assert (p.state, p.rule_id) == (S.OBSERVED, "R2")
    assert p.flags == ()


def test_r2_positive_without_static_candidate_is_observed_with_conflict_flag():
    p = one(inp([], [positive()]))
    assert p.state == S.OBSERVED and "CONFLICT_NO_STATIC_CANDIDATE" in p.flags


def test_r3_complete_negative_evaluation_gives_refuted():
    p = one(inp([static()], [negative()]))
    assert (p.state, p.rule_id) == (S.REFUTED_FOR_RUN, "R3")


def test_missing_runtime_evidence_never_refutes():
    p = one(inp([static()], []))
    assert (p.state, p.rule_id) == (S.POSSIBLE, "R4")


def test_partial_static_never_refutes():
    p = one(inp([static(ParserStatus.PARTIAL)], [negative()]))
    assert p.state == S.POSSIBLE


def test_static_with_unsupported_constructs_never_refutes():
    p = one(inp([static(constructs=("window_function",))], [negative()]))
    assert p.state == S.POSSIBLE


def test_refutation_disabled_is_three_state_b4():
    (p,) = FourStateEngine(enable_refutation=False).infer(inp([static()], [negative()]))
    assert p.state == S.POSSIBLE


def test_r5_no_static_no_runtime_gives_unknown():
    p = one(inp([], []))
    assert (p.state, p.rule_id) == (S.UNKNOWN, "R5")


def test_negative_evaluation_with_incomplete_coverage_cannot_even_be_built():
    with pytest.raises(ValueError):
        RuntimeEvidence("n", EvidenceType.RUNTIME_NEGATIVE_EVALUATION, key(), "mock", "t", cov(complete=False), "h")


def test_negative_evaluation_with_structural_or_ground_truth_mode_cannot_be_built():
    for mode in (CoverageMode.STRUCTURAL, CoverageMode.GROUND_TRUTH):
        with pytest.raises(ValueError):
            RuntimeEvidence("n", EvidenceType.RUNTIME_NEGATIVE_EVALUATION, key(), "mock", "t", cov(mode=mode), "h")


def test_ground_truth_coverage_mode_on_positive_evidence_is_rejected_by_engine():
    with pytest.raises(LeakageError):
        ENGINE.infer(inp([static()], [positive(mode=CoverageMode.GROUND_TRUTH)]))


def test_every_prediction_records_version_and_evidence():
    p = one(inp([static()], [positive()]))
    assert p.reasoning_version and p.evidence_ids == ("p1",)


# --- Day 2A gap tests ---

def test_r1_unresolved_identity_empty_target_gives_unknown():
    # Gap: Day 1 only tested empty source_column_id. Verify empty target_column_id alone also fires R1.
    k = key(tgt="")
    (p,) = ENGINE.infer(inp([static()], [], keys=[k]))
    assert (p.state, p.rule_id) == (S.UNKNOWN, "R1")


def test_r2_partial_static_with_positive_evidence_gives_observed():
    # Gap: confirm R2 fires before the fully_supported check in R3.
    # PARTIAL static must not block OBSERVED when positive runtime evidence exists.
    p = one(inp([static(ParserStatus.PARTIAL)], [positive()]))
    assert (p.state, p.rule_id) == (S.OBSERVED, "R2")


def test_r3_supported_plus_partial_mix_with_complete_negative_never_refutes():
    # Gap: one SUPPORTED + one PARTIAL static candidate + complete negative evaluation.
    # fully_supported requires ALL candidates to be SUPPORTED; PARTIAL candidate must
    # block R3 and fall through to R4 (POSSIBLE), not produce REFUTED_FOR_RUN.
    supported = static(ParserStatus.SUPPORTED, eid="s_sup")
    partial = static(ParserStatus.PARTIAL, eid="s_par")
    p = one(inp([supported, partial], [negative()]))
    assert p.state == S.POSSIBLE
    assert p.rule_id == "R4"
