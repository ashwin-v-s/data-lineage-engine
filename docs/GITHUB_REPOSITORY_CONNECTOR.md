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

---

# Implemented backend reference

Read-only reference for the pieces of the private connector that now exist in code.
Source of truth: `backend/app/services/github_app.py`,
`backend/app/services/token_crypto.py`,
`backend/app/api/routes/integrations.py`, `.env.example`, and
`docs/KAIROS_FINAL_ARCHITECTURE.md`.

Scope note: the backend client, its token encryption, and a configuration-status
endpoint are implemented and unit-tested. The install/callback routes and any UI
wiring are **not** implemented yet, so the connector cannot be enabled end to end.

## 1. What the connector is and its read-only guarantee

`GitHubAppClient` (`backend/app/services/github_app.py`) is a minimal GitHub App
client that browses repositories the app installation is authorized for. Credentials
come from the instance and the HTTP client is injectable, so no test needs network.

The read-only rule is enforced centrally in `GitHubAppClient._api_request`. Only
two request shapes are permitted:

- `GET` — all repository content reads.
- `POST` to a path ending `/access_tokens` — the sole non-GET call, used to mint
  an installation token (`POST /app/installations/{id}/access_tokens`).

Every other request is refused with `GitHubAppError` and the message
`read-only GitHub client refused {METHOD} {path}; repository content is GET-only`.
Refused operations therefore include `POST` to any non-token path, and all
`PATCH`, `PUT` and `DELETE` calls. `tests/test_github_app.py` asserts that
`PUT`/`PATCH`/`DELETE` on `/repos/o/r/contents/file` and `POST` on
`/repos/o/r/issues` all raise `GitHubAppError`.

Repository content is read through GET-only endpoints: `GET /installation/repositories`
(`list_repositories`), `GET /repos/{owner}/{repo}/git/trees/{ref}` (`get_tree`),
and `GET /repos/{owner}/{repo}/contents/{path}` (`get_file_content`).

`get_file_content` returns either a supported shape
`{"path","ref","sha","encoding":"utf-8","size","content"}` or an
`{"unsupported": True, "reason": ...}` marker. Content is never silently
truncated: non-file entries yield `not_a_file`; a `403` from the contents API
yields `github_refused_contents_request`; a `404` raises `GitHubAppApiError`; a
declared or decoded size above the limit yields `file_too_large`; non-base64
encoding yields `unsupported_encoding`; a base64 decode failure yields
`content_not_base64`; non-UTF-8 bytes yield `binary_content`. The size limit
defaults to `DEFAULT_MAX_FILE_BYTES = 1_000_000` bytes.

## 2. Required environment variables

All six `GITHUB_APP_*` variables are required together. `GITHUB_ENV_VARS`
lists them; `GitHubAppClient.missing_env_vars()` returns the names that are
absent or blank, and `is_configured()` is `True` only when none are missing.

| Variable | Secret? | Purpose |
|---|---|---|
| `GITHUB_APP_ID` | required (no per-line label) | GitHub App id (`iss` in the JWT) |
| `GITHUB_APP_PRIVATE_KEY` | SECRET | App private key; may be a one-line PEM with literal `\n` escapes |
| `GITHUB_APP_SLUG` | NOT A SECRET | Public app slug used in install URLs |
| `GITHUB_APP_CLIENT_ID` | NOT A SECRET | OAuth client id of the same app |
| `GITHUB_APP_CLIENT_SECRET` | SECRET | OAuth client secret of the same app |
| `GITHUB_APP_CALLBACK_URL` | NOT A SECRET | Callback URL registered on the GitHub App |
| `KAIROS_TOKEN_ENCRYPTION_KEY` | SECRET | AES-256 key for token-at-rest encryption and state signing |

Secret/not-secret labels match `.env.example`. Generate the encryption key with
the command recorded there:

```
python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

## 3. Token-at-rest encryption

`backend/app/services/token_crypto.py` encrypts installation tokens at rest with
AES-256-GCM. The stored value is a self-describing, versioned envelope:

```
b"KGC1" (4-byte magic) | 1-byte key version (currently 1) | 12-byte nonce | AES-256-GCM ciphertext
```

The key is read from `KAIROS_TOKEN_ENCRYPTION_KEY`, which must be urlsafe base64
decoding to exactly 32 bytes. The module fails closed: an unset/blank key, a
non-base64 key, or a wrong-length key all raise `TokenCryptoError`, and there is
no plaintext fallback. Decryption with the wrong key or a tampered ciphertext
fails the AES-GCM tag check and raises `TokenCryptoError`; a ciphertext written
under a different version is also rejected. A fresh random nonce is used per
encryption.

## 4. OAuth `state` signing

`sign_state(user_id, workspace_id)` produces a urlsafe, dot-separated string
`base64url(payload).base64url(signature)`. The payload is
`{"v":1,"u":user_id,"w":workspace_id,"iat":issued_at}` and the signature is
HMAC-SHA256 keyed by the same `KAIROS_TOKEN_ENCRYPTION_KEY`. `verify_state`
returns `{"user_id","workspace_id","issued_at"}` and raises `SignedStateError`
(a `ValueError` subclass) for a missing, malformed, tampered, or expired state.
The default lifetime is `STATE_TTL_SECONDS = 600` seconds; a state issued more
than 60 seconds in the future is also rejected.

## 5. Checking configuration at runtime

`GET /api/v1/integrations/github/status`
(`backend/app/api/routes/integrations.py`) requires an authenticated user
(`require_user`) and performs no network call and no writes. It returns:

| Field | Meaning |
|---|---|
| `configured` | `True` when no `GITHUB_APP_*` variable is missing |
| `missing_env` | List of missing/blank `GITHUB_APP_*` names |
| `token_encryption_configured` | `token_crypto.is_configured()` (valid key present) |
| `read_only` | Always `True` |
| `install_url` | `https://github.com/apps/{slug}/installations/new`, or `null` when no slug |

## 6. Running the unit tests

The connector has no network or database dependencies in tests:

```
python -m pytest tests/test_github_app.py tests/test_token_crypto.py -q
```

## 7. Operational note

`docs/KAIROS_FINAL_ARCHITECTURE.md` (Section 7, "GitHub access") records the
milestone decision: public read-only browse can support the visual demo, with
private access later via a GitHub App, to be reopened when private repo
connection/import is required. Enabling this connector is therefore an
operational decision outside the demo slice; the status endpoint only makes the
current configuration observable rather than silently absent.
