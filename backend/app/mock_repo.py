"""In-memory mock repository implementing Kairos bitemporal lineage and Section 19 reasoning.

Everything here is labeled is_mock=True and PLUMBING.
It enables full API and UI testing without needing a running PostgreSQL instance.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

from contracts.evidence import PredictorInput, RuntimeEvidence, StaticEvidence
from contracts.mocks.loaders import load_case, load_truth
from contracts.types import (
    CoverageMode, CoverageVector, DependencyKey, EvidenceType, Granularity, ParserStatus, TemporalContext,
)
from research.reasoning.engine import FourStateEngine

# Locked Section 19 Canonical State Interpretations (Word-for-Word)
STATE_INTERPRETATIONS = {
    "OBSERVED": (
        "At least one source value was observed to contribute to at least one target output in this run. "
        "This does not imply contribution to every row or every run."
    ),
    "REFUTED_FOR_RUN": (
        "No propagation was established for this run under the declared complete-evaluation conditions. "
        "This is not a universal claim that the dependency can never occur."
    ),
    "POSSIBLE": (
        "Static analysis permits this dependency, but available evidence is insufficient to establish "
        "whether propagation occurred in this run."
    ),
    "UNKNOWN": (
        "Kairos cannot safely evaluate this dependency because relevant semantics, identity, "
        "schema or instrumentation is unsupported or ambiguous."
    ),
}


def _parse_iso(s: Optional[str]) -> Optional[datetime.datetime]:
    if not s:
        return None
    try:
        # replace Z with +00:00 for fromisoformat compatibility
        cleaned = s.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _is_in_half_open(t: Optional[datetime.datetime], lo: Optional[datetime.datetime], hi: Optional[datetime.datetime]) -> bool:
    if t is None:
        return True  # If no query time specified, treat as current
    if lo is not None and t < lo:
        return False
    if hi is not None and t >= hi:
        return False
    return True


class MockLineageRepository:
    """Mock repository providing bitemporal graph navigation and 4-state reasoning."""

    def __init__(self) -> None:
        self.engine = FourStateEngine()
        self._init_entities()
        self._init_edges()
        self._init_runs()

    def _init_entities(self) -> None:
        self.entities = {
            "orders_fact": {
                "id": "e3b1c4a0-7f28-4c8d-965a-8d7b32c694a1",
                "name": "orders_fact",
                "entity_type": "TABLE",
                "namespace": "public",
                "schema_version": "v2.1",
                "columns": ["order_id", "customer_id", "order_date", "gross_amount", "discount", "net_revenue"],
                "metadata": {
                    "partition_strategy": "order_date [DAILY]",
                    "row_count_aug15": 1120410,
                    "row_count_current": 1489204,
                    "target_column": "net_revenue",
                    "column_type": "NUMERIC(14,2)",
                },
            },
            "stg_customer_orders": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "name": "stg_customer_orders",
                "entity_type": "VIEW",
                "namespace": "staging",
                "schema_version": "v2.0",
                "columns": ["order_id", "customer_id", "order_time", "gross_amount", "discount"],
                "metadata": {
                    "source_table": "raw.order_events",
                    "effective_from": "2026-09-01T00:00:00Z",
                },
            },
            "dim_customer_demographics": {
                "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
                "name": "dim_customer_demographics",
                "entity_type": "TABLE",
                "namespace": "analytics",
                "schema_version": "v2.1",
                "columns": ["customer_id", "country", "segment", "credit_tier"],
                "metadata": {"row_count": 450000},
            },
            "employees.salary": {
                "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
                "name": "employees.salary",
                "entity_type": "COLUMN",
                "namespace": "hr",
                "schema_version": "v1.0",
                "columns": ["salary"],
                "metadata": {"feeds": "out.adjusted_salary"},
            },
            "currency_rates_feed": {
                "id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
                "name": "currency_rates_feed",
                "entity_type": "STREAM",
                "namespace": "external",
                "schema_version": "v1.4",
                "columns": ["currency", "rate", "timestamp"],
                "metadata": {"stream_source": "kafka.market.fx"},
            },
            "monthly_revenue_summary": {
                "id": "d3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a",
                "name": "monthly_revenue_summary",
                "entity_type": "TABLE",
                "namespace": "finance",
                "schema_version": "v2.1",
                "columns": ["month_year", "total_orders", "monthly_total"],
                "metadata": {"type": "AGGREGATE"},
            },
            "reporting_exec_dashboard": {
                "id": "e4f5a6b7-c8d9-4e0f-1a2b-3c4d5e6f7a8b",
                "name": "reporting_exec_dashboard",
                "entity_type": "JOB",
                "namespace": "bi_pipeline",
                "schema_version": "v1.2",
                "columns": [],
                "metadata": {"pipeline_job_id": 882, "schedule": "HOURLY"},
            },
        }

    def _init_edges(self) -> None:
        # Full topological edge set with bitemporal intervals
        # [valid_from, valid_to) and [tx_from, tx_to)
        self.edges = [
            {
                "edge_id": "edge_dim_to_fact",
                "source_id": "dim_customer_demographics",
                "target_id": "orders_fact",
                "source_column": "customer_id",
                "target_column": "customer_id",
                "relationship_type": "DERIVED_FROM",
                "granularity": "COLUMN",
                "default_state": "POSSIBLE",
                "operator": "JOIN",
                "d14_warning": False,
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None,
                "tx_from": "2026-01-01T00:00:00Z",
                "tx_to": None,
            },
            {
                "edge_id": "edge_stg_to_fact",
                "source_id": "stg_customer_orders",
                "target_id": "orders_fact",
                "source_column": "gross_amount",
                "target_column": "net_revenue",
                "relationship_type": "DERIVED_FROM",
                "granularity": "COLUMN",
                "default_state": "OBSERVED",
                "operator": "PROJECTION_ARITHMETIC",
                # Note: this edge has D-14 warning active and valid window starts 2026-09-01
                "d14_warning": True,
                "valid_from": "2026-09-01T00:00:00Z",
                "valid_to": None,
                "tx_from": "2026-09-01T10:00:00Z",
                "tx_to": None,
            },
            {
                "edge_id": "edge_salary_to_adjusted",
                "source_id": "employees.salary",
                "target_id": "orders_fact",
                "source_column": "salary",
                "target_column": "adjusted_salary",
                "relationship_type": "DERIVED_FROM",
                "granularity": "COLUMN",
                "default_state": "REFUTED_FOR_RUN",
                "operator": "CASE_WHEN",
                "d14_warning": False,
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None,
                "tx_from": "2026-01-01T00:00:00Z",
                "tx_to": None,
            },
            {
                "edge_id": "edge_rates_to_fact",
                "source_id": "currency_rates_feed",
                "target_id": "orders_fact",
                "source_column": "rate",
                "target_column": "net_revenue",
                "relationship_type": "READS",
                "granularity": "COLUMN",
                "default_state": "UNKNOWN",
                "operator": "STREAM_LOOKUP",
                "d14_warning": False,
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None,
                "tx_from": "2026-01-01T00:00:00Z",
                "tx_to": None,
            },
            {
                "edge_id": "edge_fact_to_monthly",
                "source_id": "orders_fact",
                "target_id": "monthly_revenue_summary",
                "source_column": "net_revenue",
                "target_column": "monthly_total",
                "relationship_type": "DERIVED_FROM",
                "granularity": "COLUMN",
                "default_state": "OBSERVED",
                "operator": "SUM_GROUP_BY",
                "d14_warning": False,
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None,
                "tx_from": "2026-01-01T00:00:00Z",
                "tx_to": None,
            },
            {
                "edge_id": "edge_fact_to_dashboard",
                "source_id": "orders_fact",
                "target_id": "reporting_exec_dashboard",
                "source_column": "net_revenue",
                "target_column": "dashboard_kpi",
                "relationship_type": "WRITES",
                "granularity": "COLUMN",
                "default_state": "POSSIBLE",
                "operator": "BATCH_EXTRACT",
                "d14_warning": False,
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None,
                "tx_from": "2026-01-01T00:00:00Z",
                "tx_to": None,
            },
        ]

    def _init_runs(self) -> None:
        self.runs = {
            "run_2026_09_23_093214": {
                "run_id": "run_2026_09_23_093214",
                "job_name": "clean_and_aggregate_orders",
                "namespace": "analytics_prod",
                "started_at": "2026-09-23T09:30:00Z",
                "completed_at": "2026-09-23T09:32:14Z",
                "status": "COMPLETED",
                "event_count": 5,
            },
            "run_A": {
                "run_id": "run_A",
                "job_name": "w03_case_when_demo",
                "namespace": "mock_cases",
                "started_at": "2026-01-01T00:00:00Z",
                "completed_at": "2026-01-01T00:01:00Z",
                "status": "COMPLETED",
                "event_count": 2,
            },
            "run_B": {
                "run_id": "run_B",
                "job_name": "w03_case_when_demo",
                "namespace": "mock_cases",
                "started_at": "2026-01-02T00:00:00Z",
                "completed_at": "2026-01-02T00:01:00Z",
                "status": "COMPLETED",
                "event_count": 2,
            },
            "run_C": {
                "run_id": "run_C",
                "job_name": "w03_case_when_demo",
                "namespace": "mock_cases",
                "started_at": "2026-01-03T00:00:00Z",
                "completed_at": "2026-01-03T00:01:00Z",
                "status": "COMPLETED",
                "event_count": 0,
            },
            "run_D": {
                "run_id": "run_D",
                "job_name": "w03_case_when_demo",
                "namespace": "mock_cases",
                "started_at": "2026-01-04T00:00:00Z",
                "completed_at": "2026-01-04T00:01:00Z",
                "status": "COMPLETED",
                "event_count": 0,
            },
        }

    # -------------------------------------------------------------------------
    # Search API
    # -------------------------------------------------------------------------
    def search(self, query: str, entity_type: Optional[str] = None, limit: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        q = (query or "").lower().strip()
        matched = []
        for e in self.entities.values():
            if entity_type and e["entity_type"].upper() != entity_type.upper():
                continue
            if not q or q in e["name"].lower() or q in e["namespace"].lower() or any(q in col.lower() for col in e.get("columns", [])):
                matched.append({
                    "id": e["id"],
                    "name": e["name"],
                    "entity_type": e["entity_type"],
                    "namespace": e["namespace"],
                    "description": f"{e['entity_type']} in {e['namespace']} schema",
                    "column_count": len(e.get("columns", [])),
                    "row_count": e.get("metadata", {}).get("row_count") or e.get("metadata", {}).get("row_count_current"),
                })
        return matched[:limit], len(matched)

    # -------------------------------------------------------------------------
    # Lineage Queries with Bitemporal Filtering
    # -------------------------------------------------------------------------
    def get_lineage(
        self,
        anchor_entity: str,
        direction: str = "both",  # "both", "upstream", "downstream"
        depth: int = 3,
        as_of: Optional[str] = None,
        recorded_as_of: Optional[str] = None,
        granularity: str = "COLUMN",
    ) -> Dict[str, Any]:
        t_v = _parse_iso(as_of)
        t_k = _parse_iso(recorded_as_of)

        # Match anchor entity either by ID or Name
        anchor = None
        for eid, e in self.entities.items():
            if eid == anchor_entity or e["name"] == anchor_entity or e["id"] == anchor_entity:
                anchor = eid
                break
        if not anchor:
            anchor = "orders_fact"  # Default fallback to center anchor

        filtered_edges = []
        active_node_ids = {anchor}

        for edge in self.edges:
            # Direction check
            is_upstream = edge["target_id"] == anchor
            is_downstream = edge["source_id"] == anchor

            if direction == "upstream" and not is_upstream:
                continue
            if direction == "downstream" and not is_downstream:
                continue
            if direction == "both" and not (is_upstream or is_downstream):
                continue

            # Bitemporal interval check:
            # valid_from <= as_of < valid_to AND tx_from <= recorded_as_of < tx_to
            v_lo = _parse_iso(edge["valid_from"])
            v_hi = _parse_iso(edge["valid_to"])
            tx_lo = _parse_iso(edge["tx_from"])
            tx_hi = _parse_iso(edge["tx_to"])

            valid_in_range = _is_in_half_open(t_v, v_lo, v_hi)
            tx_in_range = _is_in_half_open(t_k, tx_lo, tx_hi)

            # Determine dynamic reasoning state under temporal slice
            state = edge["default_state"]
            if not valid_in_range:
                # If queried at a time before this edge became valid, revert to UNKNOWN
                state = "UNKNOWN"
            elif not tx_in_range:
                state = "UNKNOWN"

            edge_copy = dict(edge)
            edge_copy["reasoning_state"] = state
            edge_copy["temporal_range"] = {
                "valid_from": edge["valid_from"],
                "valid_to": edge["valid_to"],
                "tx_from": edge["tx_from"],
                "tx_to": edge["tx_to"],
            }
            filtered_edges.append(edge_copy)
            active_node_ids.add(edge["source_id"])
            active_node_ids.add(edge["target_id"])

        # Collect nodes
        nodes = []
        for nid in active_node_ids:
            if nid in self.entities:
                ent = self.entities[nid]
                nodes.append({
                    "id": ent["id"],
                    "name": ent["name"],
                    "entity_type": ent["entity_type"],
                    "namespace": ent["namespace"],
                    "schema_version": ent.get("schema_version"),
                    "columns": ent.get("columns", []),
                    "metadata": ent.get("metadata", {}),
                })

        return {
            "anchor_entity_id": self.entities[anchor]["id"],
            "nodes": nodes,
            "edges": filtered_edges,
            "temporal_context": {"as_of": as_of, "recorded_as_of": recorded_as_of},
            "granularity": granularity,
            "depth": depth,
            "truncated": False,
        }

    # -------------------------------------------------------------------------
    # Dependency Reasoning (FourStateEngine + Mock Fixtures)
    # -------------------------------------------------------------------------
    def evaluate_dependency(
        self,
        run_id: str,
        source: str,
        target: str,
        as_of: Optional[str] = None,
        recorded_as_of: Optional[str] = None,
    ) -> Dict[str, Any]:
        # First check fixture runs (w03_case_when)
        keys, static, runtime = load_case("w03_case_when")
        wanted_keys = [
            k for k in keys
            if (k.run_id == run_id and (k.source_column_id == source or source in k.source_column_id) and
                (k.target_column_id == target or target in k.target_column_id))
        ]

        t_v = _parse_iso(as_of)

        # If matching fixture exists
        if wanted_keys:
            pred = self.engine.infer(PredictorInput(tuple(wanted_keys), tuple(static), tuple(runtime)))[0]
            state_val = pred.state.value
            rule_id = pred.rule_id
            explanation = pred.explanation
            ev_ids = list(pred.evidence_ids)
        else:
            # Match cockpit topology (e.g. stg_customer_orders -> orders_fact)
            matched_edge = None
            for e in self.edges:
                if (e["source_id"] == source or e.get("source_column") == source) and \
                   (e["target_id"] == target or e.get("target_column") == target):
                    matched_edge = e
                    break

            if matched_edge:
                v_lo = _parse_iso(matched_edge["valid_from"])
                v_hi = _parse_iso(matched_edge["valid_to"])
                if not _is_in_half_open(t_v, v_lo, v_hi):
                    state_val = "UNKNOWN"
                    rule_id = "R5"
                    explanation = f"Rule R5: No observation recorded for {run_id} at Valid Time {as_of}."
                    ev_ids = []
                else:
                    state_val = matched_edge["default_state"]
                    rule_id = "R2" if state_val == "OBSERVED" else ("R3" if state_val == "REFUTED_FOR_RUN" else "R4")
                    explanation = f"Evaluated under rule {rule_id}"
                    ev_ids = [f"EV-{run_id}-01", f"EV-{run_id}-02"]
            else:
                # Default fallback rule R4 / R5
                state_val = "POSSIBLE"
                rule_id = "R4"
                explanation = "Static candidate without positive or negative runtime evidence"
                ev_ids = [f"EV-{run_id}-01"]

        # Warnings according to Section 17 & 19
        warnings = []
        if state_val == "POSSIBLE":
            warnings.append("NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE")
        if source == "stg_customer_orders" or "stg" in source:
            warnings.append("D-14_TIME_WINDOW_UNKNOWN")

        return {
            "run_id": run_id,
            "source": {"column_id": f"col_{source}", "display": source},
            "target": {"column_id": f"col_{target}", "display": target},
            "granularity": "COLUMN",
            "state": state_val,
            "interpretation": STATE_INTERPRETATIONS.get(state_val, STATE_INTERPRETATIONS["UNKNOWN"]),
            "temporal_context": {"as_of": as_of, "recorded_as_of": recorded_as_of},
            "coverage": {
                "run_covered": True,
                "operator_covered": True if state_val in ("OBSERVED", "REFUTED_FOR_RUN") else False,
                "source_dataset_covered": True,
                "target_dataset_covered": True,
                "source_columns_covered": [source],
                "target_columns_covered": [target],
                "branches_covered": True if state_val == "REFUTED_FOR_RUN" else False,
                "coverage_mode": "runtime",
                "parser_status": "SUPPORTED",
            },
            "evidence": [
                {
                    "evidence_id": eid,
                    "type": "RUNTIME_POSITIVE" if state_val == "OBSERVED" else "STATIC_DEPENDENCY",
                    "source_system": "openlineage" if state_val == "OBSERVED" else "sqlglot",
                    "event_time": "2026-09-23T09:32:14.882Z",
                    "raw_payload_hash": "sha256:4a8e32901b",
                }
                for eid in ev_ids
            ],
            "reasoning": {"engine_version": "1.0.0", "rule_id": rule_id},
            "warnings": warnings,
            "is_mock": True,
        }

    # -------------------------------------------------------------------------
    # Evidence Dossier
    # -------------------------------------------------------------------------
    def get_evidence(self, dependency: str) -> List[Dict[str, Any]]:
        return [
            {
                "evidence_id": "EV-093214-01",
                "evidence_type": "STATIC_AST",
                "source_system": "sqlglot",
                "event_time": "2026-09-23T09:30:00Z",
                "payload_hash": "sha256:88fa2b109e",
                "details": {
                    "ast": "SELECT (stg.gross_amount - stg.discount) AS net_revenue FROM stg_customer_orders",
                    "visitor_match": "gross_amount (AstLineageVisitor:210)",
                },
            },
            {
                "evidence_id": "EV-093214-02",
                "evidence_type": "RUNTIME_PROBE",
                "source_system": "openlineage",
                "event_time": "2026-09-23T09:32:14.882Z",
                "payload_hash": "sha256:77cd9101ff",
                "details": {
                    "parity": "Row parity confirmed: 1,489,204 rows evaluated with delta non-zero.",
                    "probe_status": "SUCCESS",
                },
            },
            {
                "evidence_id": "EV-093214-03",
                "evidence_type": "DIALECT_PROOF",
                "source_system": "sqlglot",
                "event_time": "2026-09-23T09:30:00Z",
                "payload_hash": "sha256:33bc9199aa",
                "details": {
                    "dialect": "PostgreSQL dialect strictness confirmed without coercion errors.",
                },
            },
        ]

    # -------------------------------------------------------------------------
    # Benchmark Evaluation Oracle (Exposed ONLY in Hazard Mode)
    # -------------------------------------------------------------------------
    def get_benchmark_oracle(self, run_id: str) -> List[Dict[str, Any]]:
        truth_records = load_truth("w03_case_when")
        filtered = [r for r in truth_records if r.key.run_id == run_id]
        if not filtered:
            # synthesize benchmark record for cockpits' run
            return [{
                "run_id": run_id,
                "source": "stg_customer_orders.gross_amount",
                "target": "orders_fact.net_revenue",
                "expected_truth_label": "PROPAGATED",
                "inferred_state": "OBSERVED",
                "matches": True,
                "oracle_hash": "bench:oracle:9940ac12e",
            }]
        return [
            {
                "run_id": r.key.run_id,
                "source": r.key.source_column_id,
                "target": r.key.target_column_id,
                "expected_truth_label": r.label.value,
                "inferred_state": "REFUTED_FOR_RUN" if r.label.value == "NOT_PROPAGATED" else "OBSERVED",
                "matches": True,
                "oracle_hash": "bench:oracle:w03_case_when",
            }
            for r in filtered
        ]


# Global singleton instance for the FastAPI application
mock_repo = MockLineageRepository()
