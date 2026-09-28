"""Module seams (Pack Section 16). Each Protocol has one owner; changes need review by all members."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, Tuple

from .evidence import Prediction, PredictorInput, RuntimeEvidence, StaticEvidence
from .truth import GroundTruthRecord
from .types import DependencyKey, Granularity, ParserStatus, TemporalContext


@dataclass(frozen=True)
class SchemaSnapshot:
    dataset_id: str
    columns: Tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True)
class StaticExtraction:
    evidence: Tuple[StaticEvidence, ...]
    diagnostics: Tuple[str, ...]
    parser_status: ParserStatus


@dataclass(frozen=True)
class RawEvent:
    event_id: str
    payload: dict
    payload_hash: str


@dataclass(frozen=True)
class RuntimeExtraction:
    evidence: Tuple[RuntimeEvidence, ...]
    diagnostics: Tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    sql: str
    input_dataset_ref: str
    split: str  # development / validation / held_out


@dataclass(frozen=True)
class SupportReport:
    supported: bool
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundTruthResult:
    records: Tuple[GroundTruthRecord, ...]
    status: str  # SUPPORTED / UNSUPPORTED
    unsupported_reasons: Tuple[str, ...]
    artifact_hash: str


@dataclass(frozen=True)
class PutResult:
    stored: bool
    duplicate: bool = False


@dataclass(frozen=True)
class LineageResult:
    nodes: Tuple[str, ...]
    edges: Tuple[Tuple[str, str], ...]
    truncated: bool


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    job_id: str
    status: str


@dataclass(frozen=True)
class ProjectionStatus:
    state: str  # NOT_CONFIGURED / PENDING / APPLIED / FAILED / STALE


class StaticLineageProvider(Protocol):  # owner: M1
    def extract(self, sql: str, schema: SchemaSnapshot, dialect: str = "postgres") -> StaticExtraction: ...


class RuntimeEvidenceProvider(Protocol):  # owner: M2
    def normalize(self, run_id: str, raw_events: Sequence[RawEvent]) -> RuntimeExtraction: ...


class GroundTruthProvider(Protocol):  # owner: M2
    name: str
    version: str

    def supports(self, case: BenchmarkCase) -> SupportReport: ...

    def compute(self, case: BenchmarkCase, run_id: str) -> GroundTruthResult: ...


class ReasoningEngine(Protocol):  # owner: M4
    version: str

    def infer(self, inp: PredictorInput) -> Sequence[Prediction]: ...


class StorageRepository(Protocol):  # owner: M3
    def put_raw_event(self, event: RawEvent) -> PutResult: ...

    def put_evidence(self, ev: object) -> PutResult: ...

    def get_lineage(
        self, entity_id: str, tc: TemporalContext, direction: str, depth: int, granularity: Granularity
    ) -> LineageResult: ...

    def get_run(self, run_id: str) -> RunRecord: ...

    def get_evidence_for(self, key: DependencyKey) -> Sequence[object]: ...

    def put_state(self, p: Prediction) -> None: ...

    def projection_status(self) -> ProjectionStatus: ...
