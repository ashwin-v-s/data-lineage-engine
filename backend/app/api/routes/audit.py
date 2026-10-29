"""
Audit Trail & Version History API Routes
Comprehensive change tracking and version management with validation, logging, and error handling
"""

import logging
import json
import hashlib
import time
from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from backend.app.db import get_db_connection
from backend.app.auth import require_user
from backend.app.api.errors import api_error
from backend.app.schemas.audit import (
    AuditTrailResponse,
    AuditLogEntry,
    VersionHistory,
    AssetVersion,
    VersionDiff,
    RollbackRequest,
    RollbackResponse,
    AuditStatistics,
    ComplianceReport,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_user)])

# ═══════════════════════════════════════════════════════════════════
# Constants & Configuration
# ═══════════════════════════════════════════════════════════════════

MAX_REQUESTS_PER_MINUTE = 100
RATE_LIMIT_STORE = {}  # {ip_address: [timestamp, ...]}
CACHE_CONTROL_HEADERS = {
    "Cache-Control": "public, max-age=300",  # 5 minutes
}


# ═══════════════════════════════════════════════════════════════════
# Validation Helpers
# ═══════════════════════════════════════════════════════════════════

def validate_uuid(value: str, field_name: str = "ID") -> UUID:
    """
    Validate and convert string to UUID
    
    Args:
        value: String value to validate
        field_name: Field name for error messages
        
    Returns:
        Valid UUID object
        
    Raises:
        ValueError: If not valid UUID format
    """
    try:
        return UUID(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid UUID format for {field_name}: {value}")
        raise ValueError(f"Invalid {field_name} format. Must be valid UUID.")


def validate_date_range(start_date: datetime, end_date: datetime, max_days: int = 365) -> bool:
    """
    Validate date range for audit queries
    
    Args:
        start_date: Start date
        end_date: End date
        max_days: Maximum allowed range in days
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If range is invalid
    """
    if start_date > end_date:
        raise ValueError("Start date cannot be after end date.")
    
    delta = (end_date - start_date).days
    if delta > max_days:
        raise ValueError(f"Date range cannot exceed {max_days} days.")
    
    return True


def validate_days_parameter(days: int, min_days: int = 1, max_days: int = 365) -> int:
    """
    Validate days query parameter
    
    Args:
        days: Number of days
        min_days: Minimum value
        max_days: Maximum value
        
    Returns:
        Validated days value
        
    Raises:
        ValueError: If value is out of range
    """
    if days < min_days or days > max_days:
        raise ValueError(f"Days must be between {min_days} and {max_days}.")
    return days


def validate_pagination_params(page: int, page_size: int) -> tuple:
    """
    Validate pagination parameters
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        
    Returns:
        Tuple of (page, page_size)
        
    Raises:
        ValueError: If parameters are invalid
    """
    if page < 1:
        raise ValueError("Page number must be >= 1.")
    if page_size < 1 or page_size > 1000:
        raise ValueError("Page size must be between 1 and 1000.")
    return page, page_size


def validate_field_selection(requested_fields: Optional[str]) -> list:
    """
    Validate and parse field selection parameter
    
    Args:
        requested_fields: Comma-separated field names
        
    Returns:
        List of valid field names
    """
    ALLOWED_FIELDS = [
        "id", "asset_id", "field_name", "old_value", "new_value",
        "changed_by", "change_type", "change_reason", "created_at"
    ]
    
    if not requested_fields:
        return ALLOWED_FIELDS
    
    fields = [f.strip() for f in requested_fields.split(",")]
    invalid_fields = [f for f in fields if f not in ALLOWED_FIELDS]
    
    if invalid_fields:
        raise ValueError(f"Invalid fields: {', '.join(invalid_fields)}")
    
    return fields if fields else ALLOWED_FIELDS


# ═══════════════════════════════════════════════════════════════════
# Rate Limiting
# ═══════════════════════════════════════════════════════════════════

def check_rate_limit(client_ip: str, limit: int = MAX_REQUESTS_PER_MINUTE, window_seconds: int = 60) -> bool:
    """
    Check if client has exceeded rate limit
    
    Args:
        client_ip: Client IP address
        limit: Maximum requests per window
        window_seconds: Time window in seconds
        
    Returns:
        True if within limit, raises HTTPException if exceeded
    """
    now = time.time()
    cutoff = now - window_seconds
    
    if client_ip not in RATE_LIMIT_STORE:
        RATE_LIMIT_STORE[client_ip] = []
    
    # Clean old entries
    RATE_LIMIT_STORE[client_ip] = [
        ts for ts in RATE_LIMIT_STORE[client_ip] if ts > cutoff
    ]
    
    if len(RATE_LIMIT_STORE[client_ip]) >= limit:
        logger.warning(f"Rate limit exceeded for IP {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 100 requests per minute."
        )
    
    RATE_LIMIT_STORE[client_ip].append(now)
    return True


# ═══════════════════════════════════════════════════════════════════
# Response Helpers
# ═══════════════════════════════════════════════════════════════════

def generate_etag(data: Any) -> str:
    """
    Generate ETag hash for response data
    
    Args:
        data: Response data
        
    Returns:
        ETag hash string
    """
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(json_str.encode()).hexdigest()


def filter_fields(record: Dict[str, Any], fields: list) -> Dict[str, Any]:
    """
    Filter record to only include requested fields
    
    Args:
        record: Full record dictionary
        fields: List of allowed fields
        
    Returns:
        Filtered record
    """
    return {k: v for k, v in record.items() if k in fields}


def create_error_response(
    message: str,
    error_code: str,
    status_code: int = 400,
    request_id: str = None
) -> JSONResponse:
    """
    Create structured error response
    
    Args:
        message: Error message
        error_code: Error code identifier
        status_code: HTTP status code
        request_id: Request ID for tracking
        
    Returns:
        JSONResponse with structured error
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "error_code": error_code,
                "request_id": request_id or "unknown",
            }
        }
    )


# ═══════════════════════════════════════════════════════════════════
# Logging Helpers
# ═══════════════════════════════════════════════════════════════════

def log_operation(operation: str, asset_id: str, status: str, duration_ms: float = None, details: str = None):
    """
    Log audit operation with timing
    
    Args:
        operation: Operation name
        asset_id: Asset ID
        status: Operation status (SUCCESS, FAILED, etc.)
        duration_ms: Operation duration in milliseconds
        details: Additional details
    """
    msg = f"AUDIT_OP: operation={operation}, asset_id={asset_id}, status={status}"
    if duration_ms:
        msg += f", duration_ms={duration_ms:.2f}"
    if details:
        msg += f", details={details}"
    
    if status == "SUCCESS":
        logger.info(msg)
    elif status == "FAILED":
        logger.error(msg)
    else:
        logger.debug(msg)


# ═══════════════════════════════════════════════════════════════════
# Audit Trail Endpoint
# ═══════════════════════════════════════════════════════════════════

@router.get("/{asset_id}/trail")
def get_audit_trail(
    request: Request,
    asset_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    field_filter: Optional[str] = Query(None, description="Filter by field name"),
    user_filter: Optional[str] = Query(None, description="Filter by user"),
    fields: Optional[str] = Query(None, description="Comma-separated field names to return")
):
    """
    Get complete audit trail for an asset with pagination and field selection
    
    Parameters:
        asset_id: Asset ID (must be valid UUID)
        days: Number of days to look back (1-365)
        page: Page number for pagination (1-indexed)
        page_size: Items per page (1-500)
        field_filter: Optional field name filter
        user_filter: Optional user filter
        fields: Comma-separated fields to return
    
    Returns:
        Paginated audit trail with all changes
        
    Status Codes:
        200: Success
        400: Invalid input parameters
        404: Asset not found
        429: Rate limit exceeded
        500: Server error
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.debug(f"[{request_id}] GET audit trail: asset_id={asset_id}, days={days}, page={page}")
    
    try:
        # Rate limiting check
        check_rate_limit(client_ip)
        
        # Input validation
        try:
            asset_uuid = validate_uuid(asset_id, "asset_id")
            days = validate_days_parameter(days)
            page, page_size = validate_pagination_params(page, page_size)
            selected_fields = validate_field_selection(fields)
            logger.debug(f"[{request_id}] Input validation passed")
        except ValueError as e:
            logger.warning(f"[{request_id}] Input validation failed: {str(e)}")
            return create_error_response(
                message=str(e),
                error_code="INVALID_INPUT",
                status_code=400,
                request_id=request_id
            )
        
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict)
        
        # Verify asset exists
        cur.execute("SELECT id, name FROM dataset WHERE id = %s", (str(asset_uuid),))
        asset = cur.fetchone()
        if not asset:
            logger.info(f"[{request_id}] Asset not found: {asset_id}")
            cur.close()
            conn.close()
            return create_error_response(
                message=f"Asset with ID {asset_id} not found",
                error_code="ASSET_NOT_FOUND",
                status_code=404,
                request_id=request_id
            )
        
        logger.debug(f"[{request_id}] Asset verified: {asset['name']}")
        
        # Build query with filters
        query = f"""
            SELECT id, asset_id, field_name, old_value, new_value, changed_by, change_type, change_reason, created_at
            FROM audit_log
            WHERE asset_id = %s
            AND created_at >= NOW() - INTERVAL '{days} days'
        """
        
        params = [str(asset_uuid)]
        
        if field_filter:
            query += " AND field_name = %s"
            params.append(field_filter)
            logger.debug(f"[{request_id}] Applied field filter: {field_filter}")
        
        if user_filter:
            query += " AND changed_by = %s"
            params.append(user_filter)
            logger.debug(f"[{request_id}] Applied user filter: {user_filter}")
        
        # Get total count for pagination
        count_query = query.replace(
            "SELECT id, asset_id, field_name, old_value, new_value, changed_by, change_type, change_reason, created_at",
            "SELECT COUNT(*) as total"
        )
        cur.execute(count_query, params)
        total_count = cur.fetchone()["total"]
        logger.debug(f"[{request_id}] Total audit records: {total_count}")
        
        # Add pagination
        offset = (page - 1) * page_size
        query += f" ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([page_size, offset])
        
        # Execute main query
        cur.execute(query, params)
        entries = cur.fetchall()
        
        # Filter to selected fields only
        filtered_entries = [filter_fields(entry, selected_fields) for entry in entries]
        
        logger.debug(f"[{request_id}] Retrieved {len(filtered_entries)} audit records")
        
        # Get date range
        if entries:
            latest = entries[0]["created_at"]
            oldest = entries[-1]["created_at"]
        else:
            now = datetime.utcnow()
            latest = now
            oldest = now - timedelta(days=days)
        
        # Calculate summary
        summary = {}
        for entry in entries:
            field = entry["field_name"]
            summary[field] = summary.get(field, 0) + 1
        
        cur.close()
        conn.close()
        
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_AUDIT_TRAIL", asset_id, "SUCCESS", duration_ms, f"records={len(filtered_entries)}")
        
        response_data = {
            "asset_id": str(asset_uuid),
            "asset_name": asset["name"],
            "total_changes": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size,
            "date_range": (oldest.isoformat() if isinstance(oldest, datetime) else oldest, 
                          latest.isoformat() if isinstance(latest, datetime) else latest),
            "entries": filtered_entries,
            "summary": summary
        }
        
        etag = generate_etag(response_data)
        
        response = JSONResponse(content=jsonable_encoder(response_data))
        response.headers.update(CACHE_CONTROL_HEADERS)
        response.headers["ETag"] = etag
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
    
    except HTTPException as e:
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_AUDIT_TRAIL", asset_id, "FAILED", duration_ms, str(e.detail))
        raise
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unexpected error in get_audit_trail: {str(e)}", exc_info=True)
        log_operation("GET_AUDIT_TRAIL", asset_id, "FAILED", duration_ms, str(e))
        return create_error_response(
            message="Failed to fetch audit trail",
            error_code="AUDIT_FETCH_ERROR",
            status_code=500,
            request_id=request_id
        )


