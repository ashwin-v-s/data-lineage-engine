import hashlib
import json
from typing import Any

from .models import RuntimeEvidence


class RuntimeEvidenceNormalizer:
    """
    Converts raw OpenLineage events into RuntimeEvidence.

    The original event is preserved in raw_event.
    Missing events are NOT converted into negative evidence.
    """

    def __init__(self):
        self.seen_event_ids: set[str] = set()
        self.seen_payload_hashes: set[str] = set()

    def _payload_hash(self, event: dict[str, Any]) -> str:
        """
        Create a deterministic hash from the complete event payload.
        """
        canonical = json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def _event_id(self, event: dict[str, Any]) -> str:
        """
        Use an existing event ID if available.

        Otherwise create a deterministic ID from the
        canonical event payload.
        """
        if event.get("eventId"):
            return str(event["eventId"])

        return self._payload_hash(event)

    def normalize(
        self,
        event: dict[str, Any],
    ) -> RuntimeEvidence | None:

        event_id = self._event_id(event)
        payload_hash = self._payload_hash(event)

        # --------------------------------------------------
        # Duplicate detection
        # --------------------------------------------------
        if (
            event_id in self.seen_event_ids
            or payload_hash in self.seen_payload_hashes
        ):
            return None

        self.seen_event_ids.add(event_id)
        self.seen_payload_hashes.add(payload_hash)

        # --------------------------------------------------
        # Basic OpenLineage fields
        # --------------------------------------------------
        event_type = str(event.get("eventType", "UNKNOWN"))

        event_time = str(event.get("eventTime", ""))

        run = event.get("run", {})
        run_id = str(run.get("runId", ""))

        job = event.get("job", {})
        job_name = str(job.get("name", ""))

        # --------------------------------------------------
        # Extract input datasets
        # --------------------------------------------------
        inputs = []

        for dataset in event.get("inputs", []):
            namespace = dataset.get("namespace", "")
            name = dataset.get("name", "")

            if namespace and name:
                inputs.append(f"{namespace}:{name}")
            elif name:
                inputs.append(name)

        # --------------------------------------------------
        # Extract output datasets
        # --------------------------------------------------
        outputs = []

        for dataset in event.get("outputs", []):
            namespace = dataset.get("namespace", "")
            name = dataset.get("name", "")

            if namespace and name:
                outputs.append(f"{namespace}:{name}")
            elif name:
                outputs.append(name)

        # --------------------------------------------------
        # Diagnostics
        # --------------------------------------------------
        diagnostics = []

        if not run_id:
            diagnostics.append("missing_run_id")

        if not job_name:
            diagnostics.append("missing_job_name")

        if event_type == "UNKNOWN":
            diagnostics.append("unknown_event_type")

        # --------------------------------------------------
        # Create normalized evidence
        # --------------------------------------------------
        return RuntimeEvidence(
            run_id=run_id,
            event_type=event_type,
            event_time=event_time,
            job_name=job_name,
            inputs=inputs,
            outputs=outputs,
            raw_event=event,
            event_id=event_id,
            payload_hash=payload_hash,
            diagnostics=diagnostics,
        )
        
    def normalize_events(
        self,
        events: list[dict[str, Any]],
    ) -> list[RuntimeEvidence]:
        """
        Normalize a collection of observed runtime events.

        An empty input produces an empty list.
        Missing runtime events are not converted into negative evidence.
        """
        normalized = []

        for event in events:
            evidence = self.normalize(event)

            if evidence is not None:
                normalized.append(evidence)

        return normalized