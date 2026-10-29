# GitHub repository browser and connector plan

## Intended user flow

1. The person signs in to Kairos and enters their own workspace.
2. They connect a GitHub source separately from using GitHub as their Kairos sign-in provider.
3. They choose the repository and branch Kairos may inspect.
4. Kairos lists repository files and lets the person preview supported metadata or source files.
5. A separate, explicit import action validates and persists selected metadata. Previewing a file must not write to the catalog.

The longer-term private repository integration should use a GitHub App configured with the minimum read-only repository permissions needed for metadata and file contents. The GitHub App installation should allow repository selection. Avoid requesting broad `repo` OAuth scope when fine-grained GitHub App permissions are available.

## Current implementation

The Integrations page includes a browser for **public repositories**. It lists files from a selected repository and branch, previews supported text formats, and downloads a selected file. It calls GitHub's public REST API directly from the browser and does not store credentials, repository contents, or catalog records.

Private repositories, saved source connections, automatic sync, dbt/SQL parsing of files from GitHub, and persistent catalog import are not implemented by this browser. GitHub sign-in to Kairos does not grant repository access. Do not label a public-file preview as a connected or imported catalog source.

## Security and implementation requirements for private repositories

- Register a GitHub App with user authorization and a callback URL for each deployment environment.
- Request repository metadata read and contents read only; do not request write access for this workflow.
- Bind OAuth state to the authenticated Kairos user and workspace, validate it on callback, and reject expired or reused state.
- Exchange authorization codes on the backend. Never expose the GitHub App secret or private key to browser code.
- Encrypt stored tokens with a deployment secret, scope each connection to its workspace, and never log or return tokens.
- Support disconnect/revocation and stop using credentials after revocation.
- Persist only source metadata and imported records that the user explicitly confirms; preserve repository, branch, commit SHA, file path, and import provenance.
- Make imports idempotent and report unsupported file formats and parser warnings rather than inventing lineage.

## Repository reference

The technical research report discusses GitHub repo/file metadata, branches, trees, SQL/dbt artifacts, read-only permissions, and commit/branch refresh cursors. It leaves the integration method as an open decision. For this product flow, a repository-scoped GitHub App is the preferred target; the current public browser is a demo-ready first slice.
