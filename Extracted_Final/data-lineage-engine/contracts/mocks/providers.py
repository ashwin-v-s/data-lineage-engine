"""In-memory mock providers. Every output is labelled is_mock and is PLUMBING, never a finding."""
from __future__ import annotations

from typing import Sequence

from contracts.interfaces import (
    BenchmarkCase, GroundTruthResult, RawEvent, RuntimeExtraction, SchemaSnapshot, StaticExtraction, SupportReport,
)
from contracts.types import ParserStatus

from .loaders import load_case, load_truth


class MockStaticLineageProvider:
    def __init__(self, fixture: str = "w03_case_when") -> None:
        self._fixture = fixture

    def extract(self, sql: str, schema: SchemaSnapshot, dialect: str = "postgres") -> StaticExtraction:
        _, static, _ = load_case(self._fixture)
        return StaticExtraction(tuple(static), ("MOCK: canned fixture, SQL was not parsed",), ParserStatus.SUPPORTED)


class MockRuntimeEvidenceProvider:
    def __init__(self, fixture: str = "w03_case_when") -> None:
        self._fixture = fixture

    def normalize(self, run_id: str, raw_events: Sequence[RawEvent]) -> RuntimeExtraction:
        _, _, runtime = load_case(self._fixture)
        return RuntimeExtraction(tuple(r for r in runtime if r.key.run_id == run_id), ("MOCK: canned fixture",))


class MockGroundTruthProvider:
    name = "mock_hand_derived"
    version = "0"

    def __init__(self, fixture: str = "w03_case_when") -> None:
        self._fixture = fixture

    def supports(self, case: BenchmarkCase) -> SupportReport:
        return SupportReport(True, ("MOCK",))

    def compute(self, case: BenchmarkCase, run_id: str) -> GroundTruthResult:
        recs = tuple(r for r in load_truth(self._fixture) if r.key.run_id == run_id)
        return GroundTruthResult(recs, "SUPPORTED", (), "mock")
