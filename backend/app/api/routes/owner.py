"""
Owner & Steward Assignment API Routes
Handles ownership management, assignment history, and approval workflows
"""

import logging
from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy import text

from backend.app.db import get_db_connection
from backend.app.auth import require_user
from backend.app.schemas.owner import (
    AssignOwnerRequest,
    AssignOwnerResponse,
    OwnerAssignmentHistory,
    OwnershipStats,
    TeamMember,
    OwnerRequest,
    OwnerRequestCreate,
    ApproveOwnerRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/owner", tags=["ownership"], dependencies=[Depends(require_user)])


# ═══════════════════════════════════════════════════════════════════
# Team Members
# ═══════════════════════════════════════════════════════════════════

@router.get("/team-members", response_model=list[TeamMember])
def list_team_members(
    active_only: bool = Query(True, description="Only return active members"),
    department: Optional[str] = Query(None, description="Filter by department")
):
    """
    List all team members who can be assigned as owners/stewards
    
    Parameters:
        active_only: Only return active team members
        department: Filter by department (e.g., "Data Engineering")
    
    Returns:
        List of team members
    """
    conn = get_db_connection()
    try:
        query = "SELECT id, email, name, title, department, slack_handle, is_active FROM team_member"
        filters = []
        params = []
        
        if active_only:
            filters.append("is_active = TRUE")
        
        if department:
            filters.append("department = %s")
            params.append(department)
        
        if filters:
            query += " WHERE " + " AND ".join(filters)
        
        query += " ORDER BY name"
        
        cur = conn.cursor(row_factory=dict)
        cur.execute(query, params)
        members = cur.fetchall()
        cur.close()
        conn.close()
        
        return [TeamMember(**m) for m in members]
    
    except Exception as e:
        logger.error(f"Error listing team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch team members")


@router.get("/team-members/search", response_model=list[TeamMember])
def search_team_members(
    q: str = Query(..., min_length=2, description="Search query (name or email)")
):
    """
    Search team members by name or email
    
    Parameters:
        q: Search query
    
    Returns:
        Matching team members
    """
    conn = get_db_connection()
    try:
        pattern = f"%{q.lower()}%"
        query = """
            SELECT id, email, name, title, department, slack_handle, is_active 
            FROM team_member
            WHERE LOWER(name) LIKE %(pattern)s 
               OR LOWER(email) LIKE %(pattern)s
            ORDER BY name
            LIMIT 20
        """
        
        cur = conn.cursor(row_factory=dict)
        cur.execute(query, {"pattern": pattern})
        members = cur.fetchall()
        cur.close()
        conn.close()
        
        return [TeamMember(**m) for m in members]
    
    except Exception as e:
        logger.error(f"Error searching team members: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


# ═══════════════════════════════════════════════════════════════════
# Owner Assignment
# ═══════════════════════════════════════════════════════════════════

@router.post("/assign/{asset_id}", response_model=AssignOwnerResponse)
def assign_owner(
    asset_id: str,
    request: AssignOwnerRequest,
    user: dict = Depends(require_user),
):
    """
    Assign owner or steward to a dataset
    
    Parameters:
        asset_id: Dataset ID to assign owner to
        request: Assignment request with email and reason
        user: Authenticated user resolved from the verified Supabase access token
    
    Returns:
        Confirmation of assignment
    """
    if not request.owner_email and not request.steward_email:
        raise HTTPException(status_code=400, detail="Provide an owner or steward email to assign")
    if request.requires_approval:
        raise HTTPException(status_code=400, detail="Use the owner request workflow for changes that require approval")

    conn = get_db_connection()
    try:
        # Get current owners
        cur = conn.cursor(row_factory=dict)
        cur.execute(
            "SELECT owner_name, steward_name FROM dataset WHERE id = %s",
            (asset_id,)
        )
        current = cur.fetchone()
        
        if not current:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Update dataset
        updates = []
        if request.owner_email:
            updates.append(("owner_name", request.owner_email))
            updates.append(("owner_id", request.owner_email))
            
            # Record assignment in audit trail
            cur.execute("""
                INSERT INTO owner_assignment 
                (dataset_id, assignment_type, previous_value, new_value, assigned_by, reason)
                VALUES (%s, 'OWNER', %s, %s, %s, %s)
            """, (asset_id, current["owner_name"], request.owner_email, user.get("email") or user["id"], request.reason))
        
        if request.steward_email:
            updates.append(("steward_name", request.steward_email))
            updates.append(("steward_id", request.steward_email))
            
            # Record assignment in audit trail
            cur.execute("""
                INSERT INTO owner_assignment 
                (dataset_id, assignment_type, previous_value, new_value, assigned_by, reason)
                VALUES (%s, 'STEWARD', %s, %s, %s, %s)
            """, (asset_id, current["steward_name"], request.steward_email, user.get("email") or user["id"], request.reason))
        
        # Update dataset record
        if updates:
            updates.append(("assigned_at", datetime.utcnow()))
            set_clause = ", ".join([f"{k} = %s" for k, v in updates])
            values = [v for k, v in updates]
            values.append(asset_id)
            
            cur.execute(f"UPDATE dataset SET {set_clause} WHERE id = %s", values)
        
        conn.commit()
        
        logger.info(f"Assigned owner to {asset_id}: {request.owner_email or request.steward_email}")
        
        return AssignOwnerResponse(
            dataset_id=UUID(asset_id),
            owner=request.owner_email,
            steward=request.steward_email,
            assigned_at=datetime.utcnow(),
            assigned_by=user.get("email") or user["id"],
            message="Assignment successful"
        )
    
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error assigning owner: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign owner")
    
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# Assignment History
# ═══════════════════════════════════════════════════════════════════

@router.get("/{asset_id}/history", response_model=OwnerAssignmentHistory)
def get_assignment_history(asset_id: str):
    """
    Get complete assignment history for a dataset
    
    Parameters:
        asset_id: Dataset ID
    
    Returns:
        Assignment history with all changes
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(row_factory=dict)
        
        # Get current assignment
        cur.execute("""
            SELECT owner_name, steward_name, assigned_at, last_modified_at
            FROM dataset
            WHERE id = %s
        """, (asset_id,))
        
        current = cur.fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Get assignment history
        cur.execute("""
            SELECT id, dataset_id, assignment_type, previous_value, new_value, 
                   assigned_by, assigned_at, reason
            FROM owner_assignment
            WHERE dataset_id = %s
            ORDER BY assigned_at DESC
        """, (asset_id,))
        
        history = cur.fetchall()
        cur.close()
        conn.close()
        
        return OwnerAssignmentHistory(
            dataset_id=UUID(asset_id),
            current_owner=current["owner_name"],
            current_steward=current["steward_name"],
            owner_assigned_at=current["assigned_at"],
            steward_assigned_at=current["last_modified_at"],
            history=history,
            total_changes=len(history)
        )
    
    except Exception as e:
        logger.error(f"Error fetching assignment history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


# ═══════════════════════════════════════════════════════════════════
# Ownership Statistics
# ═══════════════════════════════════════════════════════════════════

@router.get("/stats/overview", response_model=OwnershipStats)
def get_ownership_stats():
    """
    Get ownership coverage statistics
    
    Returns:
        Statistics on dataset ownership
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(row_factory=dict)
        
        # Total and assigned datasets
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(owner_name) as assigned,
                COUNT(*) - COUNT(owner_name) as unassigned
            FROM dataset
        """)
        
        counts = cur.fetchone()
        total = counts["total"] or 0
        assigned = counts["assigned"] or 0
        unassigned = counts["unassigned"] or 0
        coverage = (assigned / total * 100) if total > 0 else 0
        
        # Top owners
        cur.execute("""
            SELECT owner_name, COUNT(*) as dataset_count
            FROM dataset
            WHERE owner_name IS NOT NULL
            GROUP BY owner_name
            ORDER BY dataset_count DESC
            LIMIT 5
        """)
        
        top_owners = [(row["owner_name"], row["dataset_count"]) for row in cur.fetchall()]
        
        # Team sizes
        cur.execute("""
            SELECT department, COUNT(*) as member_count
            FROM team_member
            WHERE is_active = TRUE
            GROUP BY department
        """)
        
        team_sizes = {row["department"]: row["member_count"] for row in cur.fetchall()}
        
        cur.close()
        conn.close()
        
        return OwnershipStats(
            total_datasets=total,
            assigned_datasets=assigned,
            unassigned_datasets=unassigned,
            ownership_coverage_percent=coverage,
            team_sizes=team_sizes,
            top_owners=top_owners
        )
    
    except Exception as e:
        logger.error(f"Error calculating ownership stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate stats")


# ═══════════════════════════════════════════════════════════════════
# Owner Requests (Approval Workflow)
# ═══════════════════════════════════════════════════════════════════

@router.post("/request", response_model=OwnerRequest)
def create_owner_request(
    request: OwnerRequestCreate,
    user: dict = Depends(require_user),
):
    """
    Create an owner assignment request (requires approval)
    
    Parameters:
        request: Owner request details
        user: Authenticated user resolved from the verified Supabase access token
    
    Returns:
        Created owner request
    """
    conn = get_db_connection()
    try:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
        
        cur = conn.cursor(row_factory=dict)
        cur.execute("""
            INSERT INTO owner_request 
            (dataset_id, requested_by, requested_owner, reason, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (request.dataset_id, user.get("email") or user["id"], request.requested_owner, request.reason, expires_at))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Created owner request for {request.dataset_id}")
        
        return OwnerRequest(**result)
    
    except Exception as e:
        logger.error(f"Error creating owner request: {e}")
        raise HTTPException(status_code=500, detail="Failed to create request")


@router.get("/requests/pending", response_model=list[OwnerRequest])
def get_pending_requests():
    """Get pending owner assignment requests"""
    conn = get_db_connection()
    try:
        cur = conn.cursor(row_factory=dict)
        cur.execute("""
            SELECT * FROM owner_request
            WHERE status = 'PENDING'
            AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
        """)
        
        requests = cur.fetchall()
        cur.close()
        conn.close()
        
        return [OwnerRequest(**r) for r in requests]
    
    except Exception as e:
        logger.error(f"Error fetching pending requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch requests")


@router.post("/requests/{request_id}/approve")
def approve_owner_request(
    request_id: str,
    approval: ApproveOwnerRequest,
    user: dict = Depends(require_user),
):
    """Approve owner assignment request"""
    conn = get_db_connection()
    cur = None
    current_user = user.get("email") or user["id"]
    try:
        cur = conn.cursor(row_factory=dict)
        
        # Get request
        cur.execute(
            """SELECT *, (expires_at IS NULL OR expires_at > NOW()) AS is_active
               FROM owner_request WHERE id = %s FOR UPDATE""",
            (request_id,),
        )
        req = cur.fetchone()
        
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        if req["status"] != "PENDING" or not req["is_active"]:
            raise HTTPException(status_code=409, detail="Request is no longer pending or has expired")
        
        # Update request
        cur.execute("""
            UPDATE owner_request
            SET status = 'APPROVED', approved_by = %s, approved_at = NOW()
            WHERE id = %s
        """, (user.get("email") or user["id"], request_id))
        
        # Assign owner
        cur.execute("""
            UPDATE dataset
            SET owner_name = %s, assigned_by = %s, assigned_at = NOW()
            WHERE id = %s
        """, (req["requested_owner"], user.get("email") or user["id"], req["dataset_id"]))
        
        # Audit trail
        cur.execute("""
            INSERT INTO owner_assignment
            (dataset_id, assignment_type, new_value, assigned_by, reason)
            VALUES (%s, 'OWNER', %s, %s, %s)
        """, (req["dataset_id"], req["requested_owner"], current_user, approval.reason or req.get("reason")))
        
        conn.commit()
        logger.info(f"Approved owner request {request_id}")
        
        return {"status": "approved", "message": "Owner assignment approved"}
    
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error approving request: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve request")
    finally:
        if cur is not None:
            cur.close()
        conn.close()
