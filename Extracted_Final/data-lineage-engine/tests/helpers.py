"""Small builders for hand-made predictor inputs."""
from contracts.evidence import PredictorInput, RuntimeEvidence, StaticEvidence
from contracts.types import (
    CoverageMode, CoverageVector, DependencyKey, EvidenceType, Granularity, ParserStatus,
)

SRC, TGT = "t.src", "t.tgt"


def key(run="r1", src=SRC, tgt=TGT):
    return DependencyKey(run, src, tgt, Granularity.COLUMN)


def cov(complete=True, mode=CoverageMode.RUNTIME, status=ParserStatus.SUPPORTED, src=SRC, tgt=TGT):
    return CoverageVector(complete, complete, complete, complete, (src,) if complete else (), (tgt,) if complete else (),
                          complete, mode, status)


def static(status=ParserStatus.SUPPORTED, constructs=(), src=SRC, tgt=TGT, eid="s1"):
    return StaticEvidence(eid, "d_src", "d_tgt", src, tgt, Granularity.COLUMN, "PROJECTION", "e", "q", "sc",
                          status, tuple(constructs))


def positive(k=None, eid="p1", mode=CoverageMode.RUNTIME):
    k = k or key()
    return RuntimeEvidence(eid, EvidenceType.RUNTIME_POSITIVE, k, "mock", "2026-01-01T00:00:00Z",
                           cov(True, mode), "h")


def negative(k=None, eid="n1"):
    k = k or key()
    return RuntimeEvidence(eid, EvidenceType.RUNTIME_NEGATIVE_EVALUATION, k, "mock", "2026-01-01T00:00:00Z",
                           cov(True), "h")


def inp(static_ev=(), runtime_ev=(), keys=None):
    return PredictorInput(tuple(keys or [key()]), tuple(static_ev), tuple(runtime_ev))
