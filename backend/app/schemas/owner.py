"""
Owner & Steward Assignment Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class TeamMember(BaseModel):
    """Team member who can be assigned as owner/steward"""
    id: UUID
    email: EmailStr
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    slack_handle: Optional[str] = None
    is_active: bool = True


class TeamMemberCreate(BaseModel):
    """Create new team member"""
    email: EmailStr
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    slack_handle: Optional[str] = None


class OwnerAssignmentRecord(BaseModel):
    """Single owner assignment record (audit trail)"""
    id: UUID
    dataset_id: UUID
    assignment_type: str  # 'OWNER' or 'STEWARD'
    previous_value: Optional[str] = None
    new_value: str
    assigned_by: str
    assigned_at: datetime
    reason: Optional[str] = None


class OwnerAssignmentHistory(BaseModel):
    """Owner assignment history for a dataset"""
    dataset_id: UUID
    current_owner: Optional[str] = None
    current_steward: Optional[str] = None
    owner_assigned_at: Optional[datetime] = None
    steward_assigned_at: Optional[datetime] = None
    history: list[OwnerAssignmentRecord] = []
    total_changes: int = 0


class AssignOwnerRequest(BaseModel):
    """Request to assign owner/steward"""
    owner_email: Optional[EmailStr] = None
    steward_email: Optional[EmailStr] = None
    reason: Optional[str] = Field(None, description="Reason for assignment change")
    requires_approval: bool = False


class AssignOwnerResponse(BaseModel):
    """Response after assigning owner/steward"""
    dataset_id: UUID
    owner: Optional[str] = None
    steward: Optional[str] = None
    assigned_at: datetime
    assigned_by: str
    message: str = "Assignment successful"


class OwnerRequest(BaseModel):
    """Owner assignment request (approval workflow)"""
    id: UUID
    dataset_id: UUID
    requested_by: str
    requested_owner: str
    reason: Optional[str] = None
    status: str  # PENDING, APPROVED, REJECTED
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None


class OwnerRequestCreate(BaseModel):
    """Create owner request"""
    dataset_id: UUID
    requested_owner: str
    reason: Optional[str] = None
    expires_in_days: int = 7


class ApproveOwnerRequest(BaseModel):
    """Approve owner request"""
    approved_by: str
    reason: Optional[str] = None


class OwnershipStats(BaseModel):
    """Ownership statistics"""
    total_datasets: int = 0
    assigned_datasets: int = 0
    unassigned_datasets: int = 0
    ownership_coverage_percent: float = 0.0
    team_sizes: dict = {}  # {'Department': count}
    top_owners: list[tuple[str, int]] = []  # [(owner_name, dataset_count)]


class OwnershipNotification(BaseModel):
    """Notification for ownership changes"""
    dataset_id: UUID
    dataset_name: str
    event_type: str  # 'ASSIGNED', 'REASSIGNED', 'UNASSIGNED'
    old_owner: Optional[str] = None
    new_owner: str
    changed_by: str
    changed_at: datetime
    message: str
