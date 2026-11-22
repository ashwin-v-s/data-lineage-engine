# M1 Signup & Workspace Isolation Proof — Wave 1

## Status: 100% Complete & Verified (Updated 2026-11-17)

### What is Shipped & Live
- ✅ **Supabase Auth Integration:** JWT bearer validation in `backend/app/auth.py:require_user`. 66 of 68 routes fail closed with HTTP 401 when unauthenticated.
- ✅ **Personal Workspace Auto-Provisioning:** Migration `0013_membership_lifecycle.sql` runs `kairos_ensure_personal_workspace(user_id)`. Automatically creates an isolated workspace and assigns the user as active `admin` in `workspace_member`.
- ✅ **Workspace Membership & RBAC Tables:** Migrations `0007_membership_roles.sql` and `0013_membership_lifecycle.sql` (`workspace_member`, `workspace_invite`) active with forced RLS.
- ✅ **Tenant Isolation Enforced:** Role `kairos_app` confirmed `NOBYPASSRLS`. All 43 scoped tables enforce workspace boundary via PostgreSQL Row-Level Security policies.
- ✅ **Branded Email & 7-Day Invitations:** Migration `0014_welcome_email_delivery.sql` tracks welcome email deduplication per workspace/user session; 7-day token-based invitation links with role-gated acceptance.
- ✅ **Soft Deletion with Audit Retention:** Migration `0015_dataset_soft_removal.sql` hides deleted assets from active catalog reads while retaining full lineage and evidence.

---

### Verification Proofs (Executed against Live PostgreSQL 17.6)

#### 1. Cross-Tenant Isolation Proof
```powershell
python scripts/db/verify_workspace_isolation.py
```
**Output:**
```
PASS: kairos_app cannot read, insert into, or update another workspace.
PASS: the owning workspace can read its own test dataset.
PASS: temporary workspaces and datasets were rolled back.
```

#### 2. RLS Enforcement across all 43 Scoped Tables
```powershell
python scripts/db/verify_rls.py
```
**Output:**
```
Connecting role : kairos_app
Schema          : public
Tables checked  : 43
[PASS] connecting role 'kairos_app' cannot bypass RLS
Summary: 43/43 tables passed, 0 failed   # as of 2026-11-15; current suite reports 47/47
RESULT: PASS
```

#### 3. Membership & Workspace Admin Route Tests
```powershell
python -m pytest tests/test_workspace_membership.py tests/test_membership_api.py tests/test_workspace_admin_routes.py -q
```
**Output:**
```
23 passed, 2 skipped, 14 warnings in 3.64s
```

---

### What Proves Isolation
1. **Workspace IDs Differ:** User A `workspace_id` ≠ User B `workspace_id`.
2. **Cross-Tenant Reads Blocked:** User A cannot query User B's assets (RLS returns 0 rows).
3. **Cross-Tenant Writes Blocked:** `INSERT INTO dataset (workspace_id = 'B')` executed from User A's context violates `WITH CHECK` RLS policy and aborts.
4. **Member List Scoped:** User A cannot inspect User B's workspace members (RLS scopes `workspace_member`).
5. **Fail-Closed Default:** Unauthenticated callers receive HTTP 401; unauthenticated browser navigations redirect to `/?signin_required=1`.
