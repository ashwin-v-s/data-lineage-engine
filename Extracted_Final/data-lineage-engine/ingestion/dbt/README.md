# ingestion/dbt (M1): dbt Manifest Adapter

**Status:** NOT IMPLEMENTED (MVP-2)  
**Owner:** M1  
**Blocked by:** SQL extraction validation (tasks in `ingestion/sql/`)

dbt manifest adapter (implementation deferred to MVP-2). Will parse `manifest.json` and produce `StaticEvidence` for declared dbt models.

## Scope

Currently deferred. Intended to extract:
- Model dependencies from `manifest.json`
- Column-level lineage from dbt metadata (if available)
- Declared (not inferred) relationships

## Why Deferred

Pack Section 30 guidance: "Start after SQL extraction works". M1's MVP-1 deliverable is the SQL adapter and corpus/tests. The dbt adapter is scheduled for MVP-2 after:

1. SQL extraction (ingestion/sql/) is complete and tested
2. Ground truth spike (M2) provides direction on column-level evidence requirements
3. Storage schema (M3) is finalized

## Planned Implementation

```python
from contracts.interfaces import StaticLineageProvider, SchemaSnapshot, StaticExtraction
from pathlib import Path
import json

class DBTManifestProvider:
    """Parses dbt manifest.json and extracts declared model relationships."""
    
    def extract(
        self, 
        manifest_path: Path,
        run_artifacts_dir: Path
    ) -> StaticExtraction:
        """Extract static lineage from dbt manifest.
        
        Args:
            manifest_path: Path to manifest.json from dbt run
            run_artifacts_dir: Directory containing run_results.json, etc.
        
        Returns:
            StaticExtraction with declared dependencies as StaticEvidence
        """
        # To be implemented in MVP-2
        pass
```

## Dependencies (when implemented)

- `dbt-core >= 1.5`: To parse manifest schema
- `pyyaml`: For manifest parsing

## Integration

- **M3**: Will store dbt evidence with source_system="dbt_manifest"
- **M4**: Will treat dbt evidence as static candidates alongside SQL evidence
- **B1**: B1 adapter will include dbt evidence in static-only baseline

## MVP-2 Checklist

- [ ] Load and parse manifest.json
- [ ] Extract model definitions and dependencies
- [ ] Map to StaticEvidence with proper IDs
- [ ] Tests for real dbt projects
- [ ] Documentation of supported manifest versions
- [ ] Handle edge cases (cyclic deps, macro expansion, etc.)

## References

- Pack Section 30: M1 deliverables and schedule
- Pack Section 31: M2 provides runtime evidence requirements
- dbt manifest schema: https://docs.getdbt.com/reference/artifacts/manifest-json

