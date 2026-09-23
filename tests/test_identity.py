"""
Tests for canonical identity generation (M3).
"""
import uuid

import pytest

from backend.app.identity.canonical_ids import (
    column_id,
    dataset_id,
    edge_id,
    fingerprint_schema,
    fingerprint_sql,
    is_valid_uuid,
    job_id,
    normalize_identifier,
)


class TestNormalization:
    """Test identifier normalization."""
    
    def test_lowercase_conversion(self):
        assert normalize_identifier("USERS") == "users"
        assert normalize_identifier("MyTable") == "mytable"
    
    def test_whitespace_stripping(self):
        assert normalize_identifier("  users  ") == "users"
        assert normalize_identifier("\tusers\n") == "users"
    
    def test_quoted_identifiers(self):
        assert normalize_identifier('"Quoted Table"') == "quoted table"
        assert normalize_identifier('"MixedCase"') == "mixedcase"
    
    def test_no_change_needed(self):
        assert normalize_identifier("users") == "users"


class TestDatasetID:
    """Test dataset ID generation."""
    
    def test_deterministic(self):
        """Same inputs always produce same UUID."""
        id1 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        id2 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        assert id1 == id2
    
    def test_different_inputs_different_ids(self):
        """Different inputs produce different UUIDs."""
        id1 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        id2 = dataset_id("dbt", "prod", "analytics", "public", "orders", "table")
        assert id1 != id2
    
    def test_case_insensitive(self):
        """Case differences don't affect ID."""
        id1 = dataset_id("dbt", "PROD", "analytics", "public", "USERS", "table")
        id2 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        assert id1 == id2
    
    def test_whitespace_ignored(self):
        """Whitespace differences don't affect ID."""
        id1 = dataset_id("dbt", " prod ", "analytics", "public", " users ", "table")
        id2 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        assert id1 == id2
    
    def test_quoted_identifiers(self):
        """Quoted identifiers are normalized."""
        id1 = dataset_id("dbt", "prod", "analytics", "public", '"Users"', "table")
        id2 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        assert id1 == id2
    
    def test_all_components_matter(self):
        """Changing any component changes the ID."""
        base = ("dbt", "prod", "analytics", "public", "users", "table")
        base_id = dataset_id(*base)
        
        # Change each component
        assert dataset_id("sqlglot", "prod", "analytics", "public", "users", "table") != base_id
        assert dataset_id("dbt", "dev", "analytics", "public", "users", "table") != base_id
        assert dataset_id("dbt", "prod", "warehouse", "public", "users", "table") != base_id
        assert dataset_id("dbt", "prod", "analytics", "staging", "users", "table") != base_id
        assert dataset_id("dbt", "prod", "analytics", "public", "customers", "table") != base_id
        assert dataset_id("dbt", "prod", "analytics", "public", "users", "view") != base_id
    
    def test_returns_valid_uuid(self):
        """Generated ID is a valid UUID."""
        id1 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        assert isinstance(id1, uuid.UUID)
        assert is_valid_uuid(str(id1))


class TestColumnID:
    """Test column ID generation."""
    
    def test_deterministic(self):
        """Same inputs produce same UUID."""
        ds_id = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        col1 = column_id(ds_id, "email", "v1")
        col2 = column_id(ds_id, "email", "v1")
        assert col1 == col2
    
    def test_different_columns(self):
        """Different column names produce different UUIDs."""
        ds_id = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        col1 = column_id(ds_id, "email")
        col2 = column_id(ds_id, "name")
        assert col1 != col2
    
    def test_different_datasets(self):
        """Same column name in different datasets produces different UUIDs."""
        ds1 = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        ds2 = dataset_id("dbt", "prod", "analytics", "public", "orders", "table")
        col1 = column_id(ds1, "id")
        col2 = column_id(ds2, "id")
        assert col1 != col2
    
    def test_schema_version_matters(self):
        """Different schema versions produce different UUIDs."""
        ds_id = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        col1 = column_id(ds_id, "email", "v1")
        col2 = column_id(ds_id, "email", "v2")
        assert col1 != col2
    
    def test_case_insensitive(self):
        """Column names are case-insensitive."""
        ds_id = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        col1 = column_id(ds_id, "EMAIL")
        col2 = column_id(ds_id, "email")
        assert col1 == col2


