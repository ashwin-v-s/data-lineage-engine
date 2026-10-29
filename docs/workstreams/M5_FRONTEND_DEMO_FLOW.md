# M5 — Frontend Import-to-Catalog Demo

**Owner:** Person 5 · **Timebox:** 2–3 hours · **Architecture:** [`../KAIROS_FINAL_ARCHITECTURE.md`](../KAIROS_FINAL_ARCHITECTURE.md)

## Goal

Make the existing React/Vite entry and Kairos visual system show a truthful file import journey backed by the shared Supabase project: select → preview diagnostics → explicit confirm → authenticated API persistence to Supabase Postgres → catalog readback. Preserve the Stitch sign-in page, animation, existing CSS palette, and 3D Observatory.

## Inspect first

- `frontend/src/main.jsx`, `frontend/auth.js`, `frontend/auth-stitch.html`
- `frontend/app.js`, `frontend/assets.css`, `frontend/ingestion.html`, `frontend/ingestion.js`
- Current API wrapper/bearer fetch behavior and M3’s proposed request/response schema.

## Work

1. Keep auth UI and existing dashboard behavior working. Do not introduce a bypass login or a fake green “connected” state.
2. Build a clear Import page with file selection, format/schema feedback, preview counts, source/evidence labels, warnings, and an explicit confirm action. Provide a sample file clearly labelled as sample.
3. Call M3 preview and commit endpoints using the authenticated API client. Handle loading, empty, validation-error, expired-session, duplicate/idempotency, and success states.
4. On success, refresh data from the authenticated catalog API and link to the imported assets/lineage. Never treat browser-local preview data as a persisted catalog.
5. Ensure keyboard/focus use, narrow viewport layout, readable contrast, and retained Kairos CSS. Build with `npm ci` and `npm run build`.

## Supabase boundary

- Use the current Supabase Auth session through the existing Kairos auth bridge and the M3 API. The browser must not write catalog rows directly or receive a database password/service-role key.
- If uploaded file retention is needed, coordinate with M3 on Supabase Storage bucket/policies. For the first slice, keep parsed preview in memory and send validated metadata to the authenticated API.
- Do not add a local/mock database success path that looks like a Supabase import. Clearly label any offline sample preview.

## Likely files

- `frontend/src/` and existing `frontend/ingestion.html` / relevant JS/CSS
- Avoid backend/auth schema or database migrations; coordinate API contract with M3.

## Acceptance

- Preview is visibly distinct from committed catalog data.
- Invalid/unsupported file shows actionable diagnostics and cannot be “imported” as success.
- A successful import is verified by API readback after refresh.
- No tokens or provider secrets are rendered, logged, or sent to non-Kairos endpoints.
- `npm run build` succeeds; sign-in/dashboard visual surfaces remain intact.
