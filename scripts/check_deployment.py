#!/usr/bin/env python
"""Operator CLI: verify a Kairos deployment is live and correctly configured.

This script is the manual/live counterpart of the offline CI suite: it talks to
an *already deployed* API and checks two things that CI cannot see.

1. Liveness + readiness: it issues ``GET {base-url}/health`` and asserts the
   deployment answers with the documented success shape
   (``{"status": "ok", "db": ...}``), reporting the HTTP status and latency.
2. Configuration: it checks that every environment variable a deployment needs
   is present and non-empty.  ``.env`` is read with ``python-dotenv`` exactly
   like the other operator scripts.  Secret values are checked for presence
   only and are never printed.

Each check prints a single ``[PASS]`` / ``[FAIL]`` line and the run ends with a
summary.  The process exits non-zero when any check fails (or when
``--base-url`` is missing), so a workflow can gate on it.

``--base-url`` is the deployed API base that serves the health route, i.e. the
FastAPI prefix mounted in ``backend/app/main.py`` plus the router path
(``.../api/v1`` + ``/health``).  For the default deployment that means passing
``--base-url https://<deployment>/api/v1``.

Usage
-----
    python scripts/check_deployment.py --base-url https://kairos.example.com/api/v1
    python scripts/check_deployment.py --base-url https://kairos.example.com/api/v1 --timeout 15

The module has no import-time side effects; all work happens in ``main``.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import NamedTuple

import httpx
from dotenv import load_dotenv


# Router path of the health endpoint (``backend/app/api/routes/health.py``),
# relative to the API base passed via ``--base-url``.
HEALTH_PATH = "/health"

# Environment variables a deployment needs, mirroring docs/DEPLOYMENT.md §2
# and §4.  The boolean marks values that are secret: they are checked for
# presence only and their contents are never printed.
REQUIRED_ENV_VARS = (
    ("DATABASE_URL", True),
    ("SUPABASE_URL", False),
    ("SUPABASE_PUBLISHABLE_KEY", False),
    ("FRONTEND_ORIGIN", False),
)

# Exit codes (mirrors scripts/db/verify_rls.py).
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


class HealthResult(NamedTuple):
    """Outcome of the health-endpoint probe."""

    url: str
    ok: bool
    status_code: int | None
    latency_ms: float
    detail: str


def check_health(base_url: str, timeout: float) -> HealthResult:
    """Probe ``{base_url}/health`` and validate the success shape.

    Returns a :class:`HealthResult`; a transport error, a non-200 status, a
    non-JSON body, or an unexpected JSON shape are all reported as failures.
    """
    url = base_url.rstrip("/") + HEALTH_PATH
    start = time.perf_counter()
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return HealthResult(url, False, None, latency_ms, f"request failed: {exc}")

    latency_ms = (time.perf_counter() - start) * 1000.0

    if response.status_code != 200:
        return HealthResult(
            url,
            False,
            response.status_code,
            latency_ms,
            f"unexpected HTTP status {response.status_code}",
        )

    try:
        payload = response.json()
    except ValueError:
        return HealthResult(url, False, response.status_code, latency_ms, "body was not valid JSON")

    # The documented success shape is a JSON object whose ``status`` is "ok"
    # (``HealthResponse`` in backend/app/api/routes/health.py).
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return HealthResult(
            url,
            False,
            response.status_code,
            latency_ms,
            f"unexpected response shape: {payload!r}",
        )

    db = payload.get("db", "unknown")
    return HealthResult(url, True, response.status_code, latency_ms, f"status=ok, db={db}")


def check_env_vars() -> list[tuple[str, bool, bool]]:
    """Return ``(name, is_secret, is_set)`` for every required variable.

    Values are inspected for presence/non-emptiness only; they are never
    returned, so secrets cannot leak into logs.
    """
    results = []
    for name, is_secret in REQUIRED_ENV_VARS:
        value = os.getenv(name)
        results.append((name, is_secret, bool(value and value.strip())))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_deployment.py",
        description=(
            "Verify a deployed Kairos API is live (GET {base-url}/health) and "
            "that the required deployment environment variables are set. "
            "Exits non-zero when any check fails."
        ),
    )
    parser.add_argument(
        "--base-url",
        dest="base_url",
        help=(
            "deployed API base serving the health route, e.g. "
            "https://kairos.example.com/api/v1 (the /health path is appended)"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds for the health request (default: 10)",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.base_url:
        print(
            "ERROR: --base-url is required (the deployed API base, e.g. "
            "https://kairos.example.com/api/v1).",
            file=sys.stderr,
        )
        return EXIT_USAGE

    # .env is loaded lazily so importing this module never touches the
    # filesystem or the environment.  In CI the variables come from the
    # workflow ``env:`` block instead, so a missing .env is not an error.
    load_dotenv()

    width = 66
    print("=" * width)
    print("Kairos deployment verification")
    print("=" * width)
    print(f"Base URL : {args.base_url}")
    print(f"Health   : GET {args.base_url.rstrip('/') + HEALTH_PATH}")
    print("-" * width)

    passed = 0
    total = 0

    # 1. Liveness / readiness probe.
    total += 1
    health = check_health(args.base_url, args.timeout)
    if health.ok:
        passed += 1
        print(f"[PASS] health endpoint: HTTP 200 in {health.latency_ms:.0f} ms ({health.detail})")
    else:
        status = health.status_code if health.status_code is not None else "no response"
        print(f"[FAIL] health endpoint: {status} after {health.latency_ms:.0f} ms ({health.detail})")

    # 2. Required deployment environment variables.
    for name, is_secret, is_set in check_env_vars():
        total += 1
        suffix = " (secret; value not shown)" if is_secret else ""
        if is_set:
            passed += 1
            print(f"[PASS] {name} is set{suffix}")
        else:
            print(f"[FAIL] {name} is not set or empty{suffix}")

    failed = total - passed
    print("-" * width)
    print(f"Summary: {passed}/{total} checks passed, {failed} failed")

    if failed == 0:
        print("RESULT: PASS")
        return EXIT_OK

    print("RESULT: FAIL")
    return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
