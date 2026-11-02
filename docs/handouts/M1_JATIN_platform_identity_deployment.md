# Handout M1 — Jatin (`Jat-in32006`) · Identity, Workspace & Platform

**Stream:** M1 — Platform: signup, workspace membership, RBAC/RLS, deployment, contract ownership.
**Mission:** make *"a stranger can sign up, is isolated to their workspace, and reaches a deployed Kairos on a real URL"* true and provable.
**Read first:** [KAIROS_ARCHITECTURE_V2.md](../KAIROS_ARCHITECTURE_V2.md) §4 invariants, §5.8, §7 row M1, §11 D1/D6/D12 · [VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) §1–§4 (what I ran, with output) · [PROJECT_STATUS_2026-11-02.md](../PROJECT_STATUS_2026-11-02.md)

---

## 1. What you have already shipped (evidence)

- 58 commits / 8 of 12 PRs — you are the only member with merges after Oct 1.
- Supabase integration to the shared project: PRs #7, #8 (DB, CORS, lineage routes, seed) and `backend/app/db.py`, `auth.py` fail-closed bearer verification.
- The product-completion surface: PRs #10/#11 (personalization, downstream-impact, GitHub App connector service, AES-GCM token crypto, deploy smoke checks, browser smoke coverage, quality gates) and the contract drift fix.
- History repair: PR #12 rebase that preserved Gauree's M5 commit.
- Architecture docs + `scripts/check_deployment.py`, `scripts/db/*`, `vercel.json`, `.github/workflows/live-smoke.yml`.

## 2. What is **not** done — your gaps

| # | Gap | Proof |
|---|---|---|
| G1 | **The shared Supabase database is currently unreachable from the repo's `.env`.** `python scripts/test_connection.py` → `FATAL: password authentication failed for user "postgres"`. Every live test, every RLS check and every "applied" claim is unverifiable until this is fixed. Everyone else is blocked behind you here. | measured 2026-11-02 |
| G2 | **No workspace membership/role model is in git.** `0007_membership_roles.sql` (`workspace_member`, `workspace_invite`) is untracked; RBAC is still owner-only; roles (`viewer/steward/editor/connection_owner/admin`) and permission checks exist nowhere. | `git status` |
| G3 | **Signup has never worked end to end.** `SUPABASE_SETUP.md`: zero registered users; Google/GitHub/Microsoft providers disabled; email delivery + OAuth callbacks never tested with a real account. Gate 1 is 0% verified. | docs §"Shared project verification" |
| G4 | **No deployment.** `live-smoke` failed on 2026-10-30, -31 and 11-01 (3/3 nightly runs) because there is no base URL. `main` carries a permanently red check. | Actions runs #1–#3 |
| G5 | **Two unpushed commits** (the M4 integrity gate `12488f8` + merge `a0621f2`) and a ~4,000-line uncommitted tree — including `contracts/api/openapi.json` +2,598 lines. The architecture of record (`KAIROS_*`, `Perplexity/`) is untracked. | `git rev-list --left-right --count origin/main...HEAD` = `0 2` |
| G6 | **Review routing does not exist.** `.github/CODEOWNERS` still contains `@M1-handle … @M5-handle` placeholders (Pack §18 was never finished) — a direct cause of the other four members having ≤2 merged PRs. | file contents |
| G7 | **Unverified schema claims, and one that already flipped.** `backend/migrations/README.md` and the headers of `0004`–`0009` all assert **"Applied to the shared Supabase project"**. But the 2026-10-30 audit in `KAIROS_HANDOFF_5_MEMBERS.md` §1 measured `0005_personalization` and `0006_github_connections` as **absent** from the live DB — the same tables now marked "Applied", with no recorded evidence of the apply. Today the credentials fail, so nobody can confirm any of it. | README vs. handoff §1 vs. `scripts/test_connection.py` |
| G8 | `docs/TEAM_GUIDE.md` ownership/branch tables still describe the old M1–M5 split, contradicting Architecture v2 §7. | docs |

## 2b. Executed today — defects that are **yours**, with the command that proved them

Full evidence in [VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md). These are not "gaps in scope" — they are things that ran and produced the wrong answer.

