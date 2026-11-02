# Handout M4 — Gauree (`gaureehatkar`) · Governance & Product Shell

**Stream:** M4 — the workspace a user actually lives in: shell, Home, Sources/Freshness/Quality/Incidents screens, governance vocabulary (glossary, domains, data products, contracts), notifications.
**You own:** `frontend/` (shell, Home, governance screens), `backend/app/api/routes/{governance,sources,assets} UI-facing parts`, `backend/app/services/freshness.py`, migrations for quality/glossary/domain/product/contract/notification, Realtime + notification wiring.
**Read first:** [KAIROS_ARCHITECTURE_V2.md](../KAIROS_ARCHITECTURE_V2.md) §3 C3/C6, §5.4–§5.6, §6, **§9 (Sources screen spec)**, **§10 (the demo, step by step)** · **[KAIROS_PRODUCT_SPEC_PERPLEXITY.md](../KAIROS_PRODUCT_SPEC_PERPLEXITY.md) §1 shell, §2 Home, §6 Sources, §7 Freshness, §8 Quality, §9 Incidents, §12 Settings/admin, §13 Realtime, §16 poster wording** · [PROJECT_STATUS_2026-11-02.md](../PROJECT_STATUS_2026-11-02.md) · **[VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) §5 (what the running UI actually did today)**

---

## 1. What you have already shipped (evidence)

- `feature/m5-frontend-api` → PR #6 (merged): the M5 frontend + API client (`frontend/src/api/client.ts`, `types.ts`, `Header`, `LineageCanvas`, `Inspector/DetailsTab`, `LineageNode`).
- PR #9 (closed unmerged) and its commit `6684589` "M5: Remove hardcoded mock data from UI — show real data only", preserved by Jatin's rebase into `main` as PR #12. The mock strings you removed are gone from the live shell — that intent is in.
- `08907b3` API-route-to-Supabase wiring + CORS fix + frontend URL fixes.
- **Since 2026-10-01 no commits.** Perplexity's 14-screen product spec, written Nov 1, is now your brief.

## 2. What is **not** done — your gaps

