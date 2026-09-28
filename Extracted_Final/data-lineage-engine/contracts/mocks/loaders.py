"""JSON <-> dataclass helpers for fixtures. Everything loaded from contracts/fixtures is a MOCK."""
from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

from contracts.evidence import RuntimeEvidence, StaticEvidence
from contracts.truth import GroundTruthRecord, TruthLabel
from contracts.types import (
    CoverageMode, CoverageVector, DependencyKey, EvidenceType, Granularity, ParserStatus, TemporalContext,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def to_jsonable(o: Any) -> Any:
    if isinstance(o, Enum):
        return o.value
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {f.name: to_jsonable(getattr(o, f.name)) for f in dataclasses.fields(o)}
    if isinstance(o, (tuple, list)):
        return [to_jsonable(x) for x in o]
    return o


def key_from_dict(d: Dict[str, Any]) -> DependencyKey:
    tc = d.get("temporal_context") or {}
    return DependencyKey(d["run_id"], d["source_column_id"], d["target_column_id"], Granularity(d["granularity"]),
                         TemporalContext(tc.get("valid_at"), tc.get("known_as_of")))


def coverage_from_dict(d: Dict[str, Any]) -> CoverageVector:
    return CoverageVector(d["run_covered"], d["operator_covered"], d["source_dataset_covered"], d["target_dataset_covered"],
                          tuple(d["source_columns_covered"]), tuple(d["target_columns_covered"]), d["branches_covered"],
                          CoverageMode(d["coverage_mode"]), ParserStatus(d["parser_status"]))


def static_from_dict(d: Dict[str, Any]) -> StaticEvidence:
    return StaticEvidence(d["evidence_id"], d["source_dataset_id"], d["target_dataset_id"], d.get("source_column_id"),
                          d.get("target_column_id"), Granularity(d["granularity"]), d["operator"],
                          d["expression_fingerprint"], d["query_fingerprint"], d["schema_fingerprint"],
                          ParserStatus(d["parser_status"]), tuple(d.get("unsupported_constructs", ())),
                          tuple(d.get("diagnostics", ())), d.get("is_mock", False))


def runtime_from_dict(d: Dict[str, Any]) -> RuntimeEvidence:
    return RuntimeEvidence(d["evidence_id"], EvidenceType(d["evidence_type"]), key_from_dict(d["key"]), d["source_system"],
                           d["event_time"], coverage_from_dict(d["coverage"]), d["raw_payload_hash"], d.get("is_mock", False))


def truth_from_dict(d: Dict[str, Any]) -> GroundTruthRecord:
    return GroundTruthRecord(key_from_dict(d["key"]), TruthLabel(d["label"]), d["mechanism"], d["provider_version"],
                             d["provenance_ref"], d.get("is_mock", False))


def load_case(name: str) -> Tuple[List[DependencyKey], List[StaticEvidence], List[RuntimeEvidence]]:
    data = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf8"))
    return ([key_from_dict(k) for k in data["keys"]], [static_from_dict(s) for s in data["static_evidence"]],
            [runtime_from_dict(r) for r in data["runtime_evidence"]])


def load_truth(name: str) -> List[GroundTruthRecord]:
    data = json.loads((FIXTURE_DIR / f"{name}.truth.json").read_text(encoding="utf8"))
    return [truth_from_dict(r) for r in data["records"]]
