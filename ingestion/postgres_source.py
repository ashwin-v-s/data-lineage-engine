"""Read-only live PostgreSQL source connector for the Kairos ingestion contract.

This module is pure and database-injectable: the only I/O lives in the default
connector, which is a narrow seam that opens a read-only session, runs two
``information_schema`` queries, and always closes the connection. Tests inject
their own connector, so the module can be exercised with no database and no
network.

It never claims more than it observes: the produced envelope has no
relationships, and it is passed through
:func:`ingestion.metadata_graph.parse_metadata_graph` so contract validation,
secret stripping, and the honest ``NO_RELATIONSHIPS`` (and ``EMPTY_ASSET_BATCH``)
signals are all applied by the canonical parser rather than re-implemented here.
A password, connection string, or credential is never placed in the returned
payload, diagnostics, or provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import psycopg2
from psycopg2.extras import RealDictCursor

from ingestion.metadata_graph import (
    CONTRACT_VERSION,
    Diagnostic,
    MetadataGraphResult,
    parse_metadata_graph,
)

SOURCE_KIND = "postgresql"

# ``metadata_graph`` requires asset ids of at most 256 characters; the
# deterministic truncation keeps the id under that bound.
_MAX_ASSET_ID_LENGTH = 255

# Explicit, read-only metadata queries. No DDL, no writes.
_TABLES_SQL = (
    "SELECT table_schema, table_name FROM information_schema.tables "
    "WHERE table_type = 'BASE TABLE' AND table_schema = %s ORDER BY table_name"
)
_COLUMNS_SQL = (
    "SELECT table_schema, table_name, column_name, data_type, is_nullable, "
    "ordinal_position FROM information_schema.columns "
    "WHERE table_schema = %s ORDER BY table_name, ordinal_position"
)


@dataclass(frozen=True)
class PostgresSourceConfig:
    """Everything needed to reach one PostgreSQL source schema."""

    host: str
    port: int
    dbname: str
    user: str
    password: str
    schema: str = "public"

    @property
    def redacted_ref(self) -> str:
        """A safe source reference: host/port/database, never the password."""
        return f"{self.host}:{self.port}/{self.dbname}"


def _default_connector(
    config: PostgresSourceConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Open a read-only session, read the schema, and close the connection.

    The session is explicitly read-only and non-autocommit, so the two metadata
    queries cannot mutate the source even if a caller were to change the SQL.
    """
    conn = psycopg2.connect(
        host=config.host,
        port=config.port,
        dbname=config.dbname,
        user=config.user,
        password=config.password,
        connect_timeout=10,
    )
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_TABLES_SQL, (config.schema,))
            table_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(_COLUMNS_SQL, (config.schema,))
            column_rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
    return table_rows, column_rows


def _asset_id(schema: str, table: str) -> str:
    raw = f"{schema}.{table}"
    return raw if len(raw) <= _MAX_ASSET_ID_LENGTH else raw[:_MAX_ASSET_ID_LENGTH]


def extract_postgres_source(
    config: PostgresSourceConfig,
    *,
    connector: (
        Callable[
            [PostgresSourceConfig],
            tuple[list[dict[str, Any]], list[dict[str, Any]]],
        ]
        | None
    ) = None,
) -> MetadataGraphResult:
    """Read a source schema and return the validated ``kairos.ingest.v1`` result.

    ``connector`` is an injection seam for tests; when it is ``None`` the
    module-level :func:`_default_connector` is used. The returned result is the
    one produced by :func:`parse_metadata_graph`, unchanged.
    """
    read = connector or _default_connector
    try:
        table_rows, column_rows = read(config)
    except Exception as exc:  # the source is untrusted; report only the exception class
        return MetadataGraphResult(
            None,
            (
                Diagnostic(
                    "SOURCE_UNREACHABLE",
                    f"Could not read source schema: {type(exc).__name__}",
                ),
            ),
        )

    columns_by_table: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in column_rows:
        key = (str(row.get("table_schema")), str(row.get("table_name")))
        columns_by_table.setdefault(key, []).append(
            {
                "name": row.get("column_name"),
                "data_type": row.get("data_type"),
                "is_nullable": row.get("is_nullable") == "YES",
                "ordinal_position": int(row["ordinal_position"]),
            }
        )

    assets: list[dict[str, Any]] = []
    for row in table_rows:
        schema = str(row.get("table_schema"))
        table = str(row.get("table_name"))
        assets.append(
            {
                "id": _asset_id(schema, table),
                "qualified_name": f"{schema}/{table}",
                "name": table,
                "namespace": schema,
                "type": "TABLE",
                "metadata": {"columns": columns_by_table.get((schema, table), [])},
            }
        )

    envelope: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "source": {"kind": "database", "ref": config.redacted_ref},
        "assets": assets,
        "relationships": [],
        "runs": [],
        "evidence": [],
        "diagnostics": [],
    }
    return parse_metadata_graph(
        envelope,
        filename=f"{config.dbname}.postgres.json",
        source_revision=config.redacted_ref,
    )
