import hashlib
import json

from .provider import (
    GroundTruthProvider,
    GroundTruthResult,
    PropagationLabel,
)


class ReferenceInterpreterProvider(GroundTruthProvider):
    """
    Simple independent reference provider.

    This provider uses an explicit mapping supplied by the
    ground-truth fixture. It does not use runtime evidence
    or the prediction/reasoning layer.
    """

    def __init__(
        self,
        propagation_map: dict[tuple[str, str], bool],
        version: str = "reference-1.0",
    ):
        self.propagation_map = propagation_map
        self.version = version

    def determine(
        self,
        source_column: str,
        target_column: str,
    ) -> GroundTruthResult:

        key = (source_column, target_column)

        propagated = self.propagation_map.get(key, False)

        if propagated:
            label = PropagationLabel.PROPAGATED
        else:
            label = PropagationLabel.NOT_PROPAGATED

        artifact = {
            "source_column": source_column,
            "target_column": target_column,
            "label": label.value,
            "provider": "reference_interpreter",
            "version": self.version,
        }

        canonical = json.dumps(
            artifact,
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
            provider="reference_interpreter",
            version=self.version,
            artifact_hash=artifact_hash,
        )
        