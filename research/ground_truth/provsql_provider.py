import hashlib
import json

from .provider import (
    GroundTruthProvider,
    GroundTruthResult,
    PropagationLabel,
)


class ProvSQLProvider(GroundTruthProvider):
    """
    Independent ground-truth provider backed by a ProvSQL provenance artifact.

    The provider consumes provenance output produced by the independent
    ProvSQL path. It does not import SQLGlot, ingestion, or reasoning code.
    """

    def __init__(
        self,
        provenance_artifact: dict,
        version: str = "provsql-1.4.0",
    ):
        self.provenance_artifact = provenance_artifact
        self.version = version

    def determine(
        self,
        source_column: str,
        target_column: str,
    ) -> GroundTruthResult:

        propagated_pairs = {
            (pair[0], pair[1])
            for pair in self.provenance_artifact.get("propagated_pairs", [])
        }

        if (source_column, target_column) in propagated_pairs:
            label = PropagationLabel.PROPAGATED
        else:
            label = PropagationLabel.NOT_PROPAGATED

        canonical = json.dumps(
            self.provenance_artifact,
            sort_keys=True,
            separators=(",", ":"),
        )

        artifact_hash = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        return GroundTruthResult(
            source_column=source_column,
            target_column=target_column,
            label=label,
            provider="provsql",
            version=self.version,
            artifact_hash=artifact_hash,
        )
