"""Regenerates contracts/fixtures/w03_case_when*.json (MOCK, illustrative CASE WHEN motif from Pack Section 21).

Runs:  A = US rows, full evidence | B = no US rows, full evidence | C = no US rows, evidence lost
       D = US rows, evidence lost
Truth uses INFLUENCE semantics (country contributes everywhere). The real protocol must fix this (D-11).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from contracts.evidence import RuntimeEvidence, StaticEvidence  # noqa: E402
from contracts.mocks.loaders import to_jsonable  # noqa: E402
from contracts.truth import GroundTruthRecord, TruthLabel  # noqa: E402
from contracts.types import (  # noqa: E402
    CoverageMode, CoverageVector, DependencyKey, EvidenceType, Granularity, ParserStatus,
)

COUNTRY, SALARY, OUT = "employees.country", "employees.salary", "out.adjusted_salary"
RUNS = ["A", "B", "C", "D"]


def key(run, src):
    return DependencyKey(f"run_{run}", src, OUT, Granularity.COLUMN)


def cov(src):
    return CoverageVector(True, True, True, True, (src,), (OUT,), True, CoverageMode.RUNTIME, ParserStatus.SUPPORTED)


static = [
    StaticEvidence(f"static_{i}", "employees", "out", src, OUT, Granularity.COLUMN, "CASE",
                   f"expr-{i}", "q-w03", "schema-w03", ParserStatus.SUPPORTED, is_mock=True)
    for i, src in enumerate([COUNTRY, SALARY])
]
runtime = []
for run in ("A", "B"):
    runtime.append(RuntimeEvidence(f"rt_{run}_country", EvidenceType.RUNTIME_POSITIVE, key(run, COUNTRY), "mock",
                                   "2026-01-01T00:00:00Z", cov(COUNTRY), f"hash-{run}-c", True))
runtime.append(RuntimeEvidence("rt_A_salary", EvidenceType.RUNTIME_POSITIVE, key("A", SALARY), "mock",
                               "2026-01-01T00:00:00Z", cov(SALARY), "hash-A-s", True))
runtime.append(RuntimeEvidence("rt_B_salary_neg", EvidenceType.RUNTIME_NEGATIVE_EVALUATION, key("B", SALARY), "mock",
                               "2026-01-01T00:00:00Z", cov(SALARY), "hash-B-s", True))
keys = [key(r, s) for r in RUNS for s in (COUNTRY, SALARY)]
salary_label = {"A": TruthLabel.PROPAGATED, "B": TruthLabel.NOT_PROPAGATED,
                "C": TruthLabel.NOT_PROPAGATED, "D": TruthLabel.PROPAGATED}
truth = [GroundTruthRecord(key(r, COUNTRY), TruthLabel.PROPAGATED, "hand_derived", "0", "fixture", True) for r in RUNS]
truth += [GroundTruthRecord(key(r, SALARY), salary_label[r], "hand_derived", "0", "fixture", True) for r in RUNS]

out = ROOT / "contracts" / "fixtures"
case = {"is_mock": True, "case_id": "W03_case_when",
        "description": "PLUMBING fixture: CASE WHEN country='US' THEN salary ELSE 0 END. Not project data.",
        "keys": to_jsonable(keys), "static_evidence": to_jsonable(static), "runtime_evidence": to_jsonable(runtime)}
(out / "w03_case_when.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf8")
(out / "w03_case_when.truth.json").write_text(
    json.dumps({"is_mock": True, "records": to_jsonable(truth)}, indent=2) + "\n", encoding="utf8")
print("fixtures written")
