#!/usr/bin/env python
"""Fail when a live UI view calls an endpoint the API contract does not expose.

The product claims that its screens show persisted workspace records. That claim
is only honest if the request behind each screen exists. This checker reads the
React live views (``frontend/src``), extracts the ``/api/v1/...`` paths they
request, normalises template interpolations to ``{param}``, and compares them
with ``docs/openapi.json``.

Exit codes:
    0  every literal path a live view requests is documented
    1  at least one path is not in the contract (drift or a typo)
    2  the contract or the view directory is missing

Run: python scripts/check_ui_claims.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENAPI = ROOT / "docs" / "openapi.json"
SRC = ROOT / "frontend" / "src"
API_PREFIX = "/api/v1"

# `fetch('/api/v1/catalog')` is absolute; `request('/catalog')` is relative to
# the helper's `/api/v1` base. Both forms, with or without template
# interpolations, are captured here.
ABSOLUTE_CALL = re.compile(
    r"""fetch\s*\(\s*(?:`|'|")(/api/v1/[^`'"\s]*)""", re.MULTILINE
)
RELATIVE_CALL = re.compile(
    r"""request\s*\(\s*(?:`|'|")(/[^`'"\s]*)""", re.MULTILINE
)
INTERPOLATION = re.compile(r"\$\{[^}]*\}")


def contract_paths() -> set[str]:
    data = json.loads(OPENAPI.read_text(encoding="utf-8"))
    return {
        path[len(API_PREFIX):] if path.startswith(API_PREFIX) else path
        for path in data.get("paths", {})
    }


def normalise(raw: str) -> str:
    """Return a comparable path with every interpolation reduced to `{}`."""
    without_query = raw.split("?", 1)[0]
    without_prefix = (
        without_query[len(API_PREFIX):]
        if without_query.startswith(API_PREFIX)
        else without_query
    )
    collapsed = INTERPOLATION.sub("{}", without_prefix)
    return collapsed.rstrip("/") or "/"


def segments(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def matches(candidate: str, documented: str) -> bool:
    """True when `candidate` addresses the same endpoint as `documented`.

    `{}` in the candidate matches a documented path parameter; a trailing `{}`
    also matches a literal trailing action segment, because several views build
    `/<record>/${action}` with a runtime action name.
    """
    cand, doc = segments(candidate), segments(documented)
    for index, part in enumerate(cand):
        if index >= len(doc):
            return False
        if part == "{}":
            continue
        if doc[index] == part:
            continue
        if doc[index].startswith("{") and not part.startswith("{"):
            continue
        if index == len(cand) - 1 and part == "{}":
            continue
        return False
    return len(cand) >= len(doc) - 1


def discover() -> dict[Path, set[str]]:
    found: dict[Path, set[str]] = {}
    for file in sorted(SRC.rglob("*")):
        if file.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
            continue
        if "__tests__" in file.parts or ".test." in file.name:
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        paths = {normalise(m) for m in ABSOLUTE_CALL.findall(text)}
        paths |= {normalise(m) for m in RELATIVE_CALL.findall(text)}
        # Documentation snippets such as `/api/v1/*` are not real requests.
        paths = {path for path in paths if path.startswith("/") and "*" not in path}
        if paths:
            found[file] = paths
    return found


def main() -> int:
    if not OPENAPI.exists():
        print(f"ERROR: contract not found at {OPENAPI}", file=sys.stderr)
        return 2
    if not SRC.exists():
        print(f"ERROR: live views not found at {SRC}", file=sys.stderr)
        return 2
    documented = contract_paths()
    discovered = discover()
    if not discovered:
        print("ERROR: no /api/v1 requests found in frontend/src", file=sys.stderr)
        return 2

    problems: list[str] = []
    checked = 0
    for file, paths in discovered.items():
        relative = file.relative_to(ROOT).as_posix()
        for path in sorted(paths):
            checked += 1
            if any(matches(path, doc) for doc in documented):
                continue
            problems.append(f"{relative}: {API_PREFIX}{path}")

    print(f"Checked {checked} UI request paths across {len(discovered)} files.")
    if problems:
        print("Undocumented UI endpoints:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "Either the view is calling an endpoint the API does not expose, or "
            "docs/openapi.json is stale. Neither is acceptable for a screen that "
            "claims to show persisted records.",
            file=sys.stderr,
        )
        return 1
    print("RESULT: PASS - every live-view request maps to a documented endpoint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
