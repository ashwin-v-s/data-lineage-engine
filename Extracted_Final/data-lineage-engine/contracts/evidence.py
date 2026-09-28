"""Evidence and prediction records. Ground truth is NOT here (see contracts.truth)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .types import (
    CoverageVector,
    DependencyKey,
    EvidenceType,
    Granularity,
    ParserStatus,
    PredictedState,
    TemporalContext,
)


@dataclass(frozen=True)
class StaticEvidence:
    """What a query COULD depend on (SQLGlot / dbt). Never proof that anything executed."""

    evidence_id: str
    source_dataset_id: str
    target_dataset_id: str
    source_column_id: Optional[str]
    target_column_id: Optional[str]
    granularity: Granularity
    operator: str
    expression_fingerprint: str
    query_fingerprint: str
    schema_fingerprint: str
    parser_status: ParserStatus
    unsupported_constructs: Tuple[str, ...] = ()
    diagnostics: Tuple[str, ...] = ()
    is_mock: bool = False


@dataclass(frozen=True)
class RuntimeEvidence:
    """Positive observations or explicit, complete negative evaluations. Absence is never a record."""

    evidence_id: str
    evidence_type: EvidenceType
    key: DependencyKey
    source_system: str
    event_time: str
    coverage: CoverageVector
    raw_payload_hash: str
    is_mock: bool = False

    def __post_init__(self) -> None:
        if self.evidence_type not in (
            EvidenceType.RUNTIME_POSITIVE,
            EvidenceType.RUNTIME_NEGATIVE_EVALUATION,
        ):
            raise ValueError("RuntimeEvidence must be RUNTIME_POSITIVE or RUNTIME_NEGATIVE_EVALUATION")
        if (
            self.evidence_type == EvidenceType.RUNTIME_NEGATIVE_EVALUATION
            and not self.coverage.is_complete_for(self.key)
        ):
            raise ValueError(
                "A negative evaluation must declare complete runtime coverage for its scope; "
                "missing events are never recorded as negatives"
            )


@dataclass(frozen=True)
class Prediction:
    key: DependencyKey
    state: PredictedState
    evidence_ids: Tuple[str, ...]
    coverage: Optional[CoverageVector]
    reasoning_version: str
    rule_id: str
    explanation: str
    flags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PredictorInput:
    """Everything a predictor may read. Deliberately has NO ground-truth fields.

    Temporal filtering (as_of / recorded_as_of) is applied by the StorageRepository before this
    object is built; the engine only records the temporal context.
    """

    keys: Tuple[DependencyKey, ...]
    static_evidence: Tuple[StaticEvidence, ...]
    runtime_evidence: Tuple[RuntimeEvidence, ...]
    temporal_context: TemporalContext = TemporalContext()