# ═══════════════════════════════════════════════════════════════════
# Version History Endpoint
# ═══════════════════════════════════════════════════════════════════

@router.get("/{asset_id}/versions")
def get_version_history(
    request: Request,
    asset_id: str
):
    """
    Get complete version history for an asset
    
    Parameters:
        asset_id: Asset ID (must be valid UUID)
    
    Returns:
        Version history with all snapshots
        
    Status Codes:
        200: Success
        400: Invalid asset_id format
        404: Asset not found
        429: Rate limit exceeded
        500: Server error
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.debug(f"[{request_id}] GET version history: asset_id={asset_id}")
    
    try:
        # Rate limiting
        check_rate_limit(client_ip)
        
        # Input validation
        try:
            asset_uuid = validate_uuid(asset_id, "asset_id")
            logger.debug(f"[{request_id}] Asset UUID validated")
        except ValueError as e:
            logger.warning(f"[{request_id}] UUID validation failed: {str(e)}")
            return create_error_response(
                message=str(e),
                error_code="INVALID_ASSET_ID",
                status_code=400,
                request_id=request_id
            )
        
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict)
        
        # Verify asset exists
        cur.execute("SELECT id FROM dataset WHERE id = %s", (str(asset_uuid),))
        if not cur.fetchone():
            logger.info(f"[{request_id}] Asset not found: {asset_id}")
            cur.close()
            conn.close()
            return create_error_response(
                message=f"Asset with ID {asset_id} not found",
                error_code="ASSET_NOT_FOUND",
                status_code=404,
                request_id=request_id
            )
        
        # Get all versions
        cur.execute("""
            SELECT id, asset_id, version_number, snapshot_data, created_by, 
                   created_at, change_summary, is_release, release_notes
            FROM asset_version
            WHERE asset_id = %s
            ORDER BY version_number DESC
        """, (str(asset_uuid),))
        
        versions = cur.fetchall()
        logger.debug(f"[{request_id}] Retrieved {len(versions)} versions")
        current_version = versions[0]["version_number"] if versions else 1
        
        cur.close()
        conn.close()
        
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_VERSION_HISTORY", asset_id, "SUCCESS", duration_ms, f"versions={len(versions)}")
        
        response_data = {
            "asset_id": str(asset_uuid),
            "current_version": current_version,
            "total_versions": len(versions),
            "versions": versions
        }
        
        etag = generate_etag(response_data)
        
        response = JSONResponse(content=jsonable_encoder(response_data))
        response.headers.update(CACHE_CONTROL_HEADERS)
        response.headers["ETag"] = etag
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
    
    except HTTPException as e:
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_VERSION_HISTORY", asset_id, "FAILED", duration_ms, str(e.detail))
        raise
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unexpected error in get_version_history: {str(e)}", exc_info=True)
        log_operation("GET_VERSION_HISTORY", asset_id, "FAILED", duration_ms, str(e))
        return create_error_response(
            message="Failed to fetch version history",
            error_code="VERSION_HISTORY_ERROR",
            status_code=500,
            request_id=request_id
        )


# ═══════════════════════════════════════════════════════════════════
# Version Diff Endpoint
# ═══════════════════════════════════════════════════════════════════

@router.get("/{asset_id}/versions/diff")
def get_version_diff(
    request: Request,
    asset_id: str,
    from_version: int = Query(..., ge=1),
    to_version: int = Query(..., ge=1)
):
    """
    Get diff between two versions
    
    Parameters:
        asset_id: Asset ID (must be valid UUID)
        from_version: Starting version (>= 1)
        to_version: Ending version (>= 1)
    
    Returns:
        Diff showing what changed between versions
        
    Status Codes:
        200: Success
        400: Invalid parameters
        404: Asset or version not found
        429: Rate limit exceeded
        500: Server error
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.debug(f"[{request_id}] GET version diff: asset_id={asset_id}, from_v={from_version}, to_v={to_version}")
    
    try:
        # Rate limiting
        check_rate_limit(client_ip)
        
        # Input validation
        try:
            asset_uuid = validate_uuid(asset_id, "asset_id")
            if from_version < 1 or to_version < 1:
                raise ValueError("Version numbers must be >= 1")
            if from_version == to_version:
                raise ValueError("from_version and to_version must be different")
            logger.debug(f"[{request_id}] Input validation passed")
        except ValueError as e:
            logger.warning(f"[{request_id}] Input validation failed: {str(e)}")
            return create_error_response(
                message=str(e),
                error_code="INVALID_INPUT",
                status_code=400,
                request_id=request_id
            )
        
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict)
        
        # Get both versions
        cur.execute("""
            SELECT snapshot_data FROM asset_version
            WHERE asset_id = %s AND version_number = %s
        """, (str(asset_uuid), from_version))
        
        from_snap = cur.fetchone()
        if not from_snap:
            logger.info(f"[{request_id}] From version not found: {from_version}")
            cur.close()
            conn.close()
            return create_error_response(
                message=f"Version {from_version} not found for asset {asset_id}",
                error_code="VERSION_NOT_FOUND",
                status_code=404,
                request_id=request_id
            )
        
        cur.execute("""
            SELECT snapshot_data FROM asset_version
            WHERE asset_id = %s AND version_number = %s
        """, (str(asset_uuid), to_version))
        
        to_snap = cur.fetchone()
        if not to_snap:
            logger.info(f"[{request_id}] To version not found: {to_version}")
            cur.close()
            conn.close()
            return create_error_response(
                message=f"Version {to_version} not found for asset {asset_id}",
                error_code="VERSION_NOT_FOUND",
                status_code=404,
                request_id=request_id
            )
        
        logger.debug(f"[{request_id}] Both versions retrieved, calculating diff")
        
        # Parse JSON data
        try:
            from_data = from_snap["snapshot_data"] if isinstance(from_snap["snapshot_data"], dict) else json.loads(from_snap["snapshot_data"])
            to_data = to_snap["snapshot_data"] if isinstance(to_snap["snapshot_data"], dict) else json.loads(to_snap["snapshot_data"])
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"[{request_id}] Failed to parse snapshot data: {str(e)}")
            cur.close()
            conn.close()
            return create_error_response(
                message="Failed to parse version snapshot data",
                error_code="SNAPSHOT_PARSE_ERROR",
                status_code=500,
                request_id=request_id
            )
        
        cur.close()
        conn.close()
        
        # Calculate diff
        added = {}
        modified = {}
        removed = {}
        
        for key, to_value in to_data.items():
            if key not in from_data:
                added[key] = to_value
            elif from_data[key] != to_value:
                modified[key] = (from_data[key], to_value)
        
        for key in from_data:
            if key not in to_data:
                removed[key] = from_data[key]
        
        duration_ms = (time.time() - start_time) * 1000
        log_operation(
            "GET_VERSION_DIFF",
            asset_id,
            "SUCCESS",
            duration_ms,
            f"added={len(added)}, modified={len(modified)}, removed={len(removed)}"
        )
        
        response_data = {
            "from_version": from_version,
            "to_version": to_version,
            "added_fields": added,
            "modified_fields": modified,
            "removed_fields": removed,
            "change_summary": f"Added: {len(added)}, Modified: {len(modified)}, Removed: {len(removed)}"
        }
        
        etag = generate_etag(response_data)
        
        response = JSONResponse(content=jsonable_encoder(response_data))
        response.headers.update(CACHE_CONTROL_HEADERS)
        response.headers["ETag"] = etag
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
    
    except HTTPException as e:
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_VERSION_DIFF", asset_id, "FAILED", duration_ms, str(e.detail))
        raise
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unexpected error in get_version_diff: {str(e)}", exc_info=True)
        log_operation("GET_VERSION_DIFF", asset_id, "FAILED", duration_ms, str(e))
        return create_error_response(
            message="Failed to calculate diff",
            error_code="DIFF_CALCULATION_ERROR",
            status_code=500,
            request_id=request_id
        )


