"""
Audit Trail & Version History Schemas
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any
from uuid import UUID


class AuditLogEntry(BaseModel):
    """Single audit log entry"""
    id: UUID
    asset_id: UUID
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: str
    change_type: str  # CREATE, UPDATE, DELETE, RESTORE
    change_reason: Optional[str] = None
    created_at: datetime


class AuditTrailResponse(BaseModel):
    """Complete audit trail for an asset"""
    asset_id: UUID
    asset_name: str
    total_changes: int
    date_range: tuple[datetime, datetime]
    entries: list[AuditLogEntry] = []
    summary: dict = {}  # {field_name: change_count}


class AssetVersion(BaseModel):
    """Asset version snapshot"""
    id: UUID
    asset_id: UUID
    version_number: int
    snapshot_data: dict[str, Any]
    created_by: str
    created_at: datetime
    change_summary: Optional[str] = None
    is_release: bool = False
    release_notes: Optional[str] = None


class VersionHistory(BaseModel):
    """Complete version history"""
    asset_id: UUID
    current_version: int
    total_versions: int
    versions: list[AssetVersion] = []


class VersionDiff(BaseModel):
    """Diff between two versions"""
    from_version: int
    to_version: int
    added_fields: dict = {}
    modified_fields: dict = {}  # {field_name: (old_value, new_value)}
    removed_fields: dict = {}
    change_summary: str


class AuditEvent(BaseModel):
    """High-level audit event"""
    id: UUID
    asset_id: UUID
    event_type: str
    severity: str  # INFO, WARNING, CRITICAL
    description: str
    metadata: Optional[dict] = None
    actor: str
    created_at: datetime
    is_reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class RollbackRequest(BaseModel):
    """Request to rollback to previous version"""
    asset_id: UUID
    from_version: int
    to_version: int
    rollback_reason: str
    request_body: Optional[str] = None


class RollbackResponse(BaseModel):
    """Response from rollback operation"""
    rollback_id: UUID
    asset_id: UUID
    from_version: int
    to_version: int
    status: str  # PENDING, APPROVED, EXECUTED, REJECTED
    requested_by: str
    created_at: datetime
    message: str


class AuditExport(BaseModel):
    """Audit trail export"""
    asset_id: UUID
    asset_name: str
    export_format: str  # CSV, JSON, PDF
    export_period: tuple[datetime, datetime]
    total_entries: int
    generated_at: datetime
    generated_by: str


class AuditStatistics(BaseModel):
    """Audit statistics"""
    total_changes: int
    changes_by_type: dict[str, int]  # {change_type: count}
    changes_by_field: dict[str, int]  # {field_name: count}
    top_changers: list[tuple[str, int]] = []  # [(user, change_count)]
    date_range: tuple[datetime, datetime]


class ComplianceReport(BaseModel):
    """Compliance & governance report"""
    asset_id: UUID
    asset_name: str
    report_period: tuple[datetime, datetime]
    total_changes: int
    critical_events: int
    unapproved_changes: int
    rollbacks: int
    data_lineage_changes: int
    ownership_changes: int
    access_violations: int
    compliance_score: float  # 0-100
