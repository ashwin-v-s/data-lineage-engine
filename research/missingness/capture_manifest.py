"""Capture manifest — what the modelled capture layer claims to instrument.

D-09 decision: the CoverageVector seen by the reasoning engine is derived from
this manifest, NOT from the MCAR simulator's removed-event set.

The manifest is set BEFORE the loss draw.  It represents the instrumentation
configuration of the modelled capture layer.  The MCAR simulator then removes
events independently; the manifest does not change.

Status: PROVISIONAL.  Standard library only.

UNRESOLVED ZERO-ARRIVAL SEAM (see docs/M4_DAY2_MCAR.md):
  When the manifest says a scope is instrumented but zero events survive the
  loss draw, the downstream behaviour (POSSIBLE vs REFUTED_FOR_RUN vs
  something else) is NOT YET DECIDED by the team.  This module does not encode
  that decision.  The caller that translates a manifest + surviving events into
  RuntimeEvidence objects must handle this seam and must NOT use the simulator's
  removed-event set to resolve it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Tuple

from contracts.types import CoverageMode, CoverageVector, ParserStatus


@dataclass(frozen=True)
class CaptureManifest:
    """Describes what the modelled capture layer covers for one benchmark run.

    This object is constructed from instrumentation configuration, not from
    observed events and not from the simulator's removal draw.

    Fields mirror the structure of CoverageVector so that a covered manifest
    scope can be translated into a CoverageVector when building RuntimeEvidence
    for surviving events.  The translation is the caller's responsibility.

    run_id:                  The benchmark run this manifest applies to.
    instrumented_source_cols: Source column IDs the capture layer covers.
    instrumented_target_cols: Target column IDs the capture layer covers.
    operator_covered:        Whether the operator is in scope.
    source_dataset_covered:  Whether the source dataset is in scope.
    target_dataset_covered:  Whether the target dataset is in scope.
    branches_covered:        Whether conditional branches are in scope.
    parser_status:           Static-analysis quality for this scope.
    notes:                   Optional free-text annotation.
    """

    run_id: str
    instrumented_source_cols: FrozenSet[str]
    instrumented_target_cols: FrozenSet[str]
    operator_covered: bool = True
    source_dataset_covered: bool = True
    target_dataset_covered: bool = True
    branches_covered: bool = True
    parser_status: ParserStatus = ParserStatus.SUPPORTED
    notes: str = ""

    def coverage_vector_for(
        self,
        source_col: str,
        target_col: str,
    ) -> CoverageVector:
        """Build a CoverageVector from the manifest for one (source, target) pair.

        This is used to attach coverage to surviving RuntimeEvidence objects.
        It reflects what the capture layer claims to have covered BEFORE the
        loss draw; it does NOT reflect what the loss simulator actually removed.

        The resulting CoverageVector has coverage_mode=RUNTIME (the only mode
        that satisfies is_complete_for()).

        The caller is responsible for determining whether to produce a positive
        or negative evaluation based on whether a surviving event exists.
        The zero-arrival case (manifest says covered, no event survived) is
        NOT handled here — see docs/M4_DAY2_MCAR.md for the unresolved seam.
        """
        src_covered = source_col in self.instrumented_source_cols
        tgt_covered = target_col in self.instrumented_target_cols
        run_covered = True  # the manifest is per-run; existence of a manifest means the run is covered

        return CoverageVector(
            run_covered=run_covered,
            operator_covered=self.operator_covered,
            source_dataset_covered=self.source_dataset_covered,
            target_dataset_covered=self.target_dataset_covered,
            source_columns_covered=(source_col,) if src_covered else (),
            target_columns_covered=(target_col,) if tgt_covered else (),
            branches_covered=self.branches_covered,
            coverage_mode=CoverageMode.RUNTIME,
            parser_status=self.parser_status,
        )

    def covers(self, source_col: str, target_col: str) -> bool:
        """True if the manifest instruments both columns of this dependency."""
        return (
            source_col in self.instrumented_source_cols
            and target_col in self.instrumented_target_cols
        )