# ═══════════════════════════════════════════════════════════════════
# Statistics Endpoint
# ═══════════════════════════════════════════════════════════════════

@router.get("/{asset_id}/statistics")
def get_audit_statistics(
    request: Request,
    asset_id: str,
    days: int = Query(30, ge=1, le=365)
):
    """Get audit statistics for an asset"""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.debug(f"[{request_id}] GET audit statistics: asset_id={asset_id}, days={days}")
    
    try:
        # Rate limiting
        check_rate_limit(client_ip)
        
        # Input validation
        try:
            asset_uuid = validate_uuid(asset_id, "asset_id")
            days = validate_days_parameter(days)
        except ValueError as e:
            logger.warning(f"[{request_id}] Input validation failed: {str(e)}")
            return create_error_response(
                message=str(e),
                error_code="INVALID_INPUT",
                status_code=400,
                request_id=request_id
            )
        
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict)
        
        # Total changes by type
        cur.execute(f"""
            SELECT COUNT(*) as total, change_type
            FROM audit_log
            WHERE asset_id = %s AND created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY change_type
        """, (str(asset_uuid),))
        
        changes_by_type = {row["change_type"]: row["total"] for row in cur.fetchall()}
        total = sum(changes_by_type.values())
        
        # Changes by field
        cur.execute(f"""
            SELECT COUNT(*) as total, field_name
            FROM audit_log
            WHERE asset_id = %s AND created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY field_name
            ORDER BY total DESC
        """, (str(asset_uuid),))
        
        changes_by_field = {row["field_name"]: row["total"] for row in cur.fetchall()}
        
        # Top changers
        cur.execute(f"""
            SELECT COUNT(*) as total, changed_by
            FROM audit_log
            WHERE asset_id = %s AND created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY changed_by
            ORDER BY total DESC
            LIMIT 5
        """, (str(asset_uuid),))
        
        top_changers = [(row["changed_by"], row["total"]) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_AUDIT_STATISTICS", asset_id, "SUCCESS", duration_ms, f"total_changes={total}")
        
        now = datetime.utcnow()
        response_data = {
            "total_changes": total,
            "changes_by_type": changes_by_type,
            "changes_by_field": changes_by_field,
            "top_changers": top_changers,
            "date_range": (
                (now - timedelta(days=days)).isoformat(),
                now.isoformat()
            )
        }
        
        etag = generate_etag(response_data)
        
        response = JSONResponse(content=jsonable_encoder(response_data))
        response.headers.update(CACHE_CONTROL_HEADERS)
        response.headers["ETag"] = etag
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
    
    except HTTPException as e:
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_AUDIT_STATISTICS", asset_id, "FAILED", duration_ms, str(e.detail))
        raise
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unexpected error in get_audit_statistics: {str(e)}", exc_info=True)
        log_operation("GET_AUDIT_STATISTICS", asset_id, "FAILED", duration_ms, str(e))
        return create_error_response(
            message="Failed to calculate statistics",
            error_code="STATISTICS_ERROR",
            status_code=500,
            request_id=request_id
        )


# ═══════════════════════════════════════════════════════════════════
# Compliance Report Endpoint
# ═══════════════════════════════════════════════════════════════════

@router.get("/{asset_id}/compliance-report")
def get_compliance_report(
    request: Request,
    asset_id: str,
    days: int = Query(30, ge=1, le=365)
):
    """Get compliance & governance report"""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.debug(f"[{request_id}] GET compliance report: asset_id={asset_id}, days={days}")
    
    try:
        # Rate limiting
        check_rate_limit(client_ip)
        
        # Input validation
        try:
            asset_uuid = validate_uuid(asset_id, "asset_id")
            days = validate_days_parameter(days)
        except ValueError as e:
            logger.warning(f"[{request_id}] Input validation failed: {str(e)}")
            return create_error_response(
                message=str(e),
                error_code="INVALID_INPUT",
                status_code=400,
                request_id=request_id
            )
        
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict)
        
        # Get asset name
        cur.execute("SELECT name FROM dataset WHERE id = %s", (str(asset_uuid),))
        asset = cur.fetchone()
        if not asset:
            logger.info(f"[{request_id}] Asset not found: {asset_id}")
            cur.close()
            conn.close()
            return create_error_response(
                message=f"Asset with ID {asset_id} not found",
                error_code="ASSET_NOT_FOUND",
                status_code=404,
                request_id=request_id
            )
        
        # Count audit events by severity
        cur.execute(f"""
            SELECT COUNT(*) as total, severity
            FROM audit_event
            WHERE asset_id = %s AND created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY severity
        """, (str(asset_uuid),))
        
        events = {row["severity"]: row["total"] for row in cur.fetchall()}
        critical = events.get("CRITICAL", 0)
        
        # Count changes and rollbacks
        cur.execute(f"""
            SELECT COUNT(*) as total FROM audit_log
            WHERE asset_id = %s AND created_at >= NOW() - INTERVAL '{days} days'
        """, (str(asset_uuid),))
        total_changes = cur.fetchone()["total"]
        
        cur.execute(f"""
            SELECT COUNT(*) as total FROM rollback_record
            WHERE asset_id = %s AND created_at >= NOW() - INTERVAL '{days} days'
        """, (str(asset_uuid),))
        rollbacks = cur.fetchone()["total"]
        
        # Count lineage changes
        cur.execute(f"""
            SELECT COUNT(*) as total FROM audit_log
            WHERE asset_id = %s AND field_name LIKE 'lineage%%'
            AND created_at >= NOW() - INTERVAL '{days} days'
        """, (str(asset_uuid),))
        lineage_changes = cur.fetchone()["total"]
        
        # Count ownership changes
        cur.execute(f"""
            SELECT COUNT(*) as total FROM owner_assignment
            WHERE dataset_id = %s AND assigned_at >= NOW() - INTERVAL '{days} days'
        """, (str(asset_uuid),))
        ownership_changes = cur.fetchone()["total"]
        
        cur.close()
        conn.close()
        
        # Calculate compliance score
        score = 100.0
        score -= critical * 10  # Penalize critical events
        score -= rollbacks * 5  # Penalize rollbacks
        score = max(0, min(100, score))  # Clamp 0-100
        
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_COMPLIANCE_REPORT", asset_id, "SUCCESS", duration_ms, f"score={score:.1f}")
        
        now = datetime.utcnow()
        response_data = {
            "asset_id": str(asset_uuid),
            "asset_name": asset["name"],
            "report_period": (
                (now - timedelta(days=days)).isoformat(),
                now.isoformat()
            ),
            "total_changes": total_changes,
            "critical_events": critical,
            "unapproved_changes": 0,
            "rollbacks": rollbacks,
            "data_lineage_changes": lineage_changes,
            "ownership_changes": ownership_changes,
            "access_violations": 0,
            "compliance_score": score
        }
        
        etag = generate_etag(response_data)
        
        response = JSONResponse(content=jsonable_encoder(response_data))
        response.headers.update(CACHE_CONTROL_HEADERS)
        response.headers["ETag"] = etag
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
    
    except HTTPException as e:
        duration_ms = (time.time() - start_time) * 1000
        log_operation("GET_COMPLIANCE_REPORT", asset_id, "FAILED", duration_ms, str(e.detail))
        raise
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unexpected error in get_compliance_report: {str(e)}", exc_info=True)
        log_operation("GET_COMPLIANCE_REPORT", asset_id, "FAILED", duration_ms, str(e))
        return create_error_response(
            message="Failed to generate compliance report",
            error_code="COMPLIANCE_REPORT_ERROR",
            status_code=500,
            request_id=request_id
        )


