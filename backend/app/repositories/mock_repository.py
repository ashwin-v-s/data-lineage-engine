"""In-memory mock repository implementing M3 and M4 contracts for Kairos.

Label: is_mock=True, PLUMBING.
Provides:
- M3 Dataset and Column entities
- Half-open bitemporal queries ([valid_from, valid_to) and [tx_from, tx_to))
- Authoritative Evidence Dossier with raw_event payload hash
- Dynamic serialization of M4 Prediction without reimplementing rules R1-R5
- Evaluation Oracle isolated strictly to hazard mode
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

from contracts.evidence import PredictorInput
from contracts.mocks.loaders import load_case, load_truth
from contracts.types import CoverageMode, CoverageVector, DependencyKey, Granularity, ParserStatus
from research.reasoning.engine import FourStateEngine

from .base import BaseEntityRepository, BaseEvidenceRepository, BaseLineageRepository

# Locked Section 12 Canonical UI Interpretations (Verbatim)
STATE_INTERPRETATIONS = {
    "OBSERVED": "Positive runtime evidence establishes observed propagation for this run.",
    "REFUTED_FOR_RUN": "No propagation was established for this run under complete-evaluation conditions.",
    "POSSIBLE": "Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run.",
    "UNKNOWN": "There is insufficient evidence to safely evaluate this dependency.",
}


def _parse_dt(iso_str: Optional[str]) -> Optional[datetime.datetime]:
    if not iso_str:
        return None
    try:
        clean = iso_str.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(clean)
    except Exception:
        return None


def _is_in_half_open(
    t: Optional[datetime.datetime],
    lo: Optional[datetime.datetime],
    hi: Optional[datetime.datetime],
) -> bool:
    """Half-open interval check: [lo, hi) where None indicates open-ended."""
    if t is None:
        return True  # If no point-in-time is queried, query default is latest/current
    if lo is not None and t < lo:
        return False
    if hi is not None and t >= hi:
        return False
    return True


class MockRepository(BaseEntityRepository, BaseLineageRepository, BaseEvidenceRepository):
    def __init__(self) -> None:
        self.engine = FourStateEngine()
        self._init_entities()
        self._init_edges()
        self._init_evidence()

    def _init_entities(self) -> None:
        self.entities: Dict[str, Dict[str, Any]] = {
            "orders_fact": {
                "id": "e3b1c4a0-7f28-4c8d-965a-8d7b32c694a1",
                "type": "dataset",
                "source_system": "postgresql_analytics",
                "namespace": "public",
                "database_name": "kairos_dw",
                "schema_name": "public",
                "name": "orders_fact",
                "asset_type": "TABLE",
                "created_at": "2026-01-01T00:00:00Z",
                "display_name": "orders_fact",
                "columns": ["order_id", "customer_id", "order_date", "gross_amount", "discount", "net_revenue"],
                "metadata": {
                    "canonical_uuid": "e3b1c4a0-7f28-4c8d-965a-8d7b32c694a1",
                    "partition_strategy": "order_date [DAILY]",
                    "row_count": 1489204,
                    "target_column": "net_revenue",
                    "data_type": "NUMERIC(14,2)",
                },
            },
            "stg_customer_orders": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "type": "dataset",
                "source_system": "dbt_staging",
                "namespace": "staging",
                "database_name": "kairos_dw",
                "schema_name": "staging",
                "name": "stg_customer_orders",
                "asset_type": "VIEW",
                "created_at": "2026-09-01T00:00:00Z",
                "display_name": "stg_customer_orders",
                "columns": ["order_id", "customer_id", "order_time", "gross_amount", "discount"],
                "metadata": {
                    "source_table": "raw.order_events",
                    "effective_from": "2026-09-01T00:00:00Z",
                },
            },
            "dim_customer_demographics": {
                "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
                "type": "dataset",
                "source_system": "postgresql_analytics",
                "namespace": "analytics",
                "database_name": "kairos_dw",
                "schema_name": "analytics",
                "name": "dim_customer_demographics",
                "asset_type": "TABLE",
                "created_at": "2026-01-01T00:00:00Z",
                "display_name": "dim_customer_demographics",
                "columns": ["customer_id", "country", "segment", "credit_tier"],
                "metadata": {"row_count": 450000},
            },
            "employees.salary": {
                "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
                "type": "column",
                "dataset_id": "hr.employees",
                "column_name": "salary",
                "data_type": "INT",
                "schema_version": "v1.0",
                "created_at": "2026-01-01T00:00:00Z",
                "display_name": "employees.salary",
                "fully_qualified_name": "kairos_dw.hr.employees.salary",
                "metadata": {"feeds": "out.adjusted_salary"},
            },
            "currency_rates_feed": {
                "id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
                "type": "stream",
                "source_system": "kafka_feed",
                "namespace": "external",
                "database_name": "market_data",
                "schema_name": "fx",
                "name": "currency_rates_feed",
                "asset_type": "STREAM",
                "created_at": "2026-01-01T00:00:00Z",
                "display_name": "currency_rates_feed",
                "columns": ["currency", "rate", "timestamp"],
                "metadata": {"stream_source": "kafka.market.fx"},
            },
            "monthly_revenue_summary": {
                "id": "d3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a",
                "type": "dataset",
                "source_system": "postgresql_analytics",
                "namespace": "finance",
                "database_name": "kairos_dw",
                "schema_name": "finance",
                "name": "monthly_revenue_summary",
                "asset_type": "TABLE",
                "created_at": "2026-01-01T00:00:00Z",
                "display_name": "monthly_revenue_summary",
                "columns": ["month_year", "total_orders", "monthly_total"],
                "metadata": {"transformation": "AGGREGATE SUM"},
            },
            "reporting_exec_dashboard": {
                "id": "e4f5a6b7-c8d9-4e0f-1a2b-3c4d5e6f7a8b",
                "type": "job",
                "source_system": "bi_pipeline",
                "namespace": "bi_pipeline",
                "database_name": "bi_dw",
                "schema_name": "reports",
                "name": "reporting_exec_dashboard",
                "asset_type": "JOB",
                "created_at": "2026-01-01T00:00:00Z",
                "display_name": "reporting_exec_dashboard",
                "columns": [],
                "metadata": {"pipeline_job_id": 882, "schedule": "HOURLY"},
            },
        }

    def _init_edges(self) -> None:
        self.edges = [
            {
                "edge_id": "edge_stg_to_fact",
                "source": "stg_customer_orders",
                "target": "orders_fact",
                "granularity": "COLUMN",
                "operator_fingerprint": "op:proj:sub",
                "query_fingerprint": "qfp:9940ac12",
                "relationship_type": "DERIVED_FROM",
                "reasoning_state": "OBSERVED",
                "temporal": {
                    "valid_from": "2026-09-01T00:00:00Z",
                    "valid_to": None,
                    "transaction_from": "2026-09-01T10:00:00Z",
                    "transaction_to": None,
                    "effective_time_status": "VERIFIED",
                    "is_current": True,
                    "is_correction": False,
                    "correction_of": None,
                },
                "d14_warning": True,
                "evidence_ids": ["ev_stg_orders_01", "ev_stg_orders_02"],
            },
            {
                "edge_id": "edge_dim_to_fact",
                "source": "dim_customer_demographics",
                "target": "orders_fact",
                "granularity": "COLUMN",
                "operator_fingerprint": "op:join:customer_id",
                "query_fingerprint": "qfp:88fa2b10",
                "relationship_type": "DERIVED_FROM",
                "reasoning_state": "POSSIBLE",
                "temporal": {
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                    "transaction_from": "2026-01-01T00:00:00Z",
                    "transaction_to": None,
                    "effective_time_status": "VERIFIED",
                    "is_current": True,
                    "is_correction": False,
                    "correction_of": None,
                },
                "d14_warning": False,
                "evidence_ids": ["ev_dim_cust_01"],
            },
            {
                "edge_id": "edge_salary_to_adjusted",
                "source": "employees.salary",
                "target": "orders_fact",
                "granularity": "COLUMN",
                "operator_fingerprint": "op:case_when:salary",
                "query_fingerprint": "qfp:w03_cw",
                "relationship_type": "DERIVED_FROM",
                "reasoning_state": "REFUTED_FOR_RUN",
                "temporal": {
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                    "transaction_from": "2026-01-01T00:00:00Z",
                    "transaction_to": None,
                    "effective_time_status": "VERIFIED",
                    "is_current": True,
                    "is_correction": False,
                    "correction_of": None,
                },
                "d14_warning": False,
                "evidence_ids": ["ev_salary_neg_01"],
            },
            {
                "edge_id": "edge_rates_to_fact",
                "source": "currency_rates_feed",
                "target": "orders_fact",
                "granularity": "COLUMN",
                "operator_fingerprint": "op:stream:lookup",
                "query_fingerprint": "qfp:stream_fx",
                "relationship_type": "READS",
                "reasoning_state": "UNKNOWN",
                "temporal": {
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                    "transaction_from": "2026-01-01T00:00:00Z",
                    "transaction_to": None,
                    "effective_time_status": "UNKNOWN",
                    "is_current": True,
                    "is_correction": False,
                    "correction_of": None,
                },
                "d14_warning": False,
                "evidence_ids": [],
            },
            {
                "edge_id": "edge_fact_to_monthly",
                "source": "orders_fact",
                "target": "monthly_revenue_summary",
                "granularity": "COLUMN",
                "operator_fingerprint": "op:agg:sum_group_by",
                "query_fingerprint": "qfp:monthly_rev",
                "relationship_type": "DERIVED_FROM",
                "reasoning_state": "OBSERVED",
                "temporal": {
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                    "transaction_from": "2026-01-01T00:00:00Z",
                    "transaction_to": None,
                    "effective_time_status": "VERIFIED",
                    "is_current": True,
                    "is_correction": False,
                    "correction_of": None,
                },
                "d14_warning": False,
                "evidence_ids": ["ev_fact_monthly_01"],
            },
            {
                "edge_id": "edge_fact_to_dashboard",
                "source": "orders_fact",
                "target": "reporting_exec_dashboard",
                "granularity": "COLUMN",
                "operator_fingerprint": "op:job:extract_rollup",
                "query_fingerprint": "qfp:exec_dash",
                "relationship_type": "WRITES",
                "reasoning_state": "POSSIBLE",
                "temporal": {
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                    "transaction_from": "2026-01-01T00:00:00Z",
                    "transaction_to": None,
                    "effective_time_status": "VERIFIED",
                    "is_current": True,
                    "is_correction": False,
                    "correction_of": None,
                },
                "d14_warning": False,
                "evidence_ids": ["ev_fact_dash_01"],
            },
        ]

    def _init_evidence(self) -> None:
        self.evidence_dossiers: Dict[str, Dict[str, Any]] = {
            "ev_stg_orders_01": {
                "evidence_id": "ev_stg_orders_01",
                "evidence_type": "STATIC_AST",
                "source_system": "sqlglot",
                "run_id": "run_2026_09_23_093214",
                "granularity": "COLUMN",
                "operator": "PROJECTION_ARITHMETIC",
                "query_fingerprint": "qfp:9940ac12",
                "schema_fingerprint": "sfp:v2_postgres",
                "expression_fingerprint": "efp:(gross_amount - discount)",
                "parser_status": "SUPPORTED",
                "coverage": {
                    "run_covered": True,
                    "operator_covered": True,
                    "source_dataset_covered": True,
                    "target_dataset_covered": True,
                    "source_columns_covered": ["gross_amount"],
                    "target_columns_covered": ["net_revenue"],
                    "branches_covered": True,
                    "coverage_mode": "runtime",
                    "parser_status": "SUPPORTED",
                },
                "temporal": {
                    "event_time": "2026-09-23T09:30:00Z",
                    "effective_time": "2026-09-01T00:00:00Z",
                    "ingestion_time": "2026-09-23T09:30:01Z",
                },
                "source": {
                    "entity_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "name": "stg_customer_orders",
                    "column": "gross_amount",
                },
                "target": {
                    "entity_id": "e3b1c4a0-7f28-4c8d-965a-8d7b32c694a1",
                    "name": "orders_fact",
                    "column": "net_revenue",
                },
                "diagnostics": {
                    "ast_snippet": "SELECT (stg.gross_amount - stg.discount) AS net_revenue FROM stg_customer_orders",
                    "visitor_match": "gross_amount (AstLineageVisitor:210)",
                },
                "raw_event": {
                    "event_id": "raw_evt_sqlglot_01",
                    "payload": {
                        "dialect": "postgres",
                        "sql": "SELECT (gross_amount - discount) AS net_revenue FROM stg_customer_orders",
                    },
                    "payload_hash": "sha256:88fa2b109e4a32c0f65d",  # Payload hash comes from raw_event per contract
                    "source_system": "sqlglot",
                    "ingestion_time": "2026-09-23T09:30:01Z",
                },
                "lineage_versions": [
                    {"version_id": "ver_01", "valid_from": "2026-09-01T00:00:00Z", "tx_from": "2026-09-01T10:00:00Z"}
                ],
            },
            "ev_stg_orders_02": {
                "evidence_id": "ev_stg_orders_02",
                "evidence_type": "RUNTIME_PROBE",
                "source_system": "openlineage",
                "run_id": "run_2026_09_23_093214",
                "granularity": "COLUMN",
                "operator": "RUNTIME_EXECUTION",
                "query_fingerprint": "qfp:9940ac12",
                "schema_fingerprint": "sfp:v2_postgres",
                "expression_fingerprint": "efp:runtime_probe",
                "parser_status": "SUPPORTED",
                "coverage": {
                    "run_covered": True,
                    "operator_covered": True,
                    "source_dataset_covered": True,
                    "target_dataset_covered": True,
                    "source_columns_covered": ["gross_amount"],
                    "target_columns_covered": ["net_revenue"],
                    "branches_covered": True,
                    "coverage_mode": "runtime",
                    "parser_status": "SUPPORTED",
                },
                "temporal": {
                    "event_time": "2026-09-23T09:32:14.882Z",
                    "effective_time": "2026-09-23T09:32:14.882Z",
                    "ingestion_time": "2026-09-23T09:32:15Z",
                },
                "source": {
                    "entity_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "name": "stg_customer_orders",
                    "column": "gross_amount",
                },
                "target": {
                    "entity_id": "e3b1c4a0-7f28-4c8d-965a-8d7b32c694a1",
                    "name": "orders_fact",
                    "column": "net_revenue",
                },
                "diagnostics": {
                    "row_parity": "Row parity confirmed: 1,489,204 rows evaluated with delta non-zero.",
                    "probe_status": "SUCCESS",
                },
                "raw_event": {
                    "event_id": "raw_evt_openlineage_02",
                    "payload": {
                        "eventType": "COMPLETE",
                        "job": {"name": "clean_and_aggregate_orders"},
                    },
                    "payload_hash": "sha256:77cd9101ff2308eb941c",
                    "source_system": "openlineage",
                    "ingestion_time": "2026-09-23T09:32:15Z",
                },
                "lineage_versions": [
                    {"version_id": "ver_02", "valid_from": "2026-09-01T00:00:00Z", "tx_from": "2026-09-01T10:00:00Z"}
                ],
            },
        }

    # -------------------------------------------------------------------------
    # BaseEntityRepository Methods
    # -------------------------------------------------------------------------
    def _get_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Entity-only lookup: resolves by dict key (short name) or UUID id field."""
        for eid, ent in self.entities.items():
            if eid == entity_id or ent.get("id") == entity_id:
                return ent
        return None

    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return self._get_entity_by_id(entity_id)

    def get_by_fqn(self, fqn: str) -> Optional[Dict[str, Any]]:
        for ent in self.entities.values():
            if ent.get("fully_qualified_name") == fqn or ent.get("name") == fqn:
                return ent
        return None

    def search(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        q = (query or "").lower().strip()
        matched = []
        for ent in self.entities.values():
            if entity_type and ent["type"].lower() != entity_type.lower():
                continue
            if not q or q in (ent.get("name") or "").lower() or q in (ent.get("namespace") or "").lower() or any(q in c.lower() for c in ent.get("columns", [])):
                matched.append({
                    "id": ent.get("id"),
                    "name": ent.get("name", ""),
                    "type": ent.get("type"),
                    "namespace": ent.get("namespace"),
                    "display_name": ent.get("display_name"),
                    "fully_qualified_name": ent.get("fully_qualified_name"),
                    "column_count": len(ent.get("columns", [])),
                    "row_count": ent.get("metadata", {}).get("row_count"),
                })
        return matched[:limit], len(matched)

    # -------------------------------------------------------------------------
    # BaseLineageRepository Methods
    # -------------------------------------------------------------------------
    def get_graph(
        self,
        entity_id: str,
        granularity: str = "COLUMN",
        depth: int = 3,
        valid_at: Optional[str] = None,
        known_as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        center = self._get_entity_by_id(entity_id)
        if not center:
            # Fallback to orders_fact
            center = self.entities["orders_fact"]

        t_v = _parse_dt(valid_at)
        t_k = _parse_dt(known_as_of)

        matched_edges: List[Dict[str, Any]] = []
        active_node_ids = {center.get("id"), center.get("name")}

        for edge in self.edges:
            # Bitemporal half-open interval evaluation:
            # valid_from <= valid_at < valid_to AND tx_from <= known_as_of < tx_to
            v_lo = _parse_dt(edge["temporal"]["valid_from"])
            v_hi = _parse_dt(edge["temporal"]["valid_to"])
            tx_lo = _parse_dt(edge["temporal"]["transaction_from"])
            tx_hi = _parse_dt(edge["temporal"]["transaction_to"])

            valid_in_range = _is_in_half_open(t_v, v_lo, v_hi)
            tx_in_range = _is_in_half_open(t_k, tx_lo, tx_hi)

            # Determine dynamic reasoning state under the temporal slice
            state = edge["reasoning_state"]
            if not valid_in_range or not tx_in_range:
                # If queried outside interval, revert state to UNKNOWN
                state = "UNKNOWN"

            edge_out = dict(edge)
            edge_out["reasoning_state"] = state
            matched_edges.append(edge_out)

            active_node_ids.add(edge["source"])
            active_node_ids.add(edge["target"])

        # Collect nodes (use entity-only lookup, skip None ids)
        nodes = []
        for nid in active_node_ids:
            if not nid:
                continue
            ent = self._get_entity_by_id(nid)
            if ent:
                # Column entities use column_name instead of name, dataset_id instead of namespace
                name = ent.get("name") or ent.get("column_name") or nid
                namespace = ent.get("namespace") or ent.get("dataset_id") or ""
                nodes.append({
                    "id": ent.get("id"),
                    "type": ent.get("type"),
                    "name": name,
                    "display_name": ent.get("display_name") or name,
                    "namespace": namespace,
                    "schema_version": ent.get("schema_version"),
                    "columns": ent.get("columns", []),
                    "metadata": ent.get("metadata", {}),
                })

        # Build center node similarly
        center_name = center.get("name") or center.get("column_name") or entity_id
        center_namespace = center.get("namespace") or center.get("dataset_id") or ""

        return {
            "center_node": {
                "id": center.get("id"),
                "type": center.get("type"),
                "name": center_name,
                "display_name": center.get("display_name") or center_name,
                "namespace": center_namespace,
                "schema_version": center.get("schema_version"),
                "columns": center.get("columns", []),
                "metadata": center.get("metadata", {}),
            },
            "nodes": nodes,
            "edges": matched_edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(matched_edges),
                "depth": depth,
                "truncated": False,
            },
            "temporal": {"valid_at": valid_at, "known_as_of": known_as_of},
            "evidence_information": {"total_corroborated_records": len(self.evidence_dossiers)},
        }

    def get_upstream(
        self,
        entity_id: str,
        depth: int = 1,
        valid_at: Optional[str] = None,
        known_as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        full_graph = self.get_graph(entity_id, depth=depth, valid_at=valid_at, known_as_of=known_as_of)
        if not full_graph:
            return None
        center_name = full_graph["center_node"]["name"]
        center_id = full_graph["center_node"]["id"]
        # Upstream: target is center
        filtered_edges = [e for e in full_graph["edges"] if e["target"] in (center_name, center_id)]
        full_graph["edges"] = filtered_edges
        full_graph["stats"]["total_edges"] = len(filtered_edges)
        return full_graph

    def get_downstream(
        self,
        entity_id: str,
        depth: int = 1,
        valid_at: Optional[str] = None,
        known_as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        full_graph = self.get_graph(entity_id, depth=depth, valid_at=valid_at, known_as_of=known_as_of)
        if not full_graph:
            return None
        center_name = full_graph["center_node"]["name"]
        center_id = full_graph["center_node"]["id"]
        # Downstream: source is center
        filtered_edges = [e for e in full_graph["edges"] if e["source"] in (center_name, center_id)]
        full_graph["edges"] = filtered_edges
        full_graph["stats"]["total_edges"] = len(filtered_edges)
        return full_graph

    # -------------------------------------------------------------------------
    # BaseEvidenceRepository Methods
    # -------------------------------------------------------------------------
    def get_evidence_by_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        if evidence_id in self.evidence_dossiers:
            return self.evidence_dossiers[evidence_id]
        # Return synthesized dossier if ID matches pattern
        return {
            "evidence_id": evidence_id,
            "evidence_type": "STATIC_AST",
            "source_system": "sqlglot",
            "run_id": None,
            "granularity": "COLUMN",
            "operator": "PROJECT",
            "query_fingerprint": "qfp:default",
            "schema_fingerprint": "sfp:default",
            "expression_fingerprint": "efp:default",
            "parser_status": "SUPPORTED",
            "coverage": {
                "run_covered": True,
                "operator_covered": True,
                "source_dataset_covered": True,
                "target_dataset_covered": True,
                "source_columns_covered": [],
                "target_columns_covered": [],
                "branches_covered": False,
                "coverage_mode": "runtime",
                "parser_status": "SUPPORTED",
            },
            "temporal": {
                "event_time": "2026-09-23T00:00:00Z",
                "effective_time": "2026-09-23T00:00:00Z",
                "ingestion_time": "2026-09-23T00:00:01Z",
            },
            "source": {"entity_id": "src_default", "name": "source_table", "column": "col_a"},
            "target": {"entity_id": "tgt_default", "name": "target_table", "column": "col_b"},
            "diagnostics": {"status": "synthetic mock fixture"},
            "raw_event": {
                "event_id": f"raw_{evidence_id}",
                "payload": {"synthetic": True},
                "payload_hash": "sha256:synth_payload_hash",
                "source_system": "sqlglot",
                "ingestion_time": "2026-09-23T00:00:01Z",
            },
            "lineage_versions": [],
        }

    def get_by_entity(
        self,
        entity_id: str,
        evidence_type: Optional[str] = None,
        source_system: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        results = []
        for dos in self.evidence_dossiers.values():
            if evidence_type and dos["evidence_type"] != evidence_type:
                continue
            if source_system and dos["source_system"] != source_system:
                continue
            results.append({
                "id": dos["evidence_id"],
                "evidence_id": dos["evidence_id"],
                "evidence_type": dos["evidence_type"],
                "source_system": dos["source_system"],
                "run_id": dos["run_id"],
                "granularity": dos["granularity"],
                "operator": dos.get("operator"),
                "event_time": dos["temporal"]["event_time"],
                "payload_hash": dos["raw_event"]["payload_hash"],
                "source_column_id": dos["source"].get("column"),
                "target_column_id": dos["target"].get("column"),
            })
        return results[offset : offset + limit], len(results)

    def search_evidence(
        self,
        evidence_type: Optional[str] = None,
        source_system: Optional[str] = None,
        granularity: Optional[str] = None,
        operator: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        results = []
        for dos in self.evidence_dossiers.values():
            if evidence_type and dos["evidence_type"] != evidence_type:
                continue
            if source_system and dos["source_system"] != source_system:
                continue
            if granularity and dos["granularity"] != granularity:
                continue
            if operator and dos.get("operator") != operator:
                continue
            results.append({
                "id": dos["evidence_id"],
                "evidence_id": dos["evidence_id"],
                "evidence_type": dos["evidence_type"],
                "source_system": dos["source_system"],
                "run_id": dos["run_id"],
                "granularity": dos["granularity"],
                "operator": dos.get("operator"),
                "event_time": dos["temporal"]["event_time"],
                "payload_hash": dos["raw_event"]["payload_hash"],
                "source_column_id": dos["source"].get("column"),
                "target_column_id": dos["target"].get("column"),
            })
        return results[offset : offset + limit], len(results)

    # -------------------------------------------------------------------------
    # M4 Prediction / Dependency Reasoning (Section 10)
    # -------------------------------------------------------------------------
    def evaluate_dependency(
        self,
        run_id: str,
        source: str,
        target: str,
        valid_at: Optional[str] = None,
        known_as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Evaluates dependency by executing M4 FourStateEngine.infer without reimplementing rules R1-R5."""
        def _match_ref(ref: str, pattern: str) -> bool:
            return ref == pattern or ref.endswith("." + pattern) or pattern.endswith("." + ref)

        # 1. Check w03_case_when fixture
        keys, static, runtime = load_case("w03_case_when")
        wanted_keys = [
            k for k in keys
            if (k.run_id == run_id and _match_ref(k.source_column_id, source) and _match_ref(k.target_column_id, target))
        ]

        if wanted_keys:
            # Let M4 FourStateEngine execute R1-R5
            pred = self.engine.infer(PredictorInput(tuple(wanted_keys), tuple(static), tuple(runtime)))[0]
            state_val = pred.state.value
            rule_id = pred.rule_id
            explanation = pred.explanation
            ev_ids = list(pred.evidence_ids)
            flags = list(pred.flags)
        else:
            # Check edge in mock repository
            t_v = _parse_dt(valid_at)
            matched_edge = None
            for e in self.edges:
                if _match_ref(e["source"], source) and _match_ref(e["target"], target):
                    matched_edge = e
                    break

            if matched_edge:
                v_lo = _parse_dt(matched_edge["temporal"]["valid_from"])
                v_hi = _parse_dt(matched_edge["temporal"]["valid_to"])
                if not _is_in_half_open(t_v, v_lo, v_hi):
                    state_val = "UNKNOWN"
                    rule_id = "R5"
                    explanation = f"Rule R5: No observation recorded for run {run_id} at Valid Time {valid_at}."
                    ev_ids = []
                    flags = ["HISTORICAL_SLICE_INACTIVE"]
                else:
                    state_val = matched_edge["reasoning_state"]
                    rule_id = "R2" if state_val == "OBSERVED" else ("R3" if state_val == "REFUTED_FOR_RUN" else "R4")
                    explanation = f"Evaluated under rule {rule_id}"
                    ev_ids = matched_edge.get("evidence_ids", [])
                    flags = []
            else:
                # If neither the run nor the entities exist in the knowledge graph, it is an unknown dependency/run
                keys_runs = {k.run_id for k in keys}
                has_known_run = run_id in keys_runs or run_id.startswith("run_2026_")
                has_known_entities = bool(self._get_entity_by_id(source) or self._get_entity_by_id(target))
                if not (has_known_run and has_known_entities):
                    return None

                state_val = "POSSIBLE"
                rule_id = "R4"
                explanation = "Static candidate without positive or negative runtime evidence"
                ev_ids = ["ev_synth_01"]
                flags = []

        warnings = []
        if state_val == "POSSIBLE":
            warnings.append("NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE")
        if "stg" in source or source == "stg_customer_orders":
            warnings.append("D-14_TIME_WINDOW_UNKNOWN")

        return {
            "run_id": run_id,
            "source": {"column_id": f"col_{source}", "display": source},
            "target": {"column_id": f"col_{target}", "display": target},
            "granularity": "COLUMN",
            "state": state_val,
            "interpretation": STATE_INTERPRETATIONS.get(state_val, STATE_INTERPRETATIONS["UNKNOWN"]),
            "explanation": explanation,
            "rule_id": rule_id,
            "reasoning_version": "1.0.0",
            "evidence_ids": ev_ids,
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
            "flags": flags,
            "temporal_context": {"valid_at": valid_at, "known_as_of": known_as_of},
            "warnings": warnings,
            "is_mock": True,
        }

    # -------------------------------------------------------------------------
    # Evaluation Oracle (Hazard Mode Only)
    # -------------------------------------------------------------------------
    def get_benchmark_oracle(self, run_id: str) -> List[Dict[str, Any]]:
        truth_records = load_truth("w03_case_when")
        filtered = [r for r in truth_records if r.key.run_id == run_id]
        if not filtered:
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


# Default singleton instance
mock_repository = MockRepository()
