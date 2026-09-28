"""
Canonical identity functions (M3).
Generates deterministic IDs for datasets, columns, jobs, and edges.
Uses UUID v5 (namespace-based, deterministic) so the same entity always gets the same ID.
"""
import hashlib
import uuid
from typing import Optional, Tuple


# Namespace UUIDs for different entity types
# Generated once with uuid.uuid4(), then frozen
NAMESPACE_DATASET = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
NAMESPACE_COLUMN = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c9")
NAMESPACE_JOB = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430ca")
NAMESPACE_EDGE = uuid.UUID("6ba7b813-9dad-11d1-80b4-00c04fd430cb")


def normalize_identifier(name: str) -> str:
    """
    Normalize an identifier for canonical ID generation.
    
    Handles:
    - Case differences (convert to lowercase)
    - Quoted identifiers (strip quotes)
    - Whitespace (strip and normalize)
    
    Args:
        name: Raw identifier from source system
    
    Returns:
        Normalized identifier
    
    Examples:
        >>> normalize_identifier('  MyTable  ')
        'mytable'
        >>> normalize_identifier('"Quoted Table"')
        'quoted table'
        >>> normalize_identifier('EMPLOYEES')
        'employees'
    """
    # Strip whitespace
    name = name.strip()
    
    # Remove quotes if present
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    
    # Convert to lowercase (SQL standard)
    name = name.lower()
    
    return name


def dataset_id(
    source_system: str,
    namespace: str,
    database: str,
    schema: str,
    name: str,
    asset_type: str
) -> uuid.UUID:
    """
    Generate canonical dataset ID from identity tuple.
    
    Same tuple always produces the same UUID (deterministic).
    
    Args:
        source_system: e.g., 'sqlglot', 'dbt', 'openlineage'
        namespace: e.g., 'postgres://localhost:5432'
        database: database name
        schema: schema name
        name: table/view name
        asset_type: 'table', 'view', 'model', etc.
    
    Returns:
        Deterministic UUID v5
    
    Examples:
        >>> id1 = dataset_id('dbt', 'prod', 'analytics', 'public', 'users', 'table')
        >>> id2 = dataset_id('dbt', 'prod', 'analytics', 'public', 'users', 'table')
        >>> id1 == id2
        True
    """
    # Normalize all components
    components = (
        normalize_identifier(source_system),
        normalize_identifier(namespace),
        normalize_identifier(database),
        normalize_identifier(schema),
        normalize_identifier(name),
        normalize_identifier(asset_type),
    )
    
    # Create canonical string
    canonical = "|".join(components)
    
    # Generate UUID v5
    return uuid.uuid5(NAMESPACE_DATASET, canonical)


def column_id(
    dataset_uuid: uuid.UUID,
    column_name: str,
    schema_version: str = "v1"
) -> uuid.UUID:
    """
    Generate canonical column ID.
    
    Args:
        dataset_uuid: UUID of the parent dataset
        column_name: column name
        schema_version: schema version (default: 'v1')
    
    Returns:
        Deterministic UUID v5
    
    Examples:
        >>> ds_id = dataset_id('dbt', 'prod', 'analytics', 'public', 'users', 'table')
        >>> col_id = column_id(ds_id, 'email', 'v1')
        >>> isinstance(col_id, uuid.UUID)
        True
    """
    canonical = f"{dataset_uuid}|{normalize_identifier(column_name)}|{schema_version}"
    return uuid.uuid5(NAMESPACE_COLUMN, canonical)


def job_id(namespace: str, name: str) -> uuid.UUID:
    """
    Generate canonical job ID.
    
    Args:
        namespace: job namespace (e.g., 'airflow_prod')
        name: job name
    
    Returns:
        Deterministic UUID v5
    """
    canonical = f"{normalize_identifier(namespace)}|{normalize_identifier(name)}"
    return uuid.uuid5(NAMESPACE_JOB, canonical)


def edge_id(
    source_uuid: uuid.UUID,
    target_uuid: uuid.UUID,
    granularity: str,
    operator_fingerprint: Optional[str] = None,
    query_fingerprint: Optional[str] = None
) -> uuid.UUID:
    """
    Generate canonical edge ID.
    
    Args:
        source_uuid: source entity UUID (dataset or column)
        target_uuid: target entity UUID (dataset or column)
        granularity: 'DATASET', 'COLUMN', 'TUPLE_CELL'
        operator_fingerprint: optional operator hash
        query_fingerprint: optional query hash
    
    Returns:
        Deterministic UUID v5
    """
    parts = [
        str(source_uuid),
        str(target_uuid),
        normalize_identifier(granularity),
    ]
    
    if operator_fingerprint:
        parts.append(operator_fingerprint)
    if query_fingerprint:
        parts.append(query_fingerprint)
    
    canonical = "|".join(parts)
    return uuid.uuid5(NAMESPACE_EDGE, canonical)


def fingerprint_sql(sql: str, dialect: str = "postgres") -> str:
    """
    Generate a fingerprint for a SQL query.
    
    Uses SHA-256 to create a short, deterministic hash.
    
    Args:
        sql: SQL query string
        dialect: SQL dialect (for future normalization)
    
    Returns:
        16-character hex fingerprint
    
    Examples:
        >>> fp1 = fingerprint_sql("SELECT * FROM users")
        >>> fp2 = fingerprint_sql("SELECT * FROM users")
        >>> fp1 == fp2
        True
        >>> len(fp1)
        16
    """
    # Normalize whitespace
    normalized = " ".join(sql.split())
    
    # Generate SHA-256 hash
    hash_obj = hashlib.sha256(normalized.encode("utf-8"))
    
    # Return first 16 hex characters (64 bits)
    return hash_obj.hexdigest()[:16]


def fingerprint_schema(schema_dict: dict) -> str:
    """
    Generate a fingerprint for a schema definition.
    
    Args:
        schema_dict: Schema as dict (e.g., {"table": {"col1": "int", "col2": "text"}})
    
    Returns:
        16-character hex fingerprint
    
    Examples:
        >>> schema = {"users": {"id": "int", "email": "text"}}
        >>> fp = fingerprint_schema(schema)
        >>> len(fp)
        16
    """
    # Sort keys for deterministic output
    import json
    canonical = json.dumps(schema_dict, sort_keys=True, separators=(",", ":"))
    
    hash_obj = hashlib.sha256(canonical.encode("utf-8"))
    return hash_obj.hexdigest()[:16]


# Validation helpers

def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def parse_dataset_components(dataset_id_str: str) -> Optional[Tuple[str, ...]]:
    """
    Parse a dataset ID back to its components (if stored somewhere).
    
    Note: This is NOT reversible from UUID alone. 
    Components must be stored in the dataset table.
    
    This function is a placeholder for lookup logic.
    """
    # In practice, you'd query the dataset table
    raise NotImplementedError(
        "Dataset components must be looked up from the dataset table, "
        "not computed from UUID"
    )
