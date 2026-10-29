"""
Metadata Editing API Routes
Handles inline editing of descriptions, tags, and custom properties
"""

import logging
from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from backend.app.db import get_db_connection
from backend.app.auth import require_user
from backend.app.schemas.metadata import (
    MetadataUpdateRequest,
    MetadataUpdateResponse,
    EntityMetadata,
    EditableField,
    BulkMetadataUpdate,
    BulkUpdateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metadata", tags=["metadata"], dependencies=[Depends(require_user)])


# ═══════════════════════════════════════════════════════════════════
# Single Field Updates
# ═══════════════════════════════════════════════════════════════════

@router.put("/{asset_id}/description")
def update_description(
    asset_id: str,
    description: str = "",
    user: dict = Depends(require_user),
) -> MetadataUpdateResponse:
    """
    Update asset description (inline editing)
    
    Parameters:
        asset_id: Dataset ID
        description: New description (empty string to clear)
        user: User resolved from the verified Supabase access token
    
    Returns:
        Confirmation of update
    """
    current_user = user.get("email") or user["id"]
    conn = get_db_connection()
    try:
        cur = conn.cursor(row_factory=dict)
        
        # Get current description
        cur.execute(
            "SELECT description FROM dataset WHERE id = %s",
            (asset_id,)
        )
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        old_value = result.get("description")
        
        # Validate description length
        if len(description) > 500:
            raise HTTPException(
                status_code=400,
                detail="Description must be 500 characters or less"
            )
        
        # Update description
        cur.execute(
            """
            UPDATE dataset 
            SET description = %s, last_modified_by = %s, last_modified_at = NOW()
            WHERE id = %s
            """,
            (description if description else None, current_user, asset_id)
        )
        
        # Audit log
        cur.execute(
            """
            INSERT INTO audit_log (asset_id, field_name, old_value, new_value, changed_by, change_type)
            VALUES (%s, 'description', %s, %s, %s, 'UPDATE')
            """,
            (asset_id, old_value, description, current_user)
        )
        
        conn.commit()
        
        logger.info(f"Updated description for {asset_id}")
        
        return MetadataUpdateResponse(
            asset_id=UUID(asset_id),
            field_updated="description",
            old_value=old_value,
            new_value=description,
            updated_at=datetime.utcnow(),
            updated_by=current_user
        )
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating description: {e}")
        raise HTTPException(status_code=500, detail="Failed to update description")
    
    finally:
        cur.close()
        conn.close()


@router.put("/{asset_id}/tags")
def update_tags(
    asset_id: str,
    add_tags: Optional[list[str]] = None,
    remove_tags: Optional[list[str]] = None,
    set_tags: Optional[list[str]] = None,
    user: dict = Depends(require_user),
):
    """
    Update asset tags (add, remove, or replace)
    
    Parameters:
        asset_id: Dataset ID
        add_tags: Tags to add
        remove_tags: Tags to remove
        set_tags: Replace all tags (if provided, add_tags and remove_tags are ignored)
        current_user: User making the update
    
    Returns:
        Updated tags
    """
    current_user = user.get("email") or user["id"]
    conn = get_db_connection()
    try:
        cur = conn.cursor(row_factory=dict)
        
        # Get current tags (simplified - stored as JSON in real implementation)
        cur.execute("SELECT tags FROM dataset WHERE id = %s", (asset_id,))
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        current_tags = result.get("tags") or []
        old_tags = current_tags.copy()
        
        # Calculate new tags
        if set_tags is not None:
            new_tags = set_tags
        else:
            new_tags = set(current_tags)
            if add_tags:
                new_tags.update(add_tags)
            if remove_tags:
                new_tags.difference_update(remove_tags)
            new_tags = list(new_tags)
        
        # Validate tag count
        if len(new_tags) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 tags allowed")
        
        # Update tags
        cur.execute(
            """
            UPDATE dataset 
            SET tags = %s, last_modified_by = %s, last_modified_at = NOW()
            WHERE id = %s
            """,
            (new_tags, current_user, asset_id)
        )
        
        # Audit log
        cur.execute(
            """
            INSERT INTO audit_log (asset_id, field_name, old_value, new_value, changed_by, change_type)
            VALUES (%s, 'tags', %s, %s, %s, 'UPDATE')
            """,
            (asset_id, str(old_tags), str(new_tags), current_user)
        )
        
        conn.commit()
        
        logger.info(f"Updated tags for {asset_id}")
        
        return {"asset_id": asset_id, "tags": new_tags, "updated_by": current_user}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating tags: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tags")
    
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# Bulk Updates
# ═══════════════════════════════════════════════════════════════════

@router.post("/bulk-update")
def bulk_update_metadata(
    request: BulkMetadataUpdate,
    user: dict = Depends(require_user),
) -> BulkUpdateResponse:
    """
    Bulk update metadata for multiple assets
    
    Parameters:
        request: Bulk update request
        current_user: User making the update
    
    Returns:
        Summary of bulk update
    """
    current_user = user.get("email") or user["id"]
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        successful = 0
        failed = 0
        errors = []
        updated_assets = []
        
        for asset_id in request.asset_ids:
            try:
                # Update description if provided
                if request.description is not None:
                    cur.execute(
                        """
                        UPDATE dataset 
                        SET description = %s, last_modified_by = %s, last_modified_at = NOW()
                        WHERE id = %s
                        """,
                        (request.description, current_user, str(asset_id))
                    )
                
                # Handle tags (simplified)
                if request.add_tags or request.remove_tags:
                    # In real implementation, handle tag operations
                    pass
                
                # Handle custom properties
                if request.custom_properties:
                    # Store in separate table or JSON field
                    pass
                
                updated_assets.append(asset_id)
                successful += 1
                
            except Exception as e:
                failed += 1
                errors.append(f"Asset {asset_id}: {str(e)}")
        
        conn.commit()
        
        logger.info(f"Bulk update completed: {successful} successful, {failed} failed")
        
        return BulkUpdateResponse(
            total_updated=len(request.asset_ids),
            successful=successful,
            failed=failed,
            updated_assets=updated_assets,
            errors=errors if errors else None
        )
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in bulk update: {e}")
        raise HTTPException(status_code=500, detail="Bulk update failed")
    
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# Editable Metadata View
# ═══════════════════════════════════════════════════════════════════

@router.get("/{asset_id}/editable", response_model=EntityMetadata)
def get_editable_metadata(asset_id: str):
    """
    Get metadata formatted for inline editing
    
    Parameters:
        asset_id: Dataset ID
    
    Returns:
        Entity metadata with editable fields
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(row_factory=dict)
        
        cur.execute(
            """
            SELECT id, name, description, tags, owner_name as owner, 
                   steward_name as steward, created_at, last_modified_at, last_modified_by
            FROM dataset
            WHERE id = %s
            """,
            (asset_id,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Define editable fields
        editable_fields = [
            EditableField(
                name="description",
                label="Description",
                value=result.get("description"),
                type="textarea",
                placeholder="Enter dataset description...",
                max_length=500,
                required=False,
                editable=True
            ),
            EditableField(
                name="tags",
                label="Tags",
                value=",".join(result.get("tags") or []),
                type="tags",
                placeholder="Add tags (comma-separated)...",
                max_length=100,
                required=False,
                editable=True
            ),
        ]
        
        return EntityMetadata(
            id=result["id"],
            name=result["name"],
            description=result.get("description"),
            tags=result.get("tags") or [],
            owner=result.get("owner"),
            steward=result.get("steward"),
            created_at=result.get("created_at") or datetime.utcnow(),
            updated_at=result.get("last_modified_at") or result.get("created_at") or datetime.utcnow(),
            updated_by=result.get("last_modified_by"),
            editable_fields=editable_fields
        )
    
    except Exception as e:
        logger.error(f"Error fetching editable metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch metadata")


# ═══════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════

@router.post("/validate")
def validate_metadata_field(
    field: str,
    value: str
):
    """
    Validate metadata field before saving
    
    Parameters:
        field: Field name (e.g., 'description', 'tags')
        value: Field value to validate
    
    Returns:
        Validation result
    """
    errors = []
    
    if field == "description":
        if len(value) > 500:
            errors.append("Description must be 500 characters or less")
        if len(value.strip()) == 0:
            errors.append("Description cannot be empty")
    
    elif field == "tags":
        tags = [t.strip() for t in value.split(",") if t.strip()]
        if len(tags) > 20:
            errors.append("Maximum 20 tags allowed")
        for tag in tags:
            if len(tag) > 50:
                errors.append(f"Tag '{tag}' exceeds 50 character limit")
    
    return {
        "field": field,
        "valid": len(errors) == 0,
        "errors": errors
    }
