# Authentication Providers — verified status and setup instructions

Status recorded **2026-10-31** against the shared Supabase project
`tkvzafrcszdtyeewfhig` (the project `SUPABASE_URL` / `.env` actually points at,
and the one `/api/v1/auth/config` serves to the browser).

**Nothing in this file is a secret.** Client IDs and secrets are entered by the
project owner directly in the Google Cloud Console and the Supabase dashboard.
They must never be committed, pasted into chat, or written to a tracked file.

## Verified provider status

| Provider | Supabase setting (`external.*`) | `GET /auth/v1/authorize` | Usable today |
| --- | --- | --- | --- |
| Email / password | `email = true` | n/a | **Yes** — confirmation required, no confirmed users yet |
| GitHub | `github = false` | `400 Unsupported provider: provider is not enabled` | **No** |
| Google | `google = false` | `400 Unsupported provider: provider is not enabled` | **No** |
| Microsoft | `azure = false` | `400 Unsupported provider: provider is not enabled` | **No** |

How this was measured (no credentials involved):

```bash
# 1. What Supabase actually advertises (public endpoint):
curl -s -H "apikey: <publishable key>" https://<ref>.supabase.co/auth/v1/settings

# 2. Whether the authorize endpoint accepts each provider (no redirect followed):
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "apikey: <publishable key>" \
  "https://<ref>.supabase.co/auth/v1/authorize?provider=github&redirect_to=http://127.0.0.1:3000"
```

Both probes were also exercised through the real UI: clicking **GitHub**
navigated to `…/auth/v1/authorize?provider=github&redirect_to=http://127.0.0.1:3000`
and returned the 400 body above, and clicking **Microsoft** navigated with
`provider=azure` and returned the same 400. Those redirects prove the front-end
wiring is correct — the provider mapping (`Google→google`, `GitHub→github`,
`Microsoft→azure`) is right. The failure is purely unconfigured provider state
in Supabase.

> If the Supabase dashboard shows GitHub as available, confirm the dashboard is
> showing project ref **`tkvzafrcszdtyeewfhig`**. A different project (or the
> "Providers" catalogue list rather than an enabled toggle) would explain the
> discrepancy; the app talks to the project above and that project reports
> `github = false`.

## Why Google (and GitHub, Microsoft) still appear on the login page

The buttons are **static markup**, not generated from Supabase configuration.
`frontend/auth-stitch.html` hardcodes `onclick="handleSSOLogin('Google', this)"`
(twice per provider — once in the sign-in panel, once in the sign-up panel), and
`frontend/src/main.jsx` always renders the login iframe. Nothing in the original
flow asked Supabase which providers were enabled, so all three were presented as
working options regardless of the backend state.

That is now corrected without changing the design or the auth architecture:

- `frontend/auth.js` reads the public `/auth/v1/settings` endpoint at boot and
  forwards the result to the login frame (`control: 'providers'`).
- `frontend/auth-stitch.html` disables any provider button whose provider is
  reported `false`, sets `aria-disabled`, adds a tooltip explaining it is not
  configured, and applies the `.sso-unavailable` style (dimmed, struck-through
  label, non-actionable cursor). `beginOAuth()` also refuses to redirect to a
  provider it knows is disabled, so the user gets a sentence instead of a raw
  400 JSON page.
- Availability is only applied when Supabase answers successfully, so a transient
  failure cannot disable a working provider.

Verified in the browser after the change: all six provider buttons
(`Google`, `GitHub`, `Microsoft` × sign-in/sign-up) report `disabled = true`,
`aria-disabled = "true"` and the explanatory tooltip, while **Email & password**
stays enabled.

## Google — exact configuration required

### A. Google Cloud Console

1. Open <https://console.cloud.google.com> and create (or select) a project,
   e.g. `kairos-auth`.
2. **APIs & Services → OAuth consent screen**
   - User type: **External** (use **Internal** only with a Google Workspace org).
   - App name: `Kairos`, support email, developer contact email.
   - Scopes: leave the defaults `openid`, `email`, `profile` — no sensitive
     scopes are needed for sign-in.
   - While the app is in **Testing**, add the Google account(s) you will sign in
     with under **Test users**, otherwise consent fails with
     `Error 403: access_denied`.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Web application**
   - Authorized **JavaScript origins**:
     - `http://127.0.0.1:3000`
     - `https://tkvzafrcszdtyeewfhig.supabase.co`
   - Authorized **redirect URI** (exact, no trailing slash):
     - `https://tkvzafrcszdtyeewfhig.supabase.co/auth/v1/callback`

   The redirect URI points at **Supabase**, not at the Kairos app: Supabase
   completes the code exchange and then bounces the browser to the Kairos
   origin.
4. Copy the **Client ID** and **Client secret**.

### B. Supabase dashboard

1. **Authentication → Providers → Google** → toggle **Enable**.
2. Paste the **Client ID** and **Client secret** → **Save**.
3. **Authentication → URL Configuration**
   - **Site URL**: `http://127.0.0.1:3000`
   - **Additional redirect URLs** (the app sends `redirect_to` explicitly, so
     these must be allow-listed or Supabase will reject the redirect):
     - `http://127.0.0.1:3000`
     - `http://localhost:3000`
     - your production origin, when one exists

### C. Verify

```bash
curl -s -H "apikey: <publishable key>" https://tkvzafrcszdtyeewfhig.supabase.co/auth/v1/settings \
  | python -c "import json,sys; print(json.load(sys.stdin)['external']['google'])"
# expected: True
```

Then reload the Kairos sign-in page — the Google button re-enables itself
automatically (the front-end re-reads the settings on load) and completes a
consent round trip. Email/password keeps working throughout.

## GitHub — what is still missing

Same shape as Google, with GitHub's own app settings:

- GitHub → Settings → Developer settings → **OAuth Apps** → New OAuth App
  - Homepage URL: `http://127.0.0.1:3000`
  - Authorization callback URL:
    `https://tkvzafrcszdtyeewfhig.supabase.co/auth/v1/callback`
  - Copy the Client ID and generate a Client secret.
- Supabase → Authentication → Providers → **GitHub** → enable, paste both, save.
- Verify with the `/auth/v1/settings` probe (`external.github` → `true`).

## Microsoft — what is still missing

Supabase exposes Microsoft as the **`azure`** provider (the app already maps
`Microsoft → azure`):

- Azure Portal → **Microsoft Entra ID → App registrations → New registration**
  - Redirect URI type **Web**:
    `https://tkvzafrcszdtyeewfhig.supabase.co/auth/v1/callback`
  - Copy the **Application (client) ID**; create a **client secret** under
    *Certificates & secrets*.
- Supabase → Authentication → Providers → **Azure** → enable with the application
  ID, secret and tenant (use `common` for multi-tenant or your tenant ID).
- Verify with the probe (`external.azure` → `true`).

## Boundaries

- Do not hardcode provider client IDs or secrets in `frontend/` or `backend/`;
  they live only in the Google/Azure consoles and the Supabase dashboard.
- Do not bypass Supabase Auth. The API keeps verifying bearer tokens through
  `/auth/v1/user`; nothing here weakens that path.
- The demo's supported sign-in path remains **email/password with confirmed
  email** until at least one OAuth provider is enabled *and* a real round trip
  has been completed and recorded.
