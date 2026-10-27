# Competitor Architecture Notes: Universal Metadata and Asset-Adaptive Workspaces

**Status:** Research notes / design input, not an implementation claim.  
**Prepared:** 2026-10-27  
**Scope:** How established metadata platforms separate source ingestion, common identity, extensible metadata, relationships, and asset-specific UI.

## Executive summary

Kairos should not equate a metadata catalog with a list of database tables. A useful universal workspace needs a small common asset identity, a place to preserve source-specific fields, explicit relationships, and a capability model that lets the UI expose only supported views and actions.

This document records architecture patterns from official product documentation. It is not a claim that Kairos already has all the connectors those products provide.

## Primary-source comparison

### DataHub

DataHub describes metadata through entities and aspects, with ingestion mechanisms that bring metadata into the platform. This supports separating a stable entity identity from independently extensible metadata components rather than encoding every possible source field into one rigid schema.

- Metadata model: https://docs.datahub.com/docs/metadata-modeling/metadata-model
- Metadata ingestion architecture: https://docs.datahub.com/docs/architecture/metadata-ingestion

**Kairos implication:** retain a stable asset identity and common fields, but preserve unfamiliar connector fields in source metadata. Connector-specific facets should not require a new database table or a new frontend page for every source type.

### OpenMetadata

OpenMetadata documents asset-specific detail pages and tabs. The information available depends on the asset and its type; table-oriented capabilities should not be assumed for every entity.

- Data asset tabs: https://docs.open-metadata.org/v1.12.x/how-to-guides/guide-for-data-users/data-asset-tabs
- Data discovery / preview: https://docs.open-metadata.org/how-to-guides/data-discovery/preview

**Kairos implication:** use one consistent asset-inspection shell, then conditionally expose schema, lineage, quality, execution, governance, or media/file details only when the selected asset and source support them.

### OpenLineage and Marquez

OpenLineage standardizes run/job/dataset event concepts and supports extensible facets for additional metadata. A relationship or event supplied by a source can be recorded with provenance; the absence of an event should not be transformed into proof that an event did not happen.

- OpenLineage specification: https://openlineage.io/docs/spec/facets/
- Marquez project: https://marquezproject.ai/

**Kairos implication:** keep observed evidence separate from derived reasoning. Preserve explicit source relationships and provenance. Never infer execution lineage from similar names alone.

### Open Data Hub

Open Data Hub documents dataset discovery and data-access APIs as part of its data ecosystem.

- Documentation: https://docs.opendatahub.com/

**Kairos implication:** discovery and retrieval should be separate from UI rendering. The UI should consume normalized catalog records and capability information, not hardcode assumptions about one source's API response.

### OpenMeter clarification

OpenMeter focuses on usage metering and billing, not metadata cataloging. It can be a useful comparison for metering/usage-related product ideas, but it is not a like-for-like competitor for asset discovery and lineage.

- Documentation: https://openmeter.io/docs/get-started/overview

## Recommended Kairos design principles

1. **Connector contract:** each adapter declares what it can discover, which metadata it supplies, which relationships it can establish, and which operations it supports.
2. **Stable common identity:** use a stable asset identifier and common fields such as source, qualified name, type, and discovery/update timestamps when available.
3. **Extensible source metadata:** preserve unknown fields instead of dropping them because the current UI has no dedicated field.
4. **Explicit relationships:** accept relationships supplied by a source or produced by a supported analyzer. Do not invent lineage from names, folder proximity, or matching field names.
5. **Capability-driven UI:** render a feature only when the source, asset, and available records support it. Missing capabilities should be unavailable or absent, not populated with fabricated examples.
6. **Honest empty states:** a connected source with zero discovered assets should show connection/discovery status and an import/retry path, not demo assets.
7. **Source and demo separation:** synthetic fixtures must be visibly labelled and never mixed into a user's connected catalog without explicit opt-in.
8. **Safe metadata display:** do not return obvious credentials, tokens, or secret-bearing fields in previews or UI payloads.

## Scope reconciliation with the Kairos research pack

The current research pack's MVP explicitly scopes ingestion around SQL text / SQLGlot, OpenLineage runtime events, and dbt manifest metadata. The research pack also locks the research-engine invariants, including the separation of ground truth from predictor input, PostgreSQL as the authority if storage is implemented, and missing runtime evidence never implying a negative result.

This competitor research does **not** silently change those locked decisions. A generic JSON metadata preview is an additive backend utility for testing the broader asset model; it does not claim to be a live connector, persistent catalog, universal lineage parser, or validated research result. Expanding MVP source scope should be an explicit team decision.

## Current implementation boundary

The generic metadata preview endpoint added alongside this note:
- accepts JSON objects, arrays, or common object properties containing arrays of records;
- normalizes them into generic asset records for inspection;
- preserves safe source fields as metadata;
- reports discovered fields and a small capability summary;
- passes through explicitly supplied top-level relationships only;
- does not persist data, connect to external systems, infer lineage, or claim that source metadata is current.

## Acceptance checks for future connectors

- [ ] A source with only images/files can be discovered without SQL-specific fields being fabricated.
- [ ] A source with unfamiliar top-level fields preserves those fields after normalization and round-trip serialization.
- [ ] A source with no relationships shows no lineage claim.
- [ ] A source with explicit relationships preserves relationship type and provenance.
- [ ] A source with no runs/evidence/quality data does not display fabricated run/evidence/quality results.
- [ ] Connector capabilities can be tested independently of the frontend.
- [ ] Source metadata previews omit obvious credential-like keys.
- [ ] Synthetic data is clearly labelled and isolated from connected-source records.
- [ ] Database-specific analysis is enabled only for sources/assets with relevant metadata and adapter support.
