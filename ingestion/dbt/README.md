# ingestion/dbt (M1)

**Status: NOT IMPLEMENTED in the Python ingestion package.** The only dbt
handling currently in the repository is browser-side preview/summary in
`frontend/ingestion.js`; that preview does not normalize or persist assets.

The next adapter should parse a versioned dbt `manifest.json` into declared
asset/dependency metadata through the shared ingestion contract. dbt manifest
dependencies are declarations, not evidence that a model ran. Preserve
unsupported resource types and malformed references as diagnostics; do not
connect to Supabase from this package. See
[`../../docs/workstreams/M1_STATIC_AND_FILE_ADAPTERS.md`](../../docs/workstreams/M1_STATIC_AND_FILE_ADAPTERS.md)
and [`../ADAPTER_STATUS.md`](../ADAPTER_STATUS.md).
