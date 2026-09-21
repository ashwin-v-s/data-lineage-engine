"""Ground-truth-only types. research.reasoning and research.baselines MUST NOT import this module."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import DependencyKey


class TruthLabel(str, Enum):
    PROPAGATED = "PROPAGATED"
    NOT_PROPAGATED = "NOT_PROPAGATED"


@dataclass(frozen=True)
class GroundTruthRecord:
    key: DependencyKey
    label: TruthLabel
    mechanism: str          # "provsql" / "reference_interpreter" / "hand_derived" (mock)
    provider_version: str
    provenance_ref: str
    is_mock: bool = False
