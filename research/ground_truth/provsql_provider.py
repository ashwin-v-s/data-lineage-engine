"""
ProvSQLProvider
───────────────
Independent ground-truth provider backed by a ProvSQL provenance artifact.

Implements BOTH interfaces:
  - research.ground_truth.provider.GroundTruthProvider (ABC)
      determine(source_column, target_column) -> research GroundTruthResult

  - contracts.interfaces.GroundTruthProvider (Protocol)
      supports(case) -> SupportReport
      compute(case, run_id) -> contracts GroundTruthResult

ProvSQL status: NOT RUNNABLE on native Windows (no pre-built binary, no Docker,
no WSL2). See research/ground_truth/SPIKE_REPORT.md for the full outcome.
ReferenceInterpreterProvider is the production fallback.

Independence rule: this module must not bring in sqlglot, ingestion,
research.reasoning, or research.baselines — checked by CI.
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from contracts.truth import GroundTruthRecord, TruthLabel
from contracts.types import DependencyKey, Granularity, TemporalContext

from .provider import (
    GroundTruthProvider,
    GroundTruthResult,
    PropagationLabel,
)

if TYPE_CHECKING:
    from contracts.interfaces import BenchmarkCase, GroundTruthResult as ContractsGTResult, SupportReport


class ProvSQLProvider(GroundTruthProvider):
    """
    Ground-truth provider backed by a ProvSQL provenance artifact.

    The provenance_artifact dict must have a "propagated_pairs" key whose
    value is a list of [source_column, target_column] pairs that ProvSQL
    determined to be PROPAGATED for the run under examination.

    Example artifact (produced by the ProvSQL spike or a future Docker run):
    {
        "case_id": "W03_case_when",
        "run_id": "run-001",
        "propagated_pairs": [
            ["employees_a.country", "out_adjusted.adjusted_salary"],
            ["employees_a.salary",  "out_adjusted.adjusted_salary"]
        ],
        "provsql_version": "1.4.0",
        "query_hash": "<sha256>"
    }

    NOTE: ProvSQL is not currently installable in this environment.
    See SPIKE_REPORT.md. This class is kept so it can be activated when
    Docker or WSL2 becomes available without changing any other code.
    """

    name = "provsql"

    def __init__(
        self,
        provenance_artifact: dict[str, Any],
        version: str = "provsql-1.4.0",
    ) -> None:
        self.provenance_artifact = provenance_artifact
        self.version = version

    # ------------------------------------------------------------------
    # research.ground_truth.provider.GroundTruthProvider (ABC interface)
    # ------------------------------------------------------------------

    def determine(
        self,
        source_column: str,
        target_column: str,
    ) -> GroundTruthResult:
        """Return PROPAGATED if ProvSQL listed this pair; NOT_PROPAGATED otherwise."""
        propagated_pairs = {
            (pair[0], pair[1])
            for pair in self.provenance_artifact.get("propagated_pairs", [])
        }
        label = (
            PropagationLabel.PROPAGATED
            if (source_column, target_column) in propagated_pairs
            else PropagationLabel.NOT_PROPAGATED
        )

        canonical = json.dumps(
            self.provenance_artifact, sort_keys=True, separators=(",", ":")
        )
        artifact_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return GroundTruthResult(
            source_column=source_column,
            target_column=target_column,
            label=label,
            provider="provsql",
            version=self.version,
            artifact_hash=artifact_hash,
        )

    # ------------------------------------------------------------------
    # contracts.interfaces.GroundTruthProvider (Protocol interface)
    # ------------------------------------------------------------------

    def supports(self, case: "BenchmarkCase") -> "SupportReport":
        """Supported only when the artifact contains a propagated_pairs list."""
        from contracts.interfaces import SupportReport  # local import

        has_pairs = isinstance(
            self.provenance_artifact.get("propagated_pairs"), list
        )
        if not has_pairs:
            return SupportReport(
                supported=False,
                reasons=("ProvSQL artifact missing 'propagated_pairs' key.",),
            )
        return SupportReport(
            supported=True,
            reasons=("ProvSQL provenance artifact present with propagated_pairs.",),
        )

    def compute(
        self,
        case: "BenchmarkCase",
        run_id: str,
    ) -> "ContractsGTResult":
        """
        Produce a contracts-shaped GroundTruthResult from the ProvSQL artifact.

        Only PROPAGATED pairs from the artifact are included as records; pairs
        absent from the artifact are NOT_PROPAGATED by the closed-world
        assumption of ProvSQL where-provenance.
        """
        from contracts.interfaces import GroundTruthResult as ContractsGTResult  # local import

        propagated_pairs = [
            (pair[0], pair[1])
            for pair in self.provenance_artifact.get("propagated_pairs", [])
        ]

        records: list[GroundTruthRecord] = []
        for source_col, target_col in propagated_pairs:
            dep_key = DependencyKey(
                run_id=run_id,
                source_column_id=source_col,
                target_column_id=target_col,
                granularity=Granularity.COLUMN,
                temporal_context=TemporalContext(),
            )
            records.append(
                GroundTruthRecord(
                    key=dep_key,
                    label=TruthLabel.PROPAGATED,
                    mechanism="provsql",
                    provider_version=self.version,
                    provenance_ref=f"case:{case.case_id}:run:{run_id}:provsql",
                    is_mock=False,
                )
            )

        canonical = json.dumps(
            {
                "provider": "provsql",
                "version": self.version,
                "artifact": self.provenance_artifact,
                "run_id": run_id,
                "case_id": case.case_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        artifact_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return ContractsGTResult(
            records=tuple(records),
            status="SUPPORTED",
            unsupported_reasons=(),
            artifact_hash=artifact_hash,
        )