class TestJobID:
    """Test job ID generation."""
    
    def test_deterministic(self):
        """Same inputs produce same UUID."""
        id1 = job_id("airflow_prod", "daily_etl")
        id2 = job_id("airflow_prod", "daily_etl")
        assert id1 == id2
    
    def test_different_jobs(self):
        """Different jobs produce different UUIDs."""
        id1 = job_id("airflow_prod", "daily_etl")
        id2 = job_id("airflow_prod", "hourly_sync")
        assert id1 != id2
    
    def test_different_namespaces(self):
        """Different namespaces produce different UUIDs."""
        id1 = job_id("airflow_prod", "daily_etl")
        id2 = job_id("airflow_dev", "daily_etl")
        assert id1 != id2


class TestEdgeID:
    """Test edge ID generation."""
    
    def test_deterministic(self):
        """Same inputs produce same UUID."""
        src = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        tgt = dataset_id("dbt", "prod", "analytics", "public", "orders", "table")
        id1 = edge_id(src, tgt, "DATASET")
        id2 = edge_id(src, tgt, "DATASET")
        assert id1 == id2
    
    def test_direction_matters(self):
        """Source and target order matters."""
        src = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        tgt = dataset_id("dbt", "prod", "analytics", "public", "orders", "table")
        id1 = edge_id(src, tgt, "DATASET")
        id2 = edge_id(tgt, src, "DATASET")
        assert id1 != id2
    
    def test_granularity_matters(self):
        """Different granularities produce different UUIDs."""
        src = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        tgt = dataset_id("dbt", "prod", "analytics", "public", "orders", "table")
        id1 = edge_id(src, tgt, "DATASET")
        id2 = edge_id(src, tgt, "COLUMN")
        assert id1 != id2
    
    def test_with_fingerprints(self):
        """Optional fingerprints affect ID."""
        src = dataset_id("dbt", "prod", "analytics", "public", "users", "table")
        tgt = dataset_id("dbt", "prod", "analytics", "public", "orders", "table")
        id1 = edge_id(src, tgt, "COLUMN", operator_fingerprint="abc123")
        id2 = edge_id(src, tgt, "COLUMN", operator_fingerprint="def456")
        id3 = edge_id(src, tgt, "COLUMN")
        
        assert id1 != id2
        assert id1 != id3
        assert id2 != id3


class TestFingerprints:
    """Test SQL and schema fingerprinting."""
    
    def test_sql_fingerprint_deterministic(self):
        """Same SQL produces same fingerprint."""
        fp1 = fingerprint_sql("SELECT * FROM users")
        fp2 = fingerprint_sql("SELECT * FROM users")
        assert fp1 == fp2
    
    def test_sql_fingerprint_whitespace_normalized(self):
        """Whitespace differences don't affect fingerprint."""
        fp1 = fingerprint_sql("SELECT * FROM users")
        fp2 = fingerprint_sql("SELECT  *  FROM  users")
        fp3 = fingerprint_sql("SELECT\n*\nFROM\nusers")
        assert fp1 == fp2 == fp3
    
    def test_sql_fingerprint_different_queries(self):
        """Different queries produce different fingerprints."""
        fp1 = fingerprint_sql("SELECT * FROM users")
        fp2 = fingerprint_sql("SELECT * FROM orders")
        assert fp1 != fp2
    
    def test_sql_fingerprint_length(self):
        """Fingerprint is 16 characters."""
        fp = fingerprint_sql("SELECT * FROM users")
        assert len(fp) == 16
    
    def test_schema_fingerprint_deterministic(self):
        """Same schema produces same fingerprint."""
        schema = {"users": {"id": "int", "email": "text"}}
        fp1 = fingerprint_schema(schema)
        fp2 = fingerprint_schema(schema)
        assert fp1 == fp2
    
    def test_schema_fingerprint_key_order_irrelevant(self):
        """Key order doesn't affect fingerprint (sorted internally)."""
        schema1 = {"users": {"email": "text", "id": "int"}}
        schema2 = {"users": {"id": "int", "email": "text"}}
        fp1 = fingerprint_schema(schema1)
        fp2 = fingerprint_schema(schema2)
        assert fp1 == fp2
    
    def test_schema_fingerprint_different_schemas(self):
        """Different schemas produce different fingerprints."""
        schema1 = {"users": {"id": "int", "email": "text"}}
        schema2 = {"users": {"id": "int", "name": "text"}}
        fp1 = fingerprint_schema(schema1)
        fp2 = fingerprint_schema(schema2)
        assert fp1 != fp2


class TestUUIDValidation:
    """Test UUID validation helper."""
    
    def test_valid_uuid(self):
        """Valid UUID strings are recognized."""
        assert is_valid_uuid("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        assert is_valid_uuid(str(uuid.uuid4()))
    
    def test_invalid_uuid(self):
        """Invalid strings are rejected."""
        assert not is_valid_uuid("not-a-uuid")
        assert not is_valid_uuid("12345")
        assert not is_valid_uuid("")