| # | Gap | Proof |
|---|---|---|
| G1 | **Governance backend is uncommitted and unscheduled.** `governance.py` (9 routes: SLAs, freshness, evaluate, incidents + ack/investigate/resolve), `services/freshness.py` (pure evaluator), `0009_governance.sql` (`freshness_sla`, `freshness_evaluation`, `incident`, `incident_event`) are untracked, unverified against the live DB, and **`/datasets/{id}/evaluate` only runs when a user asks** — Perplexity's core requirement is a scheduled evaluator (every 15 min/hourly). | `git status`; no scheduler in repo |
| G2 | **Quality does not exist.** No `quality_assertion`/`quality_result` table, no assertion routes, no Quality screen beyond fixture numbers. Perplexity §8 + freshness-as-assertion model (OpenMetadata "Table Data to Be Fresh") is the spec. | grep: absent |
| G3 | **Glossary, Domains, Data Products, Contracts are UI text only.** No tables, no routes, no linkage to assets; PII tagging/classification and lineage-based PII propagation (spec §11, and the `PII_SOURCE → INHERITED → MASKED → POTENTIAL` chain) are unimplemented even though the demo fixtures already carry a `classification:'PII_SOURCE'` field in `frontend/app.js`. | grep: no code |
| G4 | **No notifications, no Realtime.** Supabase Realtime is explicitly deferred in `SUPABASE_FEATURE_ADOPTION.md` and nothing subscribes; the notification bell/center/routing (`owner`, downstream owners, stewards) from spec §9/§15 does not exist. | code |
| G5 | **Home dashboard is decorative in places.** Cards render, but not every metric is a clickable filtered link (spec §2 "do not make the dashboard number-heavy; each metric should be clickable"), and some counts still come from demo fixtures rather than the API. | `app.js` |
| G6 | **Settings/admin surface missing:** workspace members + roles (needs M1's `0007`), API keys, webhooks, credential policy, audit view. `audit.py`/`owner.py` routes exist but no screen drives them. | UI |
| G7 | **Live governance views are untracked** (`src/views/{freshness,incidents,capabilities}.js`, `src/components/{IncidentsView,AssetCapabilitiesPanel,DataModeLabel}.jsx`, `src/api/client.js`) and the legacy `app.js` (~10 `fetch` calls, still holding `DEMO FIXTURE` arrays) is the actual renderer for 6 of the 14 screens. The shell/legacy bridge is fragile and undocumented. | `git status` |
| G8 | **Status-bar / connection-health layer** (sync status, last refreshed, environment label) from spec §1 is not implemented. | UI |
| G9 | **Incident → owner routing and resolution evidence** are partial: lifecycle endpoints exist, but assignment to owner/steward, notification, and "resolution reason/action/by/time" capture are not wired end to end. | `governance.py:545-557` |

## 2b. Executed today — defects that are **yours**, with the command that proved them

Evidence in [VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) §1, §3, §5. This is the stream with the largest gap between what is written and what runs.

| # | What I ran | What happened | Consequence |
|---|---|---|---|
| K1 | `pytest --cov=backend.app` | `governance.py` **28 %**; **0 % body coverage on** `acknowledge_incident`, `investigate_incident`, `resolve_incident`, `get_incident`, `list_incidents`, `list_slas`, `upsert_sla`, `list_freshness` | the incident lifecycle has never executed. Not one acknowledge or resolve has run in any test |
| K2 | read `tests/test_incidents.py` | its own header says *"assert only the pure request-validation behaviour"* and **all seven HTTP tests assert `422`** ([test_incidents.py:6](file:///E:/EDI-Metadata_Lineage/tests/test_incidents.py#L6)) | the "incident console works" claim is backed by input-rejection tests only |
| K3 | `grep` for consumers of the React live views | **`IncidentsView.jsx` and `AssetCapabilitiesPanel.jsx` are imported by no module. `src/views/freshness.js` has no consumer at all.** Only `DataModeLabel.jsx` is mounted ([main.jsx:104](file:///E:/EDI-Metadata_Lineage/frontend/src/main.jsx#L104)) | the entire live-data governance layer you built is **dead code today**. What a user sees is legacy `app.js` fixtures — this is gap G7, now proven by execution rather than by `git status` |
| K4 | listed the served OpenAPI paths | **no routes exist** for quality, glossary, domains, data products, data contracts, notifications, API keys, webhook registration, or members admin (only `/owner/team-members`) | tasks 8-12 have no backend to build UI against. Spec §14 was right that these are absent, and the checklist's "fixtures only" wording understates it: there is no API either |
| K5 | clicked through the running app | the mode banner says **"Connected catalog mode — Views use records returned by the PostgreSQL catalog API"** in a mode that made **zero** catalog calls, sitting next to **"Demo preview · synthetic sample data — No catalog access"** | two contradictory statements, both visible, at the top of every screen. This is exactly what M5's honesty gate is supposed to prevent, and it does not |
| K6 | counted those banners | **0 on entering demo → 5 after 5 view clicks.** One is appended per render and never removed | after a normal demo run the header is a wall of ~20 duplicated banners. Reproducible, visible, and demo-breaking |
| K7 | navigated the sidebar | present: Home, Catalog×3, Data Products, Lineage×4, Import metadata, Pipeline runs, Evidence, Data quality, Incident console, Stewardship, Integrations, Preferences. **absent: Sources/connections, Freshness, Glossary, Domains, Settings (members · roles · API keys · webhooks · audit), Notifications** | six of the fourteen required screens have no entry point at all |
| K8 | opened `/ingestion.html` from the sidebar | the browser displayed **raw JSON**: `{"error":{"code":"UNAUTHENTICATED","message":"Sign in is required"}}` | the Import metadata screen is unreachable and shows an API error body to a human (M1 fixes the redirect; you fix the fallback state) |
| K9 | loaded the page with the console open | Tailwind comes from `cdn.tailwindcss.com` ([auth-stitch.html:6](file:///E:/EDI-Metadata_Lineage/frontend/auth-stitch.html#L6)); `three` and `chart.js` are injected from jsDelivr by [auth.js:7-8](file:///E:/EDI-Metadata_Lineage/frontend/auth.js#L7-L8) | no internet ⇒ no layout, no charts, no 3D observatory. Vendor these before the demo |
| K10 | searched `0009_governance.sql` for a schedule column | `freshness_sla` has **no `evaluation_schedule` and no `paused` column**, and code-side [freshness.py:27](file:///E:/EDI-Metadata_Lineage/backend/app/services/freshness.py#L27) defines five states — `HEALTHY / AT_RISK / LATE / STALE / UNKNOWN` — while v2 §5.6 requires six including **`PAUSED (explicitly disabled)`** | your Freshness screen cannot offer a pause control or a next-evaluation time, and cannot render the state the spec names. This is a schema change (needs M1 review, same migration window as Anushka's A8/A15) — decide it with her, not twice |
| K11 | grepped for realtime wiring behind the "live" language | **zero** occurrences of `realtime`, `channel(`, `postgres_changes`, `subscribe` in `frontend/*.js`, `frontend/src` or `backend/app` | nothing in Kairos pushes an update to a browser today. Any shell copy that says "live"/"real-time" (K5's banner is one) is unsupportable; and `src/views/freshness.js` cannot become a consumer of anything until M2 ships a push or pull path |
| K12 | same 72-op probe + frontend endpoint map | **no screen calls any of your live endpoints** — `governance/freshness`, `governance/incidents` (+ ack/investigate/resolve), `governance/slas`, `audit/*` (9 routes), `metadata/*`, `owner/*` are called by zero frontend files; the React governance views remain orphaned (`views/freshness.js`, `views/incidents.js`, `views/capabilities.js`, `IncidentsView.jsx`, `AssetCapabilitiesPanel.jsx` imported by nothing); `observatory.js` and `stewardship.js` contain ZERO API references; and the `/rea/*` family returns **200 while logging `[WinError 2]`** — its subprocess never launches and the failure is swallowed | mount or delete the orphaned views; point one real screen at `/governance/freshness` + `/governance/incidents`; fix or label the REA swallow | report §9, §10

**Good news, recorded so you do not redo it:** the governance code and `0009_governance.sql` are **column-consistent** — every column referenced for `freshness_sla`, `freshness_evaluation` and `incident_event` exists in the migration. So once M1 restores the DB, this slice has a real chance of working; it is unverified, not known-broken.

## 3. What you need to do

**Wave 0 — from §2b, fix these before building any new screen**
0a. **One mode banner, and it must match reality (K5).** Compute a single provenance state per render — `LIVE` / `IMPORTED` / `DEMO FIXTURE` / `NOT CONNECTED` — from whether an authenticated request actually succeeded, and render **one** line. Delete the "Connected catalog mode / records returned by the PostgreSQL catalog API" string from any path that made no call. If the app is in demo preview, the only permitted sentence is the demo one.
0b. **Stop the banner accumulation (K6).** The notice strip is appended on every render. Render into a fixed container that is replaced, not accumulated — assert it in a test by clicking five views and counting banner nodes (I measured 0 → 5).
0c. **Mount the live views you already wrote (K3).** `IncidentsView.jsx`, `AssetCapabilitiesPanel.jsx` and the freshness view have no consumer today. Wire them into `main.jsx` behind the nav entries, or delete them. Dead components are worse than missing ones because they make the plan look done.
0d. **Add the six missing nav entries (K7):** Sources/connections, Freshness, Glossary, Domains, Settings, Notifications. A screen with no entry point does not exist for a user or an examiner.
0e. **Give `/ingestion.html` a human fallback (K8)** — a "sign in to import metadata" state, not the JSON error body — once M1 makes navigation 401s redirect.
0f. **Vendor Tailwind, three.js and chart.js (K9)** and confirm the app still renders with the network offline. Then run `npx playwright install chromium` once and add it to `docs/TEAM_GUIDE.md`.

**Wave 0 — the shell decisions (unchanged)**1. PR the uncommitted governance + frontend-view slice from Jatin's tree as your own: read it, run it, and state in the PR which parts you verified against the live DB (blocked on M1's credential fix — escalate it).
2. Write the shell decision down (one page): what `main.jsx` owns, what `app.js` still owns, and the migration order. Every screen you take over must stop reading fixtures.

**Wave 1–2 — make monitoring real**
3. Freshness: apply the state rules exactly (`HEALTHY ≤80%`, `AT_RISK >80%`, `LATE >SLA`, `STALE >n×SLA`, `UNKNOWN` no evidence, `PAUSED` explicit) and the evidence-first rule C3 — never `LATE` without a known last-good update. Source-specific signals: OpenLineage run (P0), dbt `run_results` (P1, needs M2), `updated_at` (P1), GitHub commit (P1), manual confirm (with `MANUAL` provenance).
4. Schedule the evaluation with M2/M1 (serverless can't loop; use Supabase Cron / an Action / a small worker) and record each run as a `freshness_evaluation` row. Use the spec's frequency defaults rather than inventing numbers: critical/certified **every 5–15 min**, standard production 30–60 min, internal 6–24 h, experimental/demo manual — and for the MVP start at *freshness every 15 min or hourly, PostgreSQL sync daily or every 6 h, GitHub manual or hourly, dbt on upload/CI, OpenLineage event-driven*. Then build the **eleven** freshness components (checklist §7): dashboard counts, table, filters, trend chart, SLA config, evaluation schedule, evidence, incident trigger, notification settings, **manual refresh** (records `MANUAL` provenance and is honest that a human claim is not a runtime observation), and the **unknown-state explanation** — the last two are the ones people forget, and the explanation line is what turns `UNKNOWN` into a feature rather than a bug.
5. Incidents: breach ⇒ **exactly one** open incident (dedupe key = asset + breach type), owner + steward assignment, timeline `detected → acknowledged → investigating → resolved`, resolution form (reason, action, by, time), impact panel from downstream lineage (needs M3), plus three spec components we do not have at all: **comments**, **related/similar historical incidents**, and **escalation when unresolved** (the routing pipeline is severity → find owner *through lineage* → dedupe → notify → escalate → resolve-with-evidence, not just "create a row"). Tests `tests/test_freshness.py`, `tests/test_incidents.py` (extend — both are currently offline-only).
6. Sources screen: implement Architecture v2 **§9** + checklist **§6** exactly — wizard (type → credentials → **test** → **scope** → **discover** → **review discovered + save schedule**, each a separate state per §5.4/§9.1), scope checkboxes (incl. SSL `Require|Prefer|Disable` and the visibility selector pending D7), lifecycle badges, sync history (started/finished/status/discovered/updated/deleted/errors), "Sync now", sync schedule picker, credential health + rotate, and **all seven failure states with their own copy** — notably `Connected but partial authorization` (grant-or-reduce-scope as the offered action) and `Connected — no discoverable assets` (honest empty state, not a failure). Credential display follows §9.1: masked (`postgres://demo_user:••••••@host:5432/sales`), never plaintext, never in logs. File imports appear in **import history**, never as a live connector with a "last synced" clock (§9.5). Tab gating reads the registry derived from granted scope (§9.6).
7. Home: build the **ten sections** the spec lists — hero, health cards (total/healthy/at-risk/**late**/**unknown**), incident summary (open/critical/mine/resolved today), source health (connected/failed/**credentials expiring**/last sync), freshness overview, lineage overview (**observed/possible/unknown edge counts**), recent activity (**including PII changes** — depends on task 9), recent runs (per source type), my ownership, quick actions. Every metric is a filtered link; every count comes from the API.

**Wave 3–4 — governance vocabulary and product shell**
8. Quality (checklist **§8**, nine components): `0010_quality.sql` (`quality_assertion`, `quality_result`), assertion types (freshness, completeness, uniqueness, validity, schema, custom SQL — custom SQL must be **validated, parameterized and read-only**, never executed from an upload), **test creation form** (asset, type, threshold, schedule, severity), test list + detail (definition, threshold, latest result, history, evidence), trend chart, schedule, **test-to-contract link**, failure → incident. The failure-investigation pane must honour §9.8: with no `data:preview` grant it shows counts + the assertion SQL and **no row values** — "sample values" is a data-access feature, not a metadata one.
9. Glossary + PII (checklist **§11**): `glossary_term`, `term_assignment`, governance status (draft/approved/deprecated), term→asset linking and a "related lineage" view. PII classification is an **evidence-backed record with the five-rung ladder** `PII_SOURCE → PII_INHERITED → PII_MASKED → PII_POTENTIAL → PII_CLEARED (aggregation, no identifiers — still requires review)`, plus `UNKNOWN` when the lineage is missing; manual steward tag = `OBSERVED` manual, copy-through-lineage = `OBSERVED` inherited, SQLGlot guess = `POSSIBLE` inherited. **Classification propagates; access never does** — `pii:classify` / `governance:read` are separate from `data:preview` / `data:pii:unmasked`, and the PII inspector shows who classified what, when, and by which path.
10. Domains, Data Products, Contracts: `domain`, `data_product`, `product_asset`, `data_contract` + versioned clauses bound to assertions (ODCS shape), product health derived from freshness/quality/incident/coverage rows — no invented scores.
11. Notifications + Realtime (checklist **§13**): notification table + bell/centre, **seven types** (freshness breach, quality failure, new incident, sync failure, **credential expiry**, lineage change, PII change), mark-read single and bulk, filters, and an action link that opens the affected asset/incident/source. Routing targets: asset owner, downstream owners, steward, connection owner, data-product owner. Supabase Realtime as **invalidation → authorized refetch only** (C6), covering the eight event→reaction rows. If delivery cannot be tested, say so in the UI and in the report.
12. Settings + admin (checklist **§12**): members & roles (consume M1's endpoints), notifications preferences, **freshness defaults + sync defaults incl. retry policy**, API keys create/revoke, webhook endpoints (OpenLineage / GitHub / dbt), credential policy, audit view (consume `audit.py`), and the admin surface the spec calls minimal-but-real: connection inventory, ingestion-run history, **failed-record quarantine**, **fixture registry** (built with M5 — it is what makes "this is demo data" provable), classification approval queue, retention controls.
13. Global layout §1 completeness: top bar global search (M3), workspace selector, status bar with sync/health/last-refreshed/environment.
14. Accessibility/honest states: keyboard focus, narrow viewport, contrast, and honest empty/partial/failed/unsupported states on every screen (M5's audit locks the multi-redundant state styling — label + glyph + border, not colour alone).

## 4. Definition of done (your gate)

A scheduled freshness evaluation on live data detects a breach, opens exactly one incident, assigns and notifies the owner, shows the evidence row that justifies the state, and closes with a recorded resolution — all visible on a deployed Kairos with `source_mode` labels, no fixture substituting for a failed call.

**Additions from today's measurement (§2b):** one provenance banner per screen and it matches whether a request succeeded; no accumulated banner stack after clicking through the app; `IncidentsView` / `AssetCapabilitiesPanel` / the freshness view mounted or deleted; Sources, Freshness, Glossary, Domains, Settings and Notifications reachable from the nav; a test that **acknowledges and resolves** an incident (not just a `422`); and the app rendering with the network disabled.

## 5. Do not

- Do not show `LATE`/`STALE` for assets with no evidence (C3) and do not display "connected" after a credential test alone.
- Do not render a tab as available when the capability registry says otherwise — gate every Asset Detail tab through M1/M3's registry.
- Do not add numeric confidence, AI-graded "quality scores", or analytics numbers that no row supports.
- Do not put service-role keys or connection strings in the browser, and never bypass RLS to make a screen populate.

---

## 6. Full-project completion backlog — governance & shell to 100 %

### Fix (broken today)
| # | Task | DoD |
|---|---|---|
| F1 | Mount the orphaned live views (`IncidentsView.jsx`, `views/freshness.js`, `views/capabilities.js`) or delete them (K12) | each nav entry renders its real view; zero orphan modules |
| F2 | Data-quality screen honesty: delete or demo-gate 4 hardcoded chart arrays + "Open Incidents 1" + "Tier-1 85 %" (report §14) | every number on screen is API-derived or labeled DEMO FIXTURE |
| F3 | Banner contradiction + accumulation (P1): one banner, mode-accurate, never appended twice | 20-click walk ends with exactly one banner |
| F4 | `app.js:652` empty `save-profile` handler shadows the real one (A1 worst-#1) | profile save persists; test clicks the button |
| F5 | `metadata.py` bulk-update `pass` no-ops counted as successes; 404→500 swallow | unimplemented ops return 501-named; 404 stays 404 |
| F6 | `audit.py` rollback never executes (PENDING forever) + compliance-report hardcodes 0s and an invented score | approve/execute path exists or the endpoint says so; score derived from audit_event only |
| F7 | Products view + incidents view silently render Home (browser §14) | `data-view=products|incidents` renders their own screens |

### Build (missing for 100 %)
| # | Task | DoD |
|---|---|---|
| B1 | **Freshness evaluator** (C1 #1): scheduled evaluation under D12 constraints + PAUSED state | SLA→state→incident loop runs; PAUSED round-trips 0009 (needs CHECK widening) |
| B2 | **Quality engine** (C1 #2): `quality_assertion`/`quality_result` tables + API + live UI | a failing assertion raises an incident; capabilities gate flips from "not collected" to real |
| B3 | **Data contracts** (C1 #3): versioned contracts bound to quality assertions | contract v1→v2 with enforcement mode visible on asset |
| B4 | **Notifications center** (C1 #5): bell, history, types, mark-read, delivery prefs | LATE freshness + incident create a notification; mark-read persists |
| B5 | **Incident routing pipeline** (C1 #6): classify → owner-via-lineage → dedupe → notify → escalate | an incident lands assigned to the upstream owner with evidence attached |
| B6 | **Stewardship + product registries** (backend): `/requests`, `/proposals`, `/data-products` CRUD (the phantom endpoints' real replacements) | approve/reject/register buttons work end-to-end |
| B7 | Settings UI (members/roles/API keys/webhooks) with M1's RBAC (C1 #12) | screens backed by 0007 tables |