| # | What I ran | What happened | Why it is yours |
|---|---|---|---|
| J1 | `python scripts/test_connection.py` | prints `❌ Connection failed: … password authentication failed` and **exits 0** | you wrote these probes; a green exit is what CI and humans trust |
| J2 | `python scripts/db/list_tables.py`, `check_schema.py` | raise `psycopg2.OperationalError` tracebacks and **exit 0** | same |
| J3 | `python scripts/db/verify_rls.py` | prints `ERROR: could not connect using DATABASE_URL` and **exit 0** | same |
| J4 | `python scripts/db/check_migrations.py` | prints **`RESULT: PASS`** — while the DB is unreachable. It never connects: it `ast`-parses migration text and compares it to `WORKSPACE_SCOPED_TABLES`, a hand-typed list in `verify_rls.py` ([check_migrations.py:341-394](file:///E:/EDI-Metadata_Lineage/scripts/db/check_migrations.py#L341-L394)) | **this is the machine that produced the false "Applied to the shared Supabase project" headers** (G7). CI runs it as a gate ([ci.yml:45](file:///E:/EDI-Metadata_Lineage/.github/workflows/ci.yml#L45)) |
| J5 | `KAIROS_LIVE_API_TESTS=1 python -m pytest -q` | identical to a plain run: 346 passed / 80 skipped. The real gate is `KAIROS_TEST_USER_TOKEN` ([test_live_api.py:57](file:///E:/EDI-Metadata_Lineage/tests/test_live_api.py#L57)) | the env var named in `PROJECT_STATUS` and CI docs does not exist in code → the 76 live tests are unrunnable by design |
| J6 | every route in the served OpenAPI, unauthenticated | **66 of 68 → 401**; only `/healthz` and `/api/v1/auth/config` return 200. No route crashed. | auth is correct (keep it) — but `require_user` also calls `provision_personal_workspace` ([auth.py:56](file:///E:/EDI-Metadata_Lineage/backend/app/auth.py#L56)), so with the DB down there is **no way at all** to exercise the product |
| J7 | browser navigation to `/ingestion.html` | the user is served **raw JSON**: `{"error":{"code":"UNAUTHENTICATED","message":"Sign in is required",…}}` | a 401 on a *navigation* request must redirect to sign-in, not print an API error body ([main.py:151](file:///E:/EDI-Metadata_Lineage/backend/app/main.py#L151)) |
| J8 | `docker --version`, `where psql` | **not found**; no `docker-compose*` | there is no local database substitute on this machine → decision **D12** in v2 §11 is yours to settle in Wave 0 |
| J9 | `pytest --cov=backend.app` | **TOTAL 40 %**; **64 of 70 endpoint handlers have zero body lines executed**; `backend/app/repositories/*` + `mock_repo.py` + `schemas.py` are **0 %** (515 statements never imported) | CI has no coverage floor and no "live tests must run" job, so 346 green tests have never meant "the API works" |
| J10 | `npx playwright test` on a fresh clone | **2 failed** — `chrome-headless-shell.exe` missing; after `npx playwright install chromium`, **2 passed** | setup is undocumented; and the suite only proves the shell boots (M5 owns its assertions) |
| J11 | frontend load path | `auth-stitch.html:6` loads Tailwind from `cdn.tailwindcss.com`; [auth.js:7-8](file:///E:/EDI-Metadata_Lineage/frontend/auth.js#L7-L8) injects `three` and `chart.js` from jsDelivr | your deploy owns offline-safe assets. No internet at the demo = no styling, no charts, no 3D view |
| J12 | read [run_ui.py](file:///E:/EDI-Metadata_Lineage/scripts/run_ui.py) (47 lines) + [main.py:159-162](file:///E:/EDI-Metadata_Lineage/backend/app/main.py#L159-L162), then compared `frontend/dist/index.html` to the source | `run_ui.py` does not serve a frontend — the "Integrated System" section works only because `main.py` mounts `frontend/dist` **when that directory exists**, and `dist/` is gitignored, so a fresh clone gets a 404 at `/` until someone runs `npm run build` | your deploy gate must (1) run the build, and (2) assert the served HTML's stylesheet URLs actually resolve, instead of asserting `/` returned 200. *(Note: I first believed the build was also unstyled because `dist/index.html` has none of the five `<link>` tags in `frontend/index.html:17-21` — that was **wrong**, I disproved it, and report §11c records how. Vite hoists those links into `dist/assets/index-*.css`: 224 of 228 `styles.neo.css` selectors are present.)* |
| J13 | audited the isolation mechanism myself (`db.py`, `auth.py`, `0003`) — report §4b | the design is **correct and fail-closed** (`SET LOCAL ROLE kairos_app` + `FORCE ROW LEVEL SECURITY` + a `DO $$ … EXECUTE` loop that scopes all 17 core tables), but no test has ever proven it, and my first naive grep of the DDL **wrongly** concluded the core tables were unscoped because that DDL is built at runtime | two consequences for you: (1) the two-workspace test must actually run — it is the only evidence this works; (2) `verify_applied.py` must assert the **dynamically created** policies exist in `pg_policies`, not that a literal `CREATE POLICY` appears in a file. Static checks cannot see them |
| J14 | `docs/REPRODUCIBILITY.md` §4 vs the served contract + `scripts/demo_m5.py` | 10 of the 12 routes that doc names do not exist, none of its 7 named tests exist in `tests/test_api_v1.py`, and the documented verification entry point `demo_m5.py` dies with `KeyError: 'data'` (exit 1) because it calls the removed `/api/v1/entities/...` surface | the route inventory in [test_api_v1.py:129-157](file:///E:/EDI-Metadata_Lineage/tests/test_api_v1.py#L129-L157) is the real one. As contract custodian, retire the stale matrix and fix or delete the script — a broken documented command is worse than an undocumented one |
| J15 | ran `vercel.json` + all four workflow files, and probed the shared DB while stubbed | **The delivery path applies no migrations** — vercel.json builds `frontend/dist` and rewrites `/api/*` to `backend/api/index.py` (a verified 4-line re-export of `backend.app.main:app`), but nothing ever applies `0004`-`0009`, and a Vercel function cannot run one inside a request (D12). CI also has no false-green guard, no coverage floor, no authenticated browser test. **New environmental blocker:** the shared Supabase pooler currently refuses ALL connections — `FATAL: (ECIRCUITBREAKER) too many authentication failures` after repeated `password authentication failed for user "postgres"` — so even correct credentials cannot connect until it resets | add a migration/delivery decision to the deploy plan, wait out the breaker, then run `test_connection.py` once successfully before anything else touches the DB | report §12, §10; D12 in v2 §11

## 3. What you need to do

**Wave 0 — unblock the team (do this before anything else)**

0. **Make the verification scripts tell the truth (J1–J4).** Every one of `test_connection.py`, `db/list_tables.py`, `db/check_schema.py`, `db/verify_rls.py` must **exit non-zero** when it cannot connect — today all four exit 0. Rename `check_migrations.py`'s output so it cannot be quoted as proof of application (e.g. `RESULT: STATIC CHECK PASS — no database was contacted`), and add a separate `db/verify_applied.py` that connects, lists tables, and exits 0 only if each migration's expected tables exist. Until `verify_applied.py` exists and is green, no migration header may say "Applied".
0b. **Settle D12 and record it in `DECISION_LOG.md`:** restore the shared project's credentials, or install a local PostgreSQL (Docker or the Windows installer) and run `0001–0009` against it as a clearly-labelled dev DB. Say which one, and never describe dev-DB results as shared-project verification.
0c. **Fix the live-test gate (J5):** make `KAIROS_LIVE_API_TESTS=1` actually mean something — either honour that name in the skip condition or correct every doc/CI reference to `KAIROS_TEST_USER_TOKEN` — and add a CI job that runs the live suite when a token secret is present, so "346 passed" stops being read as "verified".
0d. **401 on navigation → redirect (J7):** server-gated HTML routes must bounce an unauthenticated browser to the sign-in screen; keep the JSON error body for `/api/*` requests only.
0e. **Coverage floor + dead-code decision (J9):** either wire `backend/app/repositories/` and `mock_repo.py` into the app and test them, or delete them; then add `--cov-fail-under` at today's honest number (40 %) so it can only rise.
0f. **Vendor the CDN assets (J11)** and document `npx playwright install chromium` in `docs/TEAM_GUIDE.md` (J10).

1. Restore DB access: reset the Supabase role password or correct `DATABASE_URL` in `.env`; record which role the app uses (`kairos_app`) vs the migration role; confirm `scripts/test_connection.py` passes **and now exits 1 when it does not** and print the Postgres version. **Do not commit `.env`.**
2. Re-run and paste real output into a PR description: `python scripts/db/list_tables.py`, `python scripts/db/verify_rls.py`, `python scripts/db/check_migrations.py`.
3. Re-state the schema facts once they are measurable: rewrite the `Applied` claims in `backend/migrations/README.md` (0004–0009) and in the `0007`/`0008`/`0009` headers to exactly what `list_tables.py` shows today, and add an "evidence" line to each entry (command + date + output). Treat the `0005`/`0006` flip (absent on 10-30 → "Applied" now) as the thing to prove first, because `personalization.py` and `integrations.py` routes already depend on those tables.
4. Push the 2 unpushed commits; then split the working tree into **per-stream PRs** (M2 ingest+sources, M3 capabilities, M4 governance+frontend views, M1 migrations 0007 + docs) and ask each owner to review their own slice. Commit `docs/KAIROS_ARCHITECTURE_V2.md`, this folder, `PROJECT_STATUS_2026-11-02.md` and `docs/Perplexity/`.
5. Replace CODEOWNERS placeholders with the real handles (`Jat-in32006`, `AnaaMorr`, `ashwin-v-s`, `gaureehatkar`, `pranav-samal`) mapped to Architecture v2 §7 paths, and update `docs/TEAM_GUIDE.md` §ownership + branch names.
6. Fix the encoding crash in `scripts/test_connection.py:23` (the ❌ print aborts under `cp1252` and masks the real error) — ASCII status text, or reconfigure stdout.

**Wave 1 — identity and isolation**
7. Get `0007` applied + verified: `workspace_member`, `workspace_invite`, RLS forced, grants to `kairos_app`, backfill the personal-workspace owner as `admin`.
8. Routes: `GET /api/v1/workspaces/me`, `GET/POST /api/v1/workspaces/{id}/members`, invite accept/revoke. Derive every permission from `workspace_member` server-side — never from JWT `user_metadata` (Supabase warns it is client-editable).
9. `tests/test_workspace_membership.py` (new) + make the skipped live tests run: a two-workspace cross-tenant read/write test that must fail closed, executed with `KAIROS_LIVE_API_TESTS=1`.
10. Signup proof: register 2 real users (one verification email round-trip), sign in, capture screenshots; decide explicitly whether social OAuth is in scope for the demo and either enable one provider with a tested callback or write the sentence "email/password only" into the report.

**Wave 4 — deployment**
11. Create the Vercel project (frontend `dist` + `backend/api/index.py`), set `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `FRONTEND_ORIGIN`, `KAIROS_TOKEN_ENCRYPTION_KEY`; run `python scripts/check_deployment.py --base-url <url>`; make `live-smoke` green and add the base URL secret to Actions so the nightly stops failing (or disable the schedule until there is a host).
12. Register the architecture decision that **scheduled jobs cannot live in a Vercel request** (`maxDuration: 30`) and document where the freshness/sync runner actually runs (M2/M4 depend on your answer).
13. Keep the contract: commit the regenerated `contracts/api/openapi.json`, keep `check_openapi_drift.py` green, and act as custodian for any change to §5 contracts in Architecture v2.

## 4. Definition of done (your gate)

- A real Supabase user signs up → verifies email → signs in → sees only their workspace; unauthenticated requests return 401; a second workspace cannot read or write the first (proven by a **run** test, not a skipped one).
- `list_tables.py` output exists in a PR and matches the headers of `0001`–`0009`.
- A deployed URL serves the app and `live-smoke` is green on `main`.
- CODEOWNERS routes real reviewers; every stream's slice is merged, not sitting in one laptop's working tree.
- **New, from §2b:** I can make any of the four DB scripts fail *on purpose* (wrong password) and see exit code 1; `check_migrations.py` no longer prints a word that can be mistaken for "applied"; the live suite runs with the flag the docs name; and `pytest --cov` cannot go below the recorded floor.

## 5b. What lands on you because nobody else can do it

These are items that appeared in *other* members' handouts and are blocked behind your platform work. They are not their defects — they are your dependencies, and until they close, the four of them can only write code that never runs.

| From | Their item | Why it is yours | Unblocks when |
|---|---|---|---|
| M2 | Wizard + `/ingest/commit` paths hard-fail with `Ingestion storage is not installed` ([ingest.py:150](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/ingest.py#L150), [sources.py:95](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/sources.py#L95)) | that message means migration `0004_ingestion_import_runs` is not applied to a database she can reach — a D1/J1 problem, not a code bug | `verify_applied.py` green + `0004`–`0009` actually present |
| M2 | Item 13: run the ProvSQL ground-truth spike | `docker` and `psql` are both absent on this machine (J8) → the spike is unrunnable *anywhere in the team* until you settle D12 | D12 recorded with a real Postgres target |
| M2 | Item 11: scheduler — "pick where pull jobs run (M1 owns the runtime constraint)" | a Vercel request cannot hold a schedule (`maxDuration: 30`); only you can answer where the runner lives | your Wave 4 item 12 answer, written down |
| M3 | His screens have never returned real data; 64/70 endpoint bodies unexecuted | he cannot make a single authenticated request without a signed-up user and `KAIROS_TEST_USER_TOKEN` (J5/J6) | Wave 1 items 7–10 done, token issued |
| M3 | Evidence/lineage **export** routes do not exist | D10 (client vs server export) is an architecture decision you custodian; nobody should build it twice | D10 decided + contract committed |
| M4 | No routes for quality / glossary / domains / products / contracts / notifications / members | Gauree builds the routes, but every one of them needs a **workspace-scoped table with forced RLS** — that is your migration-review role, and D7 (visibility selector) changes the policy shape, so it must be settled *before* she writes policies | D7 decided + `0007` applied + review gate agreed |
| M4 | Members/roles/API keys/webhooks admin screens | the permission check has to come from `workspace_member`, not the JWT (G2/G3) | Wave 1 item 8 |
| M5 | His honesty gates cannot assert "the screen rendered from a real API response" | that assertion needs an authenticated browser session, which needs your signup + deployment (G3/G4) | a deployed URL + a real account |
| M5 | `check_migrations.py`'s false `RESULT: PASS` is itself a research-integrity signal | the script is yours; his new CI step (his §2b) will test *your* exit codes | J1–J4 fixed |

**Nobody owns these yet — take them or assign them explicitly today:**

- The 0008 `lifecycle_state` `CHECK` constraint allows only `CONFIGURED / VERIFIED / ERROR / REVOKED` ([0008_source_connections.sql:21-22](file:///E:/EDI-Metadata_Lineage/backend/migrations/0008_source_connections.sql#L21-L22)), which makes §5.4's twelve-state connector lifecycle **unstorable**. Anushka's fix is a migration change on an unapplied migration (M2 §2b A8) — review it with her rather than letting the code invent states the database will reject.
- The six screens missing from the nav (Sources, Freshness, Glossary, Domains, Settings, Notifications) have no route **and** no table. Someone must say which of M4's migrations adds them, or they will be built twice.
- `backend/app/repositories/` + `mock_repo.py` + legacy `schemas.py` = **515 statements at 0 % coverage** that nothing imports. Delete-or-wire is an M1 call (J9).
- The 80 skipped tests. 76 skip for the token, 2 for a known LEFT/RIGHT JOIN weakness. Nobody has ever said out loud whether "80 skipped" is acceptable for the demo — it is not, if the demo claims isolation.
- CI has no coverage floor, no live-test job, and a permanently red `live-smoke`. Reconciling what CI claims vs what it runs is contract custody (your §13).

## 5c. Your remaining list, in the order that unblocks the most people

1. `verify_applied.py` + make the four DB probes exit non-zero on failure (J1–J4, item 0). ~2 hours. Ends the false "Applied" claims for good.
2. D12 in `DECISION_LOG.md`: restore Supabase creds **or** install local Postgres. Until this, items 3-8 of everyone else's handouts are stalled.
3. `KAIROS_LIVE_API_TESTS` vs `KAIROS_TEST_USER_TOKEN` (J5) + a CI job that runs the live suite.
4. Two real signup accounts + `KAIROS_TEST_USER_TOKEN` handed to M3 and M4 so their screens can finally return data.
5. `0007_membership_roles.sql` tracked, applied, RLS forced, owner backfilled as `admin`; then `GET /workspaces/me` + members routes; then the two-workspace cross-tenant test **executed**, not skipped.
6. 401-on-navigation → redirect (J7) so `/ingestion.html` stops showing the user JSON.
7. D7 and D10 decided and written; D6 rollback owner named.
8. CODEOWNERS real handles + `TEAM_GUIDE` ownership/branch tables (G6/G8) — this is what got the other four to ≤2 merged PRs.
9. Push the 2 unpushed commits; split the ~4,000-line tree into per-stream PRs (G5) and get each owner to review their own slice.
10. Deploy: Vercel project, secrets, `check_deployment.py --base-url` → 0, `live-smoke` green, and the scheduler-runtime answer (items 11-12).

## 6. Do not

- Do not write "applied", "verified", "works" anywhere without a command output behind it — that is the team's own rule and the repo's current weakest point.
- Do not run destructive/reset commands against the shared project, do not disable RLS to make a test pass, do not commit secrets or the ZIP snapshots.
- Do not re-implement M2/M3/M4 features — hand them their slice and their own PR.

---

## 6. Full-project completion backlog — platform to 100 %

Everything below is measured (report §3, §10, §14; schema audit). Fix items first, then build.

### Fix (broken today)
| # | Task | DoD |
|---|---|---|
| F1 | `scripts/db/*` probes exit non-zero on failure; `check_migrations.py` cannot print "applied" without connecting | each probe vs a wrong password exits != 0 in CI |
| F2 | Add `to_regclass` fail-closed guards to `personalization.py` (asset_view/asset_star) and `integrations.py` (github_connection) — the only two route files missing them | with 0005/0006 unapplied, routes return 503 with named diagnostic, not raw 500 |
| F3 | `search.py:38` `_SORTABLE` offers `schema_name/asset_type/source_system` the SQL never aliases | `sort_by=` each key returns 200 |
| F4 | `/api/v1/health` returns 200 "ok" with `db="unavailable"` | degraded DB ⇒ 503 or status="degraded"; orchestrators can trust it |
| F5 | 0003 `kairos_workspace` has FORCE RLS but no policy (works only under superuser owner); 0004-0009 `REVOKE ... FROM anon, authenticated, service_role` fails on vanilla Postgres | migration chain applies on a clean local Postgres; document the Supabase-only constraint otherwise |
| F6 | 0007 membership tables are written and read by nothing — role is never checked anywhere | wire auth to membership as role source of truth (B1) or delete the schema |

### Build (missing for 100 %)
| # | Task | DoD |
|---|---|---|
| B1 | RBAC: owner/admin/editor/viewer × action matrix, enforced server-side (0007 tables exist) | a viewer cannot PUT metadata; test proves 403 |
| B2 | Admin/Settings surface: members+roles UI, API keys, webhook endpoints, security policy, defaults | screens exist, backed by tables, not localStorage |
| B3 | Failed-record quarantine: table + ingest hook (D9) | an invalid payload lands in quarantine with reason; ingest never silently drops |
| B4 | Deployment: real URL, migration story under D12, `check_deployment.py` asserts stylesheets resolve | live-smoke nightly is green against it |
| B5 | Live proofs: test user token → 76 skipped tests run; two-workspace RLS gate; idempotent-commit gate | all three executed once, output pasted into a PR |
| B6 | CI hardening with M5: false-green guard, coverage floor, authenticated browser test | CI fails when probes cannot fail |

Order: wait out the DB circuit breaker → F1/F2 → B5 → the rest. Your ordered personal list is §5c.
