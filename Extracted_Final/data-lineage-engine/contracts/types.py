"""Core value types shared by every module. Standard library only."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class Granularity(str, Enum):
    DATASET = "DATASET"
    COLUMN = "COLUMN"
    TUPLE_CELL = "TUPLE_CELL"


class ParserStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"


class PredictedState(str, Enum):
    OBSERVED = "OBSERVED"
    REFUTED_FOR_RUN = "REFUTED_FOR_RUN"
    POSSIBLE = "POSSIBLE"
    UNKNOWN = "UNKNOWN"


class EvidenceType(str, Enum):
    """There is deliberately NO 'absent' value: absence of an event is never stored."""

    STATIC_DEPENDENCY = "STATIC_DEPENDENCY"
    DBT_DECLARED = "DBT_DECLARED"
    RUNTIME_POSITIVE = "RUNTIME_POSITIVE"
    RUNTIME_NEGATIVE_EVALUATION = "RUNTIME_NEGATIVE_EVALUATION"


class CoverageMode(str, Enum):
    STRUCTURAL = "structural"
    RUNTIME = "runtime"
    GROUND_TRUTH = "ground_truth"  # describes ground-truth coverage; a predictor must never consume it


@dataclass(frozen=True)
class TemporalContext:
    valid_at: Optional[str] = None      # ISO-8601. UI label "Valid at"  (API: as_of)
    known_as_of: Optional[str] = None   # ISO-8601. UI label "Known as of" (API: recorded_as_of)


@dataclass(frozen=True)
class DependencyKey:
    """The prediction unit: (run, source column, target column, granularity, temporal context)."""

    run_id: str
    source_column_id: str
    target_column_id: str
    granularity: Granularity = Granularity.COLUMN
    temporal_context: TemporalContext = TemporalContext()


@dataclass(frozen=True)
class CoverageVector:
    """Structured coverage (Pack Section 14). Not a probability and not a confidence."""

    run_covered: bool
    operator_covered: bool
    source_dataset_covered: bool
    target_dataset_covered: bool
    source_columns_covered: Tuple[str, ...]
    target_columns_covered: Tuple[str, ...]
    branches_covered: bool
    coverage_mode: CoverageMode
    parser_status: ParserStatus

    def is_complete_for(self, key: DependencyKey) -> bool:
        """Complete negative evaluation contract, coverage part.

        Every relevant scope must have been evaluated, semantics must be fully supported and
        the coverage must come from the runtime path (never structural, never ground truth).
        """
        return (
            self.run_covered
            and self.operator_covered
            and self.source_dataset_covered
            and self.target_dataset_covered
            and self.branches_covered
            and self.parser_status == ParserStatus.SUPPORTED
            and self.coverage_mode == CoverageMode.RUNTIME
            and key.source_column_id in self.source_columns_covered
            and key.target_column_id in self.target_columns_covered
        )
