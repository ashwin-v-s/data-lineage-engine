# ADR-001: Source-neutral metadata preview and capability-driven inspection

- **Status:** Proposed for team review
- **Date:** 2026-10-27
- **Context:** Metadata sources may describe datasets, files, images, documents, jobs, or other resources. Hardcoding one domain's fields makes the workspace brittle. Competitor research on DataHub, OpenMetadata, OpenLineage/Marquez, and Open Data Hub suggests separating stable identity from extensible metadata and using asset/source capabilities to determine which features apply.
- **Decision for this increment:** Add a side-effect-free JSON preview endpoint that normalizes arbitrary JSON records, preserves safe unknown fields, reports discovered fields and basic capabilities, and passes through explicit relationships only. The endpoint is not a live connector and does not persist records.
- **Security:** Obvious secret-like field names are excluded recursively from the preview. This is a defensive filter, not a substitute for source-side credential isolation or a full sensitive-data policy.
- **Research invariants preserved:** Do not infer relationships from names or absent events; do not mix ground truth into predictor inputs; do not describe mock fixtures as experimental results; do not claim a generic JSON preview is a universal connector.
- **Consequences:** This provides a reusable normalization seam for future connectors and tests, but source authentication, connector discovery, persistence, temporal storage, source freshness, and full capability negotiation remain future work. Changing the locked MVP source scope requires an explicit team decision.
- **Acceptance:** tests cover arbitrary image-like and unknown records, explicit-only relationships, secret-like field filtering, duplicate IDs, and a record-count limit.
