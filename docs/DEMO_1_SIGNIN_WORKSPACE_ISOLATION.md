# Demo 1 — Sign-in, Workspace Isolation, and Profile

**Presenter:** Jatin (M1)
**Duration:** 8–10 minutes
**Prerequisite:** Backend running (`uvicorn backend.app.main:app --reload`), frontend built (`npm --prefix frontend run build`), Supabase project credentials in `.env`.

---

## Pre-flight checklist

```powershell
# 1. Verify backend liveness
curl http://localhost:8000/healthz
# Expected: {"status":"ok","service":"kairos-api"}

# 2. Verify auth config is exposed (unauthenticated)
curl http://localhost:8000/api/v1/auth/config
# Expected: {"url":"https://...supabase.co","publishable_key":"eyJ...","auth_disabled":false}

# 3. Verify database connection
python scripts/test_connection.py
# Expected: exit 0 with "Connection test PASSED"

# 4. Verify migration state
python scripts/db/verify_applied.py
# Expected: exit 0 with "RESULT: PASS — every table … exists"

# 5. Verify RLS enforcement
python scripts/db/verify_rls.py
# Expected: exit 0 with "RESULT: PASS"

# 6. Verify workspace isolation (rollback-only)
python scripts/db/verify_workspace_isolation.py
# Expected: exit 0 with "All isolation checks passed"
```

---

## Walkthrough

### Step 1 — Open the sign-in page

1. Open `http://localhost:3000` (Vite dev) or `http://localhost:8000` (dist served by backend).
2. The sign-in page renders with the Kairos branding (auth-stitch.html).
   - **Offline note:** The sign-in page includes an inline CSS fallback. If CDN fonts are unavailable (e.g. offline demo), the page still renders using system fonts. The core layout is preserved by inline critical CSS.
3. Show the page has no pre-filled data and no access to workspace content.

### Step 2 — Demonstrate the auth gate

1. Open DevTools → Network tab.
2. Navigate directly to `http://localhost:8000/ingestion.html` without signing in.
3. Show the **302 redirect to `/?signin_required=1`** — this is the J7 fix. The server returns a redirect, not a raw JSON 401.
4. Try a direct API call:
   ```
   curl http://localhost:8000/api/v1/catalog
   ```
   Show: **HTTP 401** with JSON error `{"error":{"code":"UNAUTHENTICATED","message":"Sign in is required"}}`.
5. Show that 66 of 68 routes return 401 when unauthenticated; only `/healthz` and `/api/v1/auth/config` are public.

### Step 3 — Sign in with a real Supabase account

1. Enter email and password for a confirmed Supabase user.
2. Show the sign-in flow completes:
   - The access token is stored in `localStorage` / `sessionStorage` (show `kairos_supabase_session`).
   - The `Authorization: Bearer <token>` header is automatically injected for API calls (show in Network tab).
3. After sign-in:
   - The dashboard renders with workspace data (or empty-state if no metadata imported yet).
   - The greeting displays the signed-in user's identity from Supabase Auth metadata.

### Step 4 — Show workspace provisioning

1. Open DevTools Console and run:
   ```js
   fetch('/api/v1/me/workspace').then(r => r.json()).then(console.log)
   ```
2. Show the response contains:
   ```json
   {"ok":true,"workspace":{"id":"<uuid>","name":"My Workspace","owner_id":"<user-uuid>","created_at":"..."}}
   ```
3. Explain: the workspace was provisioned automatically by `auth.py:56` → `provision_personal_workspace(user_id)` on first authenticated request.

### Step 5 — Workspace list and switching

1. Open DevTools Console:
   ```js
   fetch('/api/v1/me/workspaces').then(r => r.json()).then(console.log)
   ```
2. Show: the user sees only workspaces where they have active membership.
3. Navigate to **Workspace Administration** (admin view in the app shell).
4. Show the workspace selector dropdown.
5. Switch to a different workspace (if available via invitation) and show:
   - The catalog content changes.
   - The `X-Kairos-Workspace-ID` header is sent on subsequent API calls.
   - Membership is verified server-side (`workspace_member` table, not JWT metadata).

### Step 6 — Demonstrate workspace isolation

1. Show the RLS mechanism:
   - `SET LOCAL ROLE kairos_app` + `set_config('kairos.workspace_id', ...)` scopes every query.
   - `FORCE ROW LEVEL SECURITY` on all 42+ tables means even the connection role is subject to policies.
2. Reference the evidence:
   ```powershell
   python scripts/db/verify_workspace_isolation.py
   ```
   Output: two temporary workspaces created, cross-workspace reads/inserts/updates blocked, all rolled back.
3. **Key claim:** workspace B cannot read workspace A's `dataset` rows. The insert into workspace A's asset from workspace B's context is blocked by RLS.

### Step 7 — Membership and invitation

1. In **Workspace Administration**, show the **Invite a member** form.
2. Create an invitation for a test email with role "Viewer".
3. Show the generated 7-day invitation link.
4. Show the pending invitation in the **Invitations** table.
5. Explain: the invitation is stored in `workspace_invite`, expires after 7 days, and acceptance is handled by `kairos_accept_workspace_invite()` which creates a `workspace_member` row.
6. If SMTP is configured: show the welcome email in the invitee's inbox.
7. If SMTP is not configured: say explicitly "SMTP delivery is gated on mail provider credentials; the invitation link is available for direct sharing."

### Step 8 — Profile identity

1. Navigate to **User Profile**.
2. Show that identity fields (name, etc.) are read from Supabase Auth `user_metadata`.
3. Edit the display name in the profile editor.
4. Show the save succeeds (calls `PUT /auth/v1/user` with updated metadata).
5. Clarify: "Profile picture and display preferences remain in this browser. Roles and permissions are never stored in user-editable JWT metadata."

---

## Evidence commands (paste these into your demo PR)

```powershell
python scripts/test_connection.py
python scripts/db/verify_applied.py
python scripts/db/verify_rls.py
python scripts/db/verify_workspace_isolation.py
python scripts/db/check_schema.py
python scripts/db/check_migrations.py
```

## What this demo does NOT prove

- Welcome email delivery (requires SMTP + `KAIROS_PUBLIC_APP_URL`).
- Social OAuth (Google/GitHub/Microsoft) — email/password only unless explicitly configured.
- Deployed URL — this demo runs locally unless Vercel project is linked and secrets set.
- Two-real-user Supabase token cross-tenant test — the `verify_workspace_isolation.py` script uses rollback-only DB transactions with the migration role, not two real JWT-authenticated users.

---

## Quick reference: auth contract

| Route pattern | Unauthenticated | Authenticated |
|---|---|---|
| `GET /healthz` | 200 | 200 |
| `GET /api/v1/auth/config` | 200 | 200 |
| `GET /ingestion.html` | 302 → `/?signin_required=1` | Serves HTML |
| `GET /api/v1/*` (all other) | 401 JSON | Workspace-scoped response |
| `POST /api/v1/*` | 401 JSON | Workspace-scoped write |
