"""Probe: execute every OpenAPI endpoint body with auth overridden and the DB
boundary stubbed.  No request reaches the real database; no port is bound.

For each endpoint we record:
  - status code returned
  - whether the handler body executed past auth + validation (proven by the
    RuntimeError('PROBE_STUB_DB') marker raised at the stubbed DB boundary)
  - any other failure class (validation, wrong method, crash before DB)
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from contextlib import contextmanager

sys.path.insert(0, r"E:\EDI-Metadata_Lineage")

from fastapi.testclient import TestClient  # noqa: E402

STUB_MSG = "PROBE_STUB_DB"


@contextmanager
def _stub_conn(*_a, **_k):
    raise RuntimeError(STUB_MSG)
    yield  # pragma: no cover


def install_stubs() -> list[str]:
    import backend.app.db as dbmod

    orig_get_conn = dbmod.get_conn
    orig_get_db_connection = dbmod.get_db_connection
    patched = []
    for name, mod in list(sys.modules.items()):
        if not name.startswith("backend.app"):
            continue
        if getattr(mod, "get_conn", None) is orig_get_conn:
            mod.get_conn = _stub_conn
            patched.append(name)
        if getattr(mod, "get_db_connection", None) is orig_get_db_connection:
            mod.get_db_connection = _stub_conn
            patched.append(name + ":get_db_connection")
    # auth must not provision a workspace (that would touch the DB)
    import backend.app.auth as authmod

    authmod.provision_personal_workspace = lambda user_id: "00000000-0000-0000-0000-00000000d3m0"

    from backend.app.auth import optional_user as _optional_user
    from backend.app.auth import require_user as _require_user

    async def fake_user():
        dbmod.set_workspace_id("00000000-0000-0000-0000-00000000d3m0")
        yield {"id": "00000000-0000-0000-0000-00000000d3m0", "email": "probe@example.com"}

    async def fake_optional():
        async for u in fake_user():
            return u
        return None

    return patched, _require_user, _optional_user, fake_user, fake_optional


def main() -> int:
    from backend.app.main import app

    patched, require_user, optional_user, fake_user, fake_optional = install_stubs()
    app.dependency_overrides[require_user] = fake_user
    app.dependency_overrides[optional_user] = fake_optional

    schema = app.openapi()
    client = TestClient(app, raise_server_exceptions=False)
    uid = str(uuid.uuid4())

    rows = []
    for path, methods in sorted(schema["paths"].items()):
        for method, op in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            real = re.sub(r"\{[^}]+\}", uid, path)
            kw = {}
            body_spec = op.get("requestBody", {})
            if body_spec:
                content = body_spec.get("content", {})
                if "multipart/form-data" in content:
                    kw["files"] = {"file": ("probe.txt", b"probe")}
                    kw["data"] = {}
                elif "application/json" in content:
                    kw["json"] = {}
            try:
                resp = client.request(method.upper(), real, **kw)
                status = resp.status_code
                try:
                    payload = resp.json()
                except Exception:
                    payload = {"raw": resp.text[:120]}
                detail = payload.get("detail") if isinstance(payload, dict) else None
                code = payload.get("code") if isinstance(payload, dict) else None
                rows.append((f"{method.upper():6} {path}", status, code, detail, payload))
            except Exception as exc:  # transport-level failure
                rows.append((f"{method.upper():6} {path}", "EXC", type(exc).__name__, str(exc)[:120], {}))

    proven, validation, crashed, other = [], [], [], []
    for label, status, code, detail, payload in rows:
        d = str(detail) if detail is not None else ""
        if status == 500 and STUB_MSG in d:
            proven.append((label, status, code, "body executed -> reached DB boundary"))
        elif status == 422:
            validation.append((label, status, code, d))
        elif status in (401, 403, 503):
            other.append((label, status, code, d))
        elif status == 500:
            crashed.append((label, status, code, d[:160]))
        elif status == 404:
            other.append((label, status, code, "404 (route shadowed or not matched)"))
        else:
            proven.append((label, status, code, d[:120] or "completed without DB"))

    out = {
        "modules_patched": len(patched),
        "total_endpoints": len(rows),
        "bodies_executed": len(proven),
        "validation_only": len(validation),
        "crashed_before_db": len(crashed),
        "auth_or_404": len(other),
        "rows": [
            {"endpoint": r[0], "status": r[1], "code": r[2], "detail": r[3]} for r in rows
        ],
    }
    with open(r"E:\EDI-Metadata_Lineage\.probe-rls\bodies_result.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    print(f"modules patched with DB stub: {len(patched)}")
    print(f"total endpoints probed: {len(rows)}")
    print(f"  bodies EXECUTED (DB-boundary marker or completed): {len(proven)}")
    print(f"  validation-only (422, body unproven): {len(validation)}")
    print(f"  crashed before DB boundary: {len(crashed)}")
    print(f"  auth/404 class: {len(other)}")
    print()
    print("== EXECUTED ==")
    for l, s, c, d in proven:
        print(f"{s} {l}  [{c}] {d[:90]}")
    print()
    print("== VALIDATION-ONLY (422) ==")
    for l, s, c, d in validation:
        print(f"{s} {l}  {d[:90]}")
    print()
    print("== CRASHED ==")
    for l, s, c, d in crashed:
        print(f"{s} {l}  [{c}] {d[:120]}")
    print()
    print("== AUTH/404 ==")
    for l, s, c, d in other:
        print(f"{s} {l}  [{c}] {d[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
