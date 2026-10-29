# Static file ingestion adapters

`parse_static_file(kind, source, ...)` is the explicit adapter registry for
file-based metadata. Each adapter is a pure extract/normalize/validate step:
it returns a `kairos.ingest.v1` envelope plus diagnostics and provenance, and
does not call a service, write to a database, or execute imported content.

```python
from pathlib import Path
from ingestion.static_files import parse_static_file

result = parse_static_file(
    "dbt_manifest", Path("target/manifest.json").read_bytes(),
    filename="manifest.json", source_revision="git:abc123",
)
if not result.ok:
    for diagnostic in result.diagnostics:
        print(diagnostic.code, diagnostic.path, diagnostic.message)
else:
    envelope = result.payload  # send to the authenticated M3 preview endpoint
```

Supported kinds:

| Kind | Input | Semantics |
|---|---|---|
| `metadata_graph` | Kairos `kairos.ingest.v1` JSON | Explicit assets and relationships; declarations are not runtime observations. |
| `dbt_manifest` | dbt `manifest.json` | Models, seeds, snapshots, sources, exposures, and declared `depends_on.nodes`; unsupported resources are reported. |
| `file_inventory` | JSON object with a `files` array | File assets with inventory metadata; it does not infer data-flow lineage. |
| `csv_headers` | UTF-8 CSV bytes/text | One table asset from the header row only; column types stay unknown and data rows are ignored. |

The registry intentionally requires an explicit `kind`, following the
source-specific recipe pattern used by catalog ingestion systems. DataHub and
OpenMetadata are not installed as runtime dependencies: their full pipelines
bring separate metadata services and storage. Kairos adopts their typed
adapter-to-central-API boundary while keeping authenticated persistence in the
existing FastAPI/Supabase layer owned by M3.
