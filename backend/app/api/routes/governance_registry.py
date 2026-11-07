"""Workspace-scoped glossary, classification, domains and product contracts."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.api.routes.membership import require_role

router = APIRouter(prefix="/governance", tags=["governance-registry"], dependencies=[Depends(require_user)])
WRITE = [Depends(require_role("owner", "admin", "editor"))]


def _tables(cur, *names: str) -> None:
    missing = []
    for name in names:
        cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{name}",))
        if cur.fetchone()["relation"] is None:
            missing.append(name)
    if missing:
        raise HTTPException(status_code=503, detail=f"Governance storage unavailable: {', '.join(missing)}. Migration 0011 requires migration-owner approval and application.")


class TermInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=4000)


class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: uuid.UUID


class ClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: uuid.UUID
    column_id: uuid.UUID | None = None
    classification: Literal["PII_SOURCE", "PII_INHERITED", "PII_MASKED", "PII_POTENTIAL", "PII_CLEARED", "UNKNOWN"]
    evidence_state: Literal["OBSERVED", "POSSIBLE", "UNKNOWN"]
    provenance: dict[str, Any]

    @model_validator(mode="after")
    def validate_provenance(self):
        allowed = {"origin", "evidence_id", "note", "lineage_edge_ids"}
        if not self.provenance or set(self.provenance) - allowed:
            raise ValueError("provenance must contain only origin, evidence_id, note, and lineage_edge_ids")
        origin = self.provenance.get("origin")
        if origin not in {"manual_steward", "inherited_lineage", "runtime_evidence", "sqlglot_possible"}:
            raise ValueError("provenance.origin must identify a supported evidence source")
        note = self.provenance.get("note")
        if note is not None and (not isinstance(note, str) or len(note) > 1000):
            raise ValueError("provenance.note must be text up to 1000 characters")
        evidence_id = self.provenance.get("evidence_id")
        if evidence_id is not None and (not isinstance(evidence_id, str) or not 1 <= len(evidence_id) <= 200):
            raise ValueError("provenance.evidence_id must be a reference up to 200 characters")
        edge_ids = self.provenance.get("lineage_edge_ids", [])
        if not isinstance(edge_ids, list) or len(edge_ids) > 50 or any(not isinstance(item, str) or len(item) > 200 for item in edge_ids):
            raise ValueError("provenance.lineage_edge_ids must contain at most 50 references")
        if origin == "inherited_lineage" and not edge_ids:
            raise ValueError("inherited classification requires one or more supporting lineage edge references")
        if origin in {"runtime_evidence", "sqlglot_possible"} and not evidence_id:
            raise ValueError("runtime or possible classification requires a supporting evidence reference")
        if self.classification == "PII_INHERITED" and origin != "inherited_lineage":
            raise ValueError("PII_INHERITED requires lineage provenance")
        if self.classification == "PII_POTENTIAL" and origin != "sqlglot_possible":
            raise ValueError("PII_POTENTIAL requires possible/static-analysis provenance")
        if self.classification == "UNKNOWN" and self.evidence_state != "UNKNOWN":
            raise ValueError("UNKNOWN classification requires UNKNOWN evidence state")
        return self


class DomainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    owner_user_id: uuid.UUID | None = None


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    domain_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    status: Literal["DRAFT", "ACTIVE", "DEPRECATED"] = "DRAFT"
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class ContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    enforcement_mode: Literal["MONITOR", "WARN", "BLOCK"]
    clauses: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


class ContractLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assertion_id: uuid.UUID
    clause_key: str = Field(min_length=1, max_length=120)


@router.get("/terms")
def list_terms(user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "glossary_term", "term_assignment")
            cur.execute("SELECT t.id::text,t.name,t.definition,t.status,t.created_at,t.updated_at,count(a.id)::int AS asset_count FROM glossary_term t LEFT JOIN term_assignment a ON a.term_id=t.id GROUP BY t.id ORDER BY lower(t.name)")
            terms = [dict(row) for row in cur.fetchall()]
    return {"terms": terms, "count": len(terms)}


@router.post("/terms", status_code=201, dependencies=WRITE)
def create_term(body: TermInput, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "glossary_term")
            cur.execute("INSERT INTO glossary_term(name,definition,created_by) VALUES (%s,%s,%s::uuid) RETURNING id::text,name,definition,status,created_at", (body.name.strip(), body.definition.strip(), user["id"]))
            row = cur.fetchone()
    return dict(row)


@router.post("/terms/{term_id}/assets", status_code=201, dependencies=WRITE)
def assign_term(term_id: uuid.UUID, body: AssignmentInput, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "glossary_term", "term_assignment")
            cur.execute("SELECT id FROM glossary_term WHERE id=%s::uuid", (str(term_id),))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Glossary term not found")
            cur.execute("SELECT id FROM dataset WHERE id=%s::uuid", (str(body.dataset_id),))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Asset not found")
            cur.execute("INSERT INTO term_assignment(term_id,dataset_id,assigned_by) VALUES (%s::uuid,%s::uuid,%s::uuid) ON CONFLICT (workspace_id,term_id,dataset_id) DO NOTHING RETURNING id::text", (str(term_id),str(body.dataset_id),user["id"]))
            result = cur.fetchone()
    return {"ok": True, "created": result is not None}


@router.post("/terms/{term_id}/approve", dependencies=[Depends(require_role("owner", "admin"))])
def approve_term(term_id: uuid.UUID, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "glossary_term")
            cur.execute("UPDATE glossary_term SET status='APPROVED',approved_by=%s::uuid,updated_at=now() WHERE id=%s::uuid RETURNING id::text,status,updated_at", (user["id"],str(term_id)))
            row = cur.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Glossary term not found")
    return dict(row)


@router.post("/classifications", status_code=201, dependencies=WRITE)
def create_classification(body: ClassificationInput, user: dict = Depends(require_user)):
    if body.classification == "PII_CLEARED" and body.evidence_state != "OBSERVED":
        raise HTTPException(status_code=422, detail="PII_CLEARED requires observed evidence and steward review")
    if body.classification == "PII_SOURCE" and body.evidence_state != "OBSERVED":
        raise HTTPException(status_code=422, detail="PII_SOURCE must be directly observed or manually steward-tagged")
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "pii_classification")
            if body.classification == "PII_CLEARED":
                cur.execute("SELECT role FROM workspace_member WHERE user_id=%s::uuid AND status='active'", (user["id"],))
                member = cur.fetchone()
                if not member or member["role"] not in {"owner", "admin"}:
                    raise HTTPException(status_code=403, detail="PII_CLEARED classification requires an owner or admin review")
            cur.execute("SELECT id FROM dataset WHERE id=%s::uuid", (str(body.dataset_id),))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Asset not found")
            if body.column_id:
                cur.execute("SELECT id FROM column_record WHERE id=%s::uuid AND dataset_id=%s::uuid", (str(body.column_id),str(body.dataset_id)))
                if not cur.fetchone(): raise HTTPException(status_code=404, detail="Column not found for this asset")
            if body.classification == "PII_CLEARED":
                cur.execute("INSERT INTO pii_classification(dataset_id,column_id,classification,evidence_state,provenance,classified_by,reviewed_by,reviewed_at) VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s::uuid,%s::uuid,now()) RETURNING id::text,dataset_id::text,column_id::text,classification,evidence_state,provenance,created_at,reviewed_by::text,reviewed_at", (str(body.dataset_id),str(body.column_id) if body.column_id else None,body.classification,body.evidence_state,Json(body.provenance),user["id"],user["id"]))
            else:
                cur.execute("INSERT INTO pii_classification(dataset_id,column_id,classification,evidence_state,provenance,classified_by) VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s::uuid) RETURNING id::text,dataset_id::text,column_id::text,classification,evidence_state,provenance,created_at", (str(body.dataset_id),str(body.column_id) if body.column_id else None,body.classification,body.evidence_state,Json(body.provenance),user["id"]))
            result = dict(cur.fetchone())
    return result


@router.get("/classifications")
def list_classifications(dataset_id: uuid.UUID | None = None, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "pii_classification")
            cur.execute("SELECT id::text,dataset_id::text,column_id::text,classification,evidence_state,provenance,classified_by::text,reviewed_by::text,reviewed_at,created_at FROM pii_classification WHERE (%s::uuid IS NULL OR dataset_id=%s::uuid) ORDER BY created_at DESC", (str(dataset_id) if dataset_id else None,str(dataset_id) if dataset_id else None))
            rows = [dict(row) for row in cur.fetchall()]
    return {"classifications": rows, "count": len(rows)}


@router.get("/domains")
def list_domains(user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "domain")
            cur.execute("SELECT id::text,name,description,owner_user_id::text,created_at,updated_at FROM domain ORDER BY lower(name)")
            rows = [dict(row) for row in cur.fetchall()]
    return {"domains": rows, "count": len(rows)}


@router.post("/domains", status_code=201, dependencies=WRITE)
def create_domain(body: DomainInput, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "domain")
            cur.execute("INSERT INTO domain(name,description,owner_user_id,created_by) VALUES (%s,%s,%s::uuid,%s::uuid) RETURNING id::text,name,description,owner_user_id::text,created_at", (body.name.strip(),body.description.strip(),str(body.owner_user_id) if body.owner_user_id else None,user["id"]))
            row = dict(cur.fetchone())
    return row


@router.get("/products")
def list_products(user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "data_product", "domain", "product_asset", "data_contract", "freshness_evaluation", "quality_result", "incident")
            cur.execute("""SELECT p.id::text,p.name,p.description,p.status,p.owner_user_id::text,p.domain_id::text,d.name AS domain_name,
                dc.version AS contract_version,dc.enforcement_mode AS contract_enforcement_mode,
                count(DISTINCT pa.dataset_id)::int AS asset_count,
                count(DISTINCT pa.dataset_id) FILTER (WHERE fe.state='LATE' OR fe.state='STALE')::int AS late_assets,
                count(DISTINCT pa.dataset_id) FILTER (WHERE qr.status='FAIL')::int AS failing_quality_assets,
                count(DISTINCT pa.dataset_id) FILTER (WHERE i.status <> 'RESOLVED')::int AS incident_assets
                FROM data_product p LEFT JOIN domain d ON d.id=p.domain_id
                LEFT JOIN LATERAL (SELECT version,enforcement_mode FROM data_contract WHERE product_id=p.id ORDER BY version DESC LIMIT 1) dc ON true
                LEFT JOIN product_asset pa ON pa.product_id=p.id
                LEFT JOIN LATERAL (SELECT state FROM freshness_evaluation WHERE dataset_id=pa.dataset_id ORDER BY evaluated_at DESC LIMIT 1) fe ON true
                LEFT JOIN LATERAL (SELECT status FROM quality_result WHERE assertion_id IN (SELECT id FROM quality_assertion WHERE dataset_id=pa.dataset_id) ORDER BY evaluated_at DESC LIMIT 1) qr ON true
                LEFT JOIN incident i ON i.dataset_id=pa.dataset_id GROUP BY p.id,d.name ORDER BY lower(p.name)""")
            rows = [dict(row) for row in cur.fetchall()]
    return {"products": rows, "count": len(rows)}


@router.post("/products", status_code=201, dependencies=WRITE)
def create_product(body: ProductInput, user: dict = Depends(require_user)):
    if len(set(body.asset_ids)) != len(body.asset_ids):
        raise HTTPException(status_code=422, detail="asset_ids must not contain duplicates")
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "data_product", "domain", "product_asset")
            if body.domain_id:
                cur.execute("SELECT id FROM domain WHERE id=%s::uuid", (str(body.domain_id),))
                if not cur.fetchone(): raise HTTPException(status_code=404, detail="Domain not found")
            cur.execute("INSERT INTO data_product(name,description,domain_id,owner_user_id,status,created_by) VALUES (%s,%s,%s::uuid,%s::uuid,%s,%s::uuid) RETURNING id::text,name,status,domain_id::text", (body.name.strip(),body.description.strip(),str(body.domain_id) if body.domain_id else None,str(body.owner_user_id) if body.owner_user_id else None,body.status,user["id"]))
            product = dict(cur.fetchone())
            for asset_id in body.asset_ids:
                cur.execute("SELECT id FROM dataset WHERE id=%s::uuid", (str(asset_id),))
                if not cur.fetchone(): raise HTTPException(status_code=404, detail="One or more assets were not found in this workspace")
                cur.execute("INSERT INTO product_asset(product_id,dataset_id) VALUES (%s::uuid,%s::uuid)", (product["id"],str(asset_id)))
    return {**product,"asset_ids":[str(v) for v in body.asset_ids]}


@router.post("/products/{product_id}/contracts", status_code=201, dependencies=[Depends(require_role("owner", "admin"))])
def create_contract(product_id: uuid.UUID, body: ContractInput, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "data_contract", "data_product")
            cur.execute("SELECT id FROM data_product WHERE id=%s::uuid", (str(product_id),))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Data product not found")
            cur.execute("SELECT COALESCE(max(version),0)::int AS version FROM data_contract WHERE product_id=%s::uuid", (str(product_id),))
            latest_version = cur.fetchone()["version"]
            if body.version != latest_version + 1:
                raise HTTPException(status_code=409, detail=f"Contract versions must be sequential; next version is {latest_version + 1}.")
            cur.execute("INSERT INTO data_contract(product_id,version,enforcement_mode,clauses,created_by) VALUES (%s::uuid,%s,%s,%s,%s::uuid) RETURNING id::text,product_id::text,version,enforcement_mode,clauses,created_at", (str(product_id),body.version,body.enforcement_mode,Json(body.clauses),user["id"]))
            contract = dict(cur.fetchone())
    return contract


@router.get("/products/{product_id}/contracts")
def list_contracts(product_id: uuid.UUID, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "data_product", "data_contract", "quality_contract_link")
            cur.execute("SELECT id::text FROM data_product WHERE id=%s::uuid", (str(product_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Data product not found")
            cur.execute("""SELECT c.id::text,c.product_id::text,c.version,c.enforcement_mode,c.clauses,c.created_at,
                COALESCE(jsonb_agg(jsonb_build_object('assertion_id',l.assertion_id::text,'clause_key',l.clause_key))
                    FILTER (WHERE l.assertion_id IS NOT NULL),'[]'::jsonb) AS assertion_links
                FROM data_contract c LEFT JOIN quality_contract_link l ON l.contract_id=c.id
                WHERE c.product_id=%s::uuid GROUP BY c.id ORDER BY c.version DESC""", (str(product_id),))
            rows = [dict(row) for row in cur.fetchall()]
    return {"contracts": rows, "count": len(rows)}


@router.post("/contracts/{contract_id}/assertions", status_code=201, dependencies=[Depends(require_role("owner", "admin"))])
def link_contract_assertion(contract_id: uuid.UUID, body: ContractLinkInput, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _tables(cur, "data_contract", "quality_assertion", "quality_contract_link")
            cur.execute("SELECT id FROM data_contract WHERE id=%s::uuid", (str(contract_id),))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Contract not found")
            cur.execute("SELECT id FROM quality_assertion WHERE id=%s::uuid", (str(body.assertion_id),))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Assertion not found")
            cur.execute("INSERT INTO quality_contract_link(assertion_id,contract_id,clause_key) VALUES (%s::uuid,%s::uuid,%s) ON CONFLICT DO NOTHING RETURNING assertion_id::text", (str(body.assertion_id),str(contract_id),body.clause_key.strip()))
            row = cur.fetchone()
    return {"ok": True, "created": row is not None}

