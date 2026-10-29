"""
Metadata Editing Schemas
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class MetadataUpdateRequest(BaseModel):
    """Request to update asset metadata"""
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[list[str]] = Field(None, max_items=20)
    custom_properties: Optional[dict] = Field(None, description="Custom key-value metadata")


class MetadataUpdateResponse(BaseModel):
    """Response after updating metadata"""
    asset_id: UUID
    field_updated: str  # 'description', 'tags', etc.
    old_value: Optional[str] = None
    new_value: str
    updated_at: datetime
    updated_by: str


class BulkMetadataUpdate(BaseModel):
    """Bulk update metadata for multiple assets"""
    asset_ids: list[UUID]
    description: Optional[str] = None
    add_tags: Optional[list[str]] = None
    remove_tags: Optional[list[str]] = None
    custom_properties: Optional[dict] = None


class BulkUpdateResponse(BaseModel):
    """Response for bulk metadata update"""
    total_updated: int
    successful: int
    failed: int
    updated_assets: list[UUID]
    errors: Optional[list[str]] = None


class EditableField(BaseModel):
    """Represents an editable field in the UI"""
    name: str  # e.g., 'description'
    label: str  # e.g., 'Description'
    value: Optional[str] = None
    type: str = "text"  # 'text', 'textarea', 'tags', 'number', etc.
    placeholder: Optional[str] = None
    max_length: Optional[int] = None
    required: bool = False
    editable: bool = True
    validation_rules: Optional[dict] = None


class EntityMetadata(BaseModel):
    """Complete entity metadata for editing"""
    id: UUID
    name: str
    description: Optional[str] = None
    tags: list[str] = []
    custom_properties: dict = {}
    owner: Optional[str] = None
    steward: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None
    editable_fields: list[EditableField] = []


class UndoRedoState(BaseModel):
    """State for undo/redo functionality"""
    current_index: int = 0
    history: list[dict] = []
    can_undo: bool = False
    can_redo: bool = False


class ValidationError(BaseModel):
    """Validation error details"""
    field: str
    message: str
    value: Optional[str] = None


class BatchEditOperation(BaseModel):
    """Batch edit operation with rollback capability"""
    operation_id: str
    timestamp: datetime
    user: str
    asset_ids: list[UUID]
    changes: dict
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    rollback_available: bool = True
