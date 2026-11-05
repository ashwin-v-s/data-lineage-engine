# Metadata graph JSON adapter (M1)

`parse_metadata_graph()` is a pure parser/validator for the versioned
`kairos.ingest.v1` metadata-graph file format. It returns normalized JSON plus
diagnostics; it never connects to Supabase or writes data. See
[`../../docs/KAIROS_FINAL_ARCHITECTURE.md`](../../docs/KAIROS_FINAL_ARCHITECTURE.md)
for the cross-source contract and
[`../../tests/fixtures/ingestion/metadata_graph/`](../../tests/fixtures/ingestion/metadata_graph/)
for valid, invalid, unsupported-version, and expected-output examples.

```python
from pathlib import Path
from ingestion.metadata_graph import parse_metadata_graph

result = parse_metadata_graph(
    Path("metadata.json").read_bytes(),
    filename="metadata.json",
    source_revision="git:commit-sha-or-upload-id",
)
if not result.ok:
    for diagnostic in result.diagnostics:
        print(diagnostic.code, diagnostic.path, diagnostic.message)
else:
    # Pass this normalized envelope to the M3 preview/commit orchestrator.
    normalized = result.payload
```

The adapter requires `contract_version: "kairos.ingest.v1"`, an `assets`
array, unique asset IDs and qualified names, and relationships whose endpoints
are present in the same batch. It caps input at 2 MiB, 1,000 assets, and 5,000
relationships. Invalid batches return no payload. Secret-like metadata keys
are removed recursively and reported as warnings. Output arrays are sorted for
stable comparison. Declared edges are labeled `DECLARED_METADATA`; they do not
claim runtime execution.

The old CLI wrapper `{ "kind": "metadata_graph", "payload": {...} }` is
accepted for compatibility, but the graph itself must still declare v1.
