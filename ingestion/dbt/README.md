# ingestion/dbt (M1)

**Status: pure Python adapter implemented.** `parse_dbt_manifest()` reads a
local artifact and returns a normalized `kairos.ingest.v1` envelope. It does
not connect to dbt, a database, or Supabase, and does not persist anything.

The adapter supports models, seeds, snapshots, sources, and exposures. It
normalizes `depends_on.nodes` into `declared_dependency` relationships and
preserves dbt schema version, artifact hash, filename, and optional revision.
Unsupported resource types and unresolved dependencies are reported as
warnings. dbt manifest dependencies are declarations, not evidence that a
model ran. Use `ingestion.static_files.parse_static_file("dbt_manifest", ...)`
when consuming multiple supported file kinds through one registry. See
[`../../docs/workstreams/M1_STATIC_AND_FILE_ADAPTERS.md`](../../docs/workstreams/M1_STATIC_AND_FILE_ADAPTERS.md)
and [`../ADAPTER_STATUS.md`](../ADAPTER_STATUS.md).
