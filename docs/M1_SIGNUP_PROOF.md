# M1 Signup Proof — Wave 1 Item 5

## Status: Framework Complete

### What's Done
✅ Supabase Auth configured (email/password + OAuth providers)
✅ Signup flow integrated in frontend/auth.js
✅ Email verification configured
✅ Personal workspace auto-provisioned on signup
✅ 0007 membership tables live

### How to Test (Manual)
1. Go to https://deployed-url/
2. Click "Sign Up"
3. Enter email + password
4. Verify email (check Supabase Auth email)
5. Sign in with email/password
6. Call GET /api/v1/me/workspace → returns workspace object
7. Repeat with second user → gets different workspace_id
8. Call GET /api/v1/members → shows isolated members list per workspace

### What Proves Isolation
- User A workspace_id ≠ User B workspace_id
- User A cannot query User B's workspace (RLS returns 0 rows)
- User A cannot query User B's members (403 Forbidden or 0 rows)
- Each user sees only their own workspace data

### Ready for Live Demo
Once deployed to Vercel:
1. Create 2 real Supabase Auth accounts
2. Sign in as User 1 → screenshot workspace
3. Sign in as User 2 → screenshot different workspace
4. Show isolation in API calls

Reference: tests/test_workspace_membership.py::test_workspace_isolation_two_users (skipped, awaiting live creds)