# ═══════════════════════════════════════════════════════════════════
# Rollback Endpoint
# ═══════════════════════════════════════════════════════════════════

@router.post("/{asset_id}/rollback")
def request_rollback(
    request: Request,
    asset_id: str,
    rollback_request: RollbackRequest,
    user: dict = Depends(require_user),
):
    """
    Request rollback to previous version (with approval workflow)
    
    Parameters:
        asset_id: Asset ID (must be valid UUID)
        rollback_request: Rollback details
        current_user: User requesting rollback
    
    Returns:
        Rollback request with status
        
    Status Codes:
        200: Success
        400: Invalid input
        404: Asset not found
        429: Rate limit exceeded
        500: Server error
    """
    current_user = user.get("email") or user["id"]
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.debug(f"[{request_id}] POST rollback: asset_id={asset_id}")
    
    try:
        # Rate limiting
        check_rate_limit(client_ip)
        
        # Input validation
        try:
            asset_uuid = validate_uuid(asset_id, "asset_id")
            if rollback_request.from_version < 1 or rollback_request.to_version < 1:
                raise ValueError("Version numbers must be >= 1")
            if rollback_request.from_version == rollback_request.to_version:
                raise ValueError("Versions must be different")
            if not rollback_request.rollback_reason or len(rollback_request.rollback_reason) < 10:
                raise ValueError("Rollback reason must be at least 10 characters")
            logger.debug(f"[{request_id}] Input validation passed")
        except ValueError as e:
            logger.warning(f"[{request_id}] Input validation failed: {str(e)}")
            return create_error_response(
                message=str(e),
                error_code="INVALID_INPUT",
                status_code=400,
                request_id=request_id
            )
        
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict)
        
        try:
            cur.execute("""
                INSERT INTO rollback_record
                (asset_id, from_version, to_version, rollback_reason, requested_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
            """, (
                str(asset_uuid),
                rollback_request.from_version,
                rollback_request.to_version,
                rollback_request.rollback_reason,
                current_user
            ))
            
            result = cur.fetchone()
            conn.commit()
            
            duration_ms = (time.time() - start_time) * 1000
            log_operation(
                "POST_ROLLBACK",
                asset_id,
                "SUCCESS",
                duration_ms,
                f"v{rollback_request.from_version}->v{rollback_request.to_version}"
            )
            
            logger.info(f"[{request_id}] Rollback created: {result['id']}")
            
            response_data = {
                "rollback_id": str(result["id"]),
                "asset_id": str(asset_uuid),
                "from_version": rollback_request.from_version,
                "to_version": rollback_request.to_version,
                "status": "PENDING",
                "requested_by": current_user,
                "created_at": result["created_at"].isoformat() if isinstance(result["created_at"], datetime) else result["created_at"],
                "message": "Rollback request created. Awaiting approval."
            }
            
            response = JSONResponse(content=jsonable_encoder(response_data), status_code=200)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            return response
        
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
    
    except HTTPException as e:
        duration_ms = (time.time() - start_time) * 1000
        log_operation("POST_ROLLBACK", asset_id, "FAILED", duration_ms, str(e.detail))
        raise
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unexpected error in request_rollback: {str(e)}", exc_info=True)
        log_operation("POST_ROLLBACK", asset_id, "FAILED", duration_ms, str(e))
        return create_error_response(
            message="Failed to create rollback request",
            error_code="ROLLBACK_ERROR",
            status_code=500,
            request_id=request_id
        )


