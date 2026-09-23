from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class PropagationLabel(str, Enum):
    PROPAGATED = "PROPAGATED"
    NOT_PROPAGATED = "NOT_PROPAGATED"


@dataclass(frozen=True)
class GroundTruthResult:
    """
    Independently determined ground-truth result.
    """

    source_column: str
    target_column: str
    label: PropagationLabel
    provider: str
    version: str
    artifact_hash: str


class GroundTruthProvider(ABC):
    """
    Interface for independently determining propagation truth.
    """

    @abstractmethod
    def determine(
        self,
        source_column: str,
        target_column: str,
    ) -> GroundTruthResult:
        raise NotImplementedError