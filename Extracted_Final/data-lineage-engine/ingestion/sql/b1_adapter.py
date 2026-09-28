"""
M1: B1 Baseline Adapter

Thin wrapper to integrate M1's SQLGlotLineageProvider with the B1StaticOnly baseline.
Provides B1 input from real SQL extraction (not mock data).

Status: PROVISIONAL. Depends on M1's StaticLineageProvider implementation.
"""

from typing import TYPE_CHECKING, Sequence, Tuple

from contracts.evidence import PredictorInput, StaticEvidence
from contracts.interfaces import SchemaSnapshot, StaticLineageProvider
from contracts.types import DependencyKey, ParserStatus, TemporalContext

if TYPE_CHECKING:
    pass


def extract_static_evidence(
    sql: str,
    schema: SchemaSnapshot,
    dialect: str = "postgres",
    provider: StaticLineageProvider | None = None,
) -> Tuple[StaticEvidence, ...]:
    """Extract static evidence from SQL using M1's provider.

    Args:
        sql: SQL query text.
        schema: SchemaSnapshot with dataset, columns, fingerprint.
        dialect: SQLGlot dialect (e.g., "postgres").
        provider: StaticLineageProvider instance (defaults to SQLGlotLineageProvider).

    Returns:
        Tuple of StaticEvidence objects extracted from the SQL.
        Returns empty tuple if extraction fails (unsupported, parse error, etc.).
    """
    # Lazy import to avoid circular dependency
    if provider is None:
        from ingestion.sql import SQLGlotLineageProvider
        provider = SQLGlotLineageProvider()

    result = provider.extract(sql, schema, dialect)

    # Only return evidence if parsing succeeded
    if result.parser_status == ParserStatus.UNSUPPORTED:
        return ()

    # Filter out unsupported evidence
    return tuple(ev for ev in result.evidence if ev.parser_status == ParserStatus.SUPPORTED)


def build_predictor_input_from_static(
    static_evidence: Sequence[StaticEvidence],
    temporal_context: TemporalContext | None = None,
) -> PredictorInput:
    """Build a PredictorInput from static evidence for B1 evaluation.

    Args:
        static_evidence: Tuple/list of StaticEvidence objects from M1.
        temporal_context: Optional TemporalContext for temporal filtering.

    Returns:
        PredictorInput with static evidence and empty runtime evidence.
    """
    # Build the set of prediction keys from static evidence
    keys = set()
    for ev in static_evidence:
        if ev.source_column_id and ev.target_column_id:
            # Column-level dependency
            key = DependencyKey(
                run_id="static",  # Static evidence has no run_id
                source_column_id=ev.source_column_id,
                target_column_id=ev.target_column_id,
                granularity=ev.granularity,
                temporal_context=temporal_context or TemporalContext(valid_at=None, known_as_of=None),
            )
            keys.add(key)

    return PredictorInput(
        keys=tuple(keys),
        static_evidence=tuple(static_evidence),
        runtime_evidence=(),  # B1 ignores runtime evidence
    )


class B1Adapter:
    """M1 adapter for B1StaticOnly baseline.

    Provides a high-level interface to extract static evidence and prepare it
    for B1 evaluation without runtime or ground-truth data.

    Usage:
        adapter = B1Adapter()
        evidence = adapter.extract_static(sql, schema)
        predictor_input = adapter.build_input(evidence)
    """

    def __init__(self, provider: StaticLineageProvider | None = None):
        """Initialize the B1 adapter with a StaticLineageProvider.

        Args:
            provider: StaticLineageProvider (defaults to SQLGlotLineageProvider).
        """
        if provider is None:
            from ingestion.sql import SQLGlotLineageProvider
            provider = SQLGlotLineageProvider()
        self.provider = provider

    def extract_static(
        self,
        sql: str,
        schema: SchemaSnapshot,
        dialect: str = "postgres",
    ) -> Tuple[StaticEvidence, ...]:
        """Extract static evidence from SQL.

        Args:
            sql: SQL query text.
            schema: SchemaSnapshot.
            dialect: SQLGlot dialect.

        Returns:
            Tuple of StaticEvidence objects (empty if unsupported).
        """
        return extract_static_evidence(sql, schema, dialect, self.provider)

    def build_input(
        self,
        static_evidence: Sequence[StaticEvidence],
        temporal_context: TemporalContext | None = None,
    ) -> PredictorInput:
        """Build a PredictorInput from static evidence.

        Args:
            static_evidence: Output from extract_static().
            temporal_context: Optional temporal context.

        Returns:
            PredictorInput ready for B1 inference.
        """
        return build_predictor_input_from_static(static_evidence, temporal_context)

    def extract_and_build(
        self,
        sql: str,
        schema: SchemaSnapshot,
        dialect: str = "postgres",
        temporal_context: TemporalContext | None = None,
    ) -> PredictorInput:
        """Extract static evidence and build a PredictorInput in one step.

        Args:
            sql: SQL query text.
            schema: SchemaSnapshot.
            dialect: SQLGlot dialect.
            temporal_context: Optional temporal context.

        Returns:
            PredictorInput ready for B1 inference.
        """
        evidence = self.extract_static(sql, schema, dialect)
        return self.build_input(evidence, temporal_context)


__all__ = [
    "B1Adapter",
    "extract_static_evidence",
    "build_predictor_input_from_static",
]
