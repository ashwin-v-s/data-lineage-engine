# Trust Center: certification, discussion, usage and quality

**Status:** implemented and applied 2026-11-26. Migration
`0019_trust_collaboration.sql` is applied to the shared Supabase project and was
verified with `verify_applied.py` and `verify_rls.py`. The API was exercised
against that database (see §6). This build is **not deployed**, so the hosted
site does not serve the Trust Center yet.

---

## 1. Why these four surfaces

The competitive analysis (`docs/COMPETITOR_ANALYSIS_2026-11.md`) found that
certification, asset discussion, popularity and a quality scorecard are present
in nearly every established catalog and observability platform, while Kairos
had none of them. They are implemented together because they answer one
question: *should I trust this asset, and who says so?*

## 2. Semantic rules

### Certification

- A row in `asset_certification` is the endorsement. There is no separate
  boolean that can drift out of sync.
- State is computed at read time:
  - `CERTIFIED` — no expiry, or expiry more than 30 days away;
  - `EXPIRING` — expiry within 30 days;
  - `EXPIRED` — expiry at or before now.
- Certifying again replaces the note, certifier and expiry. Revoking deletes the
  row; a second revoke is `404`, not a silent success.
- Certification is metadata trust. It never grants access to source data.
- Only owner, admin or editor may certify or revoke. Viewers receive `403`.

### Discussion

- `asset_discussion` is threaded: a root row has `parent_id = NULL`; replies
  point at the root.
- Only a root can be resolved. Resolving records the time and the member.
- A reply cannot be resolved on its own (`422`), and an already resolved thread
  returns `409`.
- Any signed-in member may comment. Machine API keys cannot (`403`), because a
  comment is attributed to a person.

### Usage and popularity

- `asset_engagement` counts recorded asset opens per workspace. It stores no
  user id.
- Per-user history stays in `asset_view`, which remains private to that user.
  The Trust Center never exposes who opened an asset.
- The counter is optional storage: if migration 0019 is absent, recording a view
  still succeeds and simply does not update popularity.
- The ranking is labelled "recorded opens", not query frequency. It is not a
  warehouse usage metric.

### Quality scorecard

- The snapshot uses the **latest** result per enabled assertion.
- Pass rate counts `PASS` and `FAIL` only. `SKIPPED` and `ERROR` are reported
  separately, and an unevaluated assertion is never scored.
- With no PASS/FAIL result the pass rate is `null` and the UI renders `—`, not
  `0%`.
- The trend is a daily series over the requested window (default 30 days).
- `uncovered_assets` counts assets with no enabled assertion.

### PII inheritance

`POST /api/v1/governance/classifications/propagate` walks **stored column
lineage** downstream and proposes `PII_INHERITED` / `POSSIBLE` rows.

- Seeds: `PII_SOURCE` or already `PII_INHERITED` columns.
- Never seeds: `PII_MASKED`, `PII_CLEARED`, `PII_POTENTIAL`, `UNKNOWN`.
- A target column that already has **any** classification is skipped, and
  traversal does not continue through it. A steward decision always wins.
- Every created row records the exact `lineage_edge_ids` that justify it plus a
  human note naming the source column. An edge without an id cannot justify a
  row, so it is ignored.
- Proposals are bounded by `depth` (1–5, default 3) and cycles are visited once.
- `dry_run: true` returns the proposal list without writing.

## 3. API surface

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/trust/overview` | member | certification, ownership, discussion, trending and quality snapshot |
| GET | `/api/v1/trust/certifications?state=all\|certified\|expiring\|expired` | member | certification register |
| PUT | `/api/v1/trust/assets/{asset_id}/certification` | owner/admin/editor | certify or re-certify |
| DELETE | `/api/v1/trust/assets/{asset_id}/certification` | owner/admin/editor | revoke |
| GET | `/api/v1/trust/assets/{asset_id}/discussion` | member | threads and replies |
| POST | `/api/v1/trust/assets/{asset_id}/discussion` | member | open a thread or reply |
| POST | `/api/v1/trust/discussion/{comment_id}/resolve` | owner/admin/editor | resolve a root |
| GET | `/api/v1/quality/scorecard?days=30` | member | quality snapshot and trend |
| POST | `/api/v1/governance/classifications/propagate` | owner/admin/editor | derive inherited PII |

`asset_id` accepts a dataset UUID or a dataset name, resolved inside the current
workspace. Every route is workspace-scoped by `get_conn()` and RLS; no client
supplied workspace id is accepted.

## 4. Database

Migration `backend/migrations/0019_trust_collaboration.sql` adds:

- `asset_certification` — unique per `(workspace_id, dataset_id)`;
- `asset_discussion` — threaded, with a check that a reply cannot be resolved
  and that resolution always names both time and person;
- `asset_engagement` — `(workspace_id, dataset_id)` counter.

All three enable and force RLS with the standard `kairos_workspace_isolation`
policy, revoke the PostgREST roles, and grant only `kairos_app`.

### Apply

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0019_trust_collaboration.sql
python scripts/db/verify_applied.py
python scripts/db/verify_rls.py --table asset_certification asset_discussion asset_engagement
python scripts/db/check_migrations.py
```

Do not edit the migration after it has been applied to any environment; correct
forward with `0020_*.sql`.

## 5. UI

- New nav entry **Trust & governance → Trust center** (`?view=trust`).
- `frontend/src/components/TrustView.jsx` renders three tabs: Overview,
  Certifications, Discussions.
- The PII screen gains **Propagate from lineage**, which calls the derivation
  endpoint and reports how many classifications were created.
- The view shows an explicit empty/error state when the migration is absent. It
  never substitutes sample certifications or comments.

## 6. Verification

- `python -m pytest -q tests/test_trust_api.py tests/test_pii_propagation.py`
- `python -m pytest -q` (full suite)
- `python -m ruff check` on changed files
- `python scripts/export_openapi.py && python scripts/check_openapi_drift.py --write`
- `python scripts/check_ui_claims.py`
- `python scripts/db/check_migrations.py`
- `cd frontend && npm run build`

### Live database smoke (2026-11-26)

Run through `TestClient` against the shared Supabase project, workspace
`d91f7d80-dc3e-401e-9df4-e7670e4d3ba1`, with a temporary certification and
thread that were deleted afterwards:

| Call | Result |
| --- | --- |
| `GET /trust/overview` | 200 |
| `PUT /trust/assets/{id}/certification` | 200 |
| `GET /trust/certifications` | 200 |
| `POST /trust/assets/{id}/discussion` | 201 |
| `GET /trust/assets/{id}/discussion` | 200 |
| `POST /trust/discussion/{id}/resolve` | 200 |
| `GET /quality/scorecard` | 200 |
| `POST /governance/classifications/propagate` (dry run) | 200 |
| `POST /governance/classifications/propagate` (write) | 200, 1 created, second run 0 (idempotent) |
| `DELETE /trust/assets/{id}/certification` | 200 |
| `POST /me/recently-viewed/{id}` | 200; engagement `None → 1`, then restored |

A real column pair was used for propagation (`country_code → country_code`),
which produced `PII_INHERITED` / `POSSIBLE` with the exact lineage edge id.
Both the temporary seed and the inherited row were removed afterwards, and the
workspace's usage counter was restored.

What these do **not** prove: that the deployed site renders the new view. That
requires an explicit deploy and a browser check.