# ═══════════════════════════════════════════════════════════════════
# Export Endpoint
# ═══════════════════════════════════════════════════════════════════

@router.post("/{asset_id}/export-audit")
def export_audit_trail(
    request: Request,
    asset_id: str,
    format: str = Query("json", regex="^(csv|json)$"),
    days: int = Query(30, ge=1, le=365)
):
    """
    Export audit trail in specified format
    
    Parameters:
        asset_id: Asset ID (must be valid UUID)
        format: Export format (csv, json)
        days: Days to include
    
    Returns:
        Exported audit trail as file
        
    Status Codes:
        200: Success
        400: Invalid input
        404: Asset not found
        429: Rate limit exceeded
        500: Server error
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.debug(f"[{request_id}] POST export-audit: asset_id={asset_id}, format={format}")
    
    try:
        # Rate limiting
        check_rate_limit(client_ip)
        
        # Input validation
        try:
            asset_uuid = validate_uuid(asset_id, "asset_id")
            days = validate_days_parameter(days)
            if format not in ["csv", "json"]:
                raise ValueError("Format must be 'csv' or 'json'")
            logger.debug(f"[{request_id}] Input validation passed")
        except ValueError as e:
            logger.warning(f"[{request_id}] Input validation failed: {str(e)}")
            return create_error_response(
                message=str(e),
                error_code="INVALID_INPUT",
                status_code=400,
                request_id=request_id
            )
        
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict)
        
        # Get audit entries
        cur.execute(f"""
            SELECT id, field_name, old_value, new_value, changed_by, change_type, created_at
            FROM audit_log
            WHERE asset_id = %s AND created_at >= NOW() - INTERVAL '{days} days'
            ORDER BY created_at DESC
        """, (str(asset_uuid),))
        
        entries = cur.fetchall()
        
        cur.close()
        conn.close()
        
        logger.debug(f"[{request_id}] Retrieved {len(entries)} entries for export")
        
        if format == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=["Timestamp", "Field", "Old Value", "New Value", "Changed By", "Type"]
            )
            writer.writeheader()
            for entry in entries:
                writer.writerow({
                    "Timestamp": entry["created_at"],
                    "Field": entry["field_name"],
                    "Old Value": entry["old_value"],
                    "New Value": entry["new_value"],
                    "Changed By": entry["changed_by"],
                    "Type": entry["change_type"]
                })
            
            duration_ms = (time.time() - start_time) * 1000
            log_operation("EXPORT_AUDIT", asset_id, "SUCCESS", duration_ms, f"format=csv, entries={len(entries)}")
            
            response_data = {"data": output.getvalue(), "format": "csv", "entry_count": len(entries)}
            response = JSONResponse(content=jsonable_encoder(response_data))
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            return response
        
        else:  # json
            # Convert datetime objects to ISO format strings
            export_data = []
            for entry in entries:
                entry_dict = dict(entry)
                if isinstance(entry_dict.get("created_at"), datetime):
                    entry_dict["created_at"] = entry_dict["created_at"].isoformat()
                export_data.append(entry_dict)
            
            duration_ms = (time.time() - start_time) * 1000
            log_operation("EXPORT_AUDIT", asset_id, "SUCCESS", duration_ms, f"format=json, entries={len(entries)}")
            
            response_data = {"data": export_data, "format": "json", "entry_count": len(entries)}
            response = JSONResponse(content=jsonable_encoder(response_data))
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            return response
    
    except HTTPException as e:
        duration_ms = (time.time() - start_time) * 1000
        log_operation("EXPORT_AUDIT", asset_id, "FAILED", duration_ms, str(e.detail))
        raise
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unexpected error in export_audit_trail: {str(e)}", exc_info=True)
        log_operation("EXPORT_AUDIT", asset_id, "FAILED", duration_ms, str(e))
        return create_error_response(
            message="Failed to export audit trail",
            error_code="EXPORT_ERROR",
            status_code=500,
            request_id=request_id
        )
