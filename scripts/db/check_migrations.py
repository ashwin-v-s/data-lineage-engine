#!/usr/bin/env python
"""Operator/CI CLI: static migration-consistency check for the Kairos schema.

This script needs **no database**.  It parses the numbered SQL files in
``backend/migrations`` and cross-checks what they declare against the
hard-coded table list in ``scripts/db/verify_rls.py``, so drift between the two
is caught before a release gate ever touches a live project.

It reports, at minimum:

1. the ordered list of migration files and the tables/objects each defines;
2. any table a migration creates that is **missing** from ``verify_rls.py``'s
   RLS-verified table list (the exact class of gap that let
   ``0006_github_connections.sql`` slip past the previous hard-coded check),
   and the reverse: any table in the verified list that no migration creates;
3. whether a migration that adds a workspace-scoped table (one carrying a
   ``workspace_id`` column) also ENABLEs row-level security, FORCEs it, and
   defines a policy for that table.

Migrations whose header marks them "PROPOSAL ONLY / NOT APPLIED" are still
reported and are still subject to check (3).  They are *not* automatically
exempt from check (2): the whole point of this check is to catch a table that a
migration defines but the verify list forgot (the class of gap that let
``0006_github_connections.sql`` slip past).  The single deliberate exception is
recorded in :data:`VERIFY_LIST_EXCLUSIONS` (``import_run``), and it is printed
as a ``[NOTE]`` rather than a ``[FAIL]``.

Exit codes mirror ``scripts/db/verify_rls.py``:

    0  schema is consistent (no gap)
    1  a gap was found
    2  setup/parse error (missing file, unreadable/invalid ``verify_rls.py``)

Usage
-----
    python scripts/db/check_migrations.py
    python scripts/db/check_migrations.py --migrations backend/migrations

The module has no import-time side effects; all work happens in ``main``.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

# Exit codes (mirrors scripts/db/verify_rls.py).
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

# Repository root: this file lives at <root>/scripts/db/check_migrations.py.
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIGRATIONS_DIR = ROOT / "backend" / "migrations"
VERIFY_RLS_PATH = ROOT / "scripts" / "db" / "verify_rls.py"

# Workspace-scoped tables that a migration creates but that are *deliberately*
# absent from verify_rls.py's WORKSPACE_SCOPED_TABLES list, mapped to the
# reason.  Every other workspace-scoped table missing from that list is a gap.
# Keep this in step with the matching comment in scripts/db/verify_rls.py and
# the runbook in backend/migrations/README.md.
VERIFY_LIST_EXCLUSIONS = {
    "import_run": (
        "0004_ingestion_import_runs.sql is PROPOSAL ONLY / NOT APPLIED; the live "
        "gate would report it missing on the shared project"
    ),
}


# ---------------------------------------------------------------------------
# Static SQL parsing helpers (no database, no sqlglot dependency).
# ---------------------------------------------------------------------------

_CREATE_TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r'((?:"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)(?:\.(?:"[^"]+"|[A-Za-z_][A-Za-z0-9_]*))?)',
    re.IGNORECASE,
)
_ALTER_ENABLE_RLS_RE = re.compile(
    r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?([\w.\"]+)"
    r"\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)
_ALTER_FORCE_RLS_RE = re.compile(
    r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?([\w.\"]+)"
    r"\s+FORCE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)
_CREATE_POLICY_RE = re.compile(
    r"\bCREATE\s+POLICY\s+(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*)\s+ON\s+([\w.\"]+)",
    re.IGNORECASE,
)
_ADD_WORKSPACE_COLUMN_RE = re.compile(
    r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?([\w.\"]+)"
    r"\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?workspace_id\b",
    re.IGNORECASE,
)
_FOREACH_ARRAY_RE = re.compile(
    r"FOREACH\s+\w+\s+IN\s+ARRAY\s+ARRAY\s*\[([^\]]*)\]",
    re.IGNORECASE | re.DOTALL,
)

_OBJECT_RES = (
    ("function", re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([\w.\"]+)\s*\(", re.IGNORECASE)),
    ("role", re.compile(r"\bCREATE\s+ROLE\s+([\w\"]+)", re.IGNORECASE)),
    ("extension", re.compile(r"\bCREATE\s+EXTENSION\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.\"-]+)", re.IGNORECASE)),
    ("trigger", re.compile(r"\bCREATE\s+TRIGGER\s+([\w\"]+)", re.IGNORECASE)),
    ("index", re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\"]+)", re.IGNORECASE)),
)


def _strip_sql_comments(sql: str) -> str:
    """Drop ``--`` line comments and ``/* ... */`` block comments."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _norm_ident(raw: str) -> str:
    """Lower-case a possibly schema-qualified, possibly quoted identifier."""
    raw = raw.strip()
    if "." in raw:
        raw = raw.split(".")[-1]
    raw = raw.strip().strip('"').strip("'")
    return raw.lower()


def _find_matching_paren(text: str, open_idx: int) -> int:
    """Return the index of the ``)`` matching the ``(`` at ``open_idx``.

    Respects single-quoted string literals (with ``''`` escaping) and
    double-quoted identifiers so parens inside them are ignored.  Returns -1
    when no match is found.
    """
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            i += 1
            while i < n:
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":
                        i += 2
                        continue
                    break
                i += 1
        elif ch == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _create_table_body(sql: str, search_from: int):
    """Return the column-definition body of a CREATE TABLE starting the search
    at ``search_from``, or ``None`` when it cannot be delimited."""
    open_idx = sql.find("(", search_from)
    if open_idx == -1:
        return None
    close_idx = _find_matching_paren(sql, open_idx)
    if close_idx == -1:
        return None
    return sql[open_idx + 1 : close_idx]


def _is_proposal(raw_text: str) -> bool:
    """True when the migration header marks it as not applied to the shared DB."""
    upper = raw_text.upper()
    return "NOT APPLIED" in upper or "PROPOSAL ONLY" in upper


class Migration:
    """A parsed migration file and the schema objects it declares."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.raw = path.read_text(encoding="utf-8")
        self.applied = not _is_proposal(self.raw)
        sql = _strip_sql_comments(self.raw)

        self.created_tables: list[str] = []  # ordered, normalized
        self.other_objects: list[str] = []  # ordered, de-duplicated
        self.workspace_scoped: set[str] = set()
        self.rls_enabled: set[str] = set()
        self.rls_forced: set[str] = set()
        self.policy_tables: set[str] = set()

        self._parse_create_tables(sql)
        self._parse_rls(sql)
        self._parse_workspace_columns(sql)
        self._parse_do_loop(sql)
        self._parse_other_objects(sql)

    # -- parsing steps ------------------------------------------------------
    def _parse_create_tables(self, sql: str) -> None:
        for m in _CREATE_TABLE_RE.finditer(sql):
            name = _norm_ident(m.group(1))
            if name not in self.created_tables:
                self.created_tables.append(name)
            body = _create_table_body(sql, m.end())
            if body and re.search(r"\bworkspace_id\b", body, re.IGNORECASE):
                self.workspace_scoped.add(name)

    def _parse_rls(self, sql: str) -> None:
        for m in _ALTER_ENABLE_RLS_RE.finditer(sql):
            if "%" in m.group(1):
                continue
            self.rls_enabled.add(_norm_ident(m.group(1)))
        for m in _ALTER_FORCE_RLS_RE.finditer(sql):
            if "%" in m.group(1):
                continue
            self.rls_forced.add(_norm_ident(m.group(1)))
        for m in _CREATE_POLICY_RE.finditer(sql):
            if "%" in m.group(1):
                continue
            self.policy_tables.add(_norm_ident(m.group(1)))

    def _parse_workspace_columns(self, sql: str) -> None:
        for m in _ADD_WORKSPACE_COLUMN_RE.finditer(sql):
            if "%" in m.group(1):
                continue
            self.workspace_scoped.add(_norm_ident(m.group(1)))

    def _parse_do_loop(self, sql: str) -> None:
        """Handle 0003's ``DO`` block, which applies RLS to a table list that is
        only spelled out inside a ``FOREACH ... IN ARRAY ARRAY[...]`` literal
        and applied through ``EXECUTE format(... 'public.%I' ...)``."""
        for m in _FOREACH_ARRAY_RE.finditer(sql):
            tables = [_norm_ident(t) for t in re.findall(r"'([^']+)'", m.group(1))]
            if not tables:
                continue
            self.workspace_scoped.update(tables)
            if re.search(r"ENABLE\s+ROW\s+LEVEL\s+SECURITY", sql, re.IGNORECASE):
                self.rls_enabled.update(tables)
            if re.search(r"FORCE\s+ROW\s+LEVEL\s+SECURITY", sql, re.IGNORECASE):
                self.rls_forced.update(tables)
            if re.search(r"CREATE\s+POLICY", sql, re.IGNORECASE):
                self.policy_tables.update(tables)

    def _parse_other_objects(self, sql: str) -> None:
        for kind, pattern in _OBJECT_RES:
            for m in pattern.finditer(sql):
                token = m.group(1)
                if "%" in token:
                    continue
                label = f"{kind} {_norm_ident(token)}" if kind != "extension" else f"extension {token.strip(chr(34))}"
                if label not in self.other_objects:
                    self.other_objects.append(label)


def load_verified_tables(path: Path) -> list[str]:
    """Statically read ``WORKSPACE_SCOPED_TABLES`` from verify_rls.py.

    Parsed with :mod:`ast` so importing the database module (and its
    ``psycopg2``/``dotenv`` dependencies) is never required.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "WORKSPACE_SCOPED_TABLES":
                    if isinstance(node.value, (ast.Tuple, ast.List)):
                        return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    raise ValueError(
        f"{path} does not define a WORKSPACE_SCOPED_TABLES tuple/list literal"
    )


# ---------------------------------------------------------------------------
# Report + checks.
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_migrations.py",
        description=(
            "Statically verify that the Kairos migrations stay consistent with "
            "scripts/db/verify_rls.py.  Requires no database.  Exits non-zero "
            "when a gap is found."
        ),
    )
    parser.add_argument(
        "--migrations",
        default=str(DEFAULT_MIGRATIONS_DIR),
        help="directory holding the numbered migration .sql files "
        "(default: backend/migrations)",
    )
    parser.add_argument(
        "--verify-rls",
        default=str(VERIFY_RLS_PATH),
        help="path to verify_rls.py whose table list is cross-checked "
        "(default: scripts/db/verify_rls.py)",
    )
    return parser


def _gather_migrations(migrations_dir: Path) -> list[Migration]:
    files = sorted(
        (p for p in migrations_dir.glob("*.sql") if p.is_file()),
        key=lambda p: p.name,
    )
    return [Migration(p) for p in files]


def _print_per_migration_report(migrations: list[Migration], width: int) -> None:
    print("-" * width)
    print("Per-migration report (ordered by file name)")
    print("-" * width)
    for mig in migrations:
        status = "applied" if mig.applied else "PROPOSAL ONLY / NOT APPLIED"
        print(f"[{mig.name}]  status: {status}")
        if mig.created_tables:
            print(f"  creates tables ({len(mig.created_tables)}): "
                  + ", ".join(mig.created_tables))
        else:
            print("  creates tables (0): -")
        if mig.workspace_scoped:
            print(f"  workspace-scoped tables ({len(mig.workspace_scoped)}): "
                  + ", ".join(sorted(mig.workspace_scoped)))
        print(f"  RLS: enable={len(mig.rls_enabled)} "
              f"force={len(mig.rls_forced)} "
              f"policy={len(mig.policy_tables)}")
        if mig.other_objects:
            print("  other objects: " + ", ".join(mig.other_objects))
        print("")


def run_checks(migrations: list[Migration], verified: list[str]):
    """Return ``(coverage_gaps, rls_gaps, notes)`` lists of human-readable items.

    ``coverage_gaps`` are verify-list drift (hard failures); ``rls_gaps`` are
    workspace-scoped tables a migration did not enable+force+policy; ``notes``
    are informational only (they never fail the run).
    """
    verified_set = set(verified)

    all_creators: dict[str, list[str]] = {}
    for mig in migrations:
        for table in mig.created_tables:
            all_creators.setdefault(table, []).append(mig.name)

    # Which migration(s) mark each table workspace-scoped (add its workspace_id).
    scoping: dict[str, list[Migration]] = {}
    for mig in migrations:
        for table in mig.workspace_scoped:
            scoping.setdefault(table, []).append(mig)

    coverage_gaps: list[str] = []
    notes: list[str] = []

    # Check 2a: any workspace-scoped table a migration creates must appear in the
    # verify list.  This is the class of gap that let 0006 slip past the
    # previously hand-maintained list, so it is a hard failure; only the tables
    # recorded in VERIFY_LIST_EXCLUSIONS are reported as notes instead.
    for table in sorted(scoping):
        if table in verified_set:
            continue
        if table in VERIFY_LIST_EXCLUSIONS:
            notes.append(
                f"table '{table}' is intentionally excluded from the verified "
                f"list ({VERIFY_LIST_EXCLUSIONS[table]})"
            )
            continue
        scoped_by = ", ".join(m.name for m in scoping[table])
        coverage_gaps.append(
            f"table '{table}' is workspace-scoped by {scoped_by} but is NOT in "
            f"verify_rls.py's WORKSPACE_SCOPED_TABLES list"
        )

    # Informational: tables created by a migration that carry no workspace_id
    # (so they are correctly absent from the workspace-scoped verified list).
    for table in sorted(all_creators):
        if table in scoping or table in verified_set:
            continue
        notes.append(
            f"table '{table}' is created by {', '.join(all_creators[table])} but "
            f"has no workspace_id, so it is not workspace-scoped and is not "
            f"required in the verified list"
        )

    # Check 2b (reverse): a verified table that no migration creates.
    for table in sorted(verified_set):
        if table not in all_creators:
            coverage_gaps.append(
                f"verify_rls.py verifies '{table}' but no migration creates it"
            )

    # Check 3: every workspace-scoped table a migration adds must be RLS-enabled,
    # RLS-forced and have a policy in that same migration.
    rls_gaps: list[str] = []
    for mig in migrations:
        for table in sorted(mig.workspace_scoped):
            missing = []
            if table not in mig.rls_enabled:
                missing.append("ENABLE ROW LEVEL SECURITY")
            if table not in mig.rls_forced:
                missing.append("FORCE ROW LEVEL SECURITY")
            if table not in mig.policy_tables:
                missing.append("CREATE POLICY")
            if missing:
                rls_gaps.append(
                    f"[{mig.name}] workspace-scoped table '{table}' is missing: "
                    + "; ".join(missing)
                )

    return coverage_gaps, rls_gaps, notes


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    migrations_dir = Path(args.migrations)
    verify_rls_path = Path(args.verify_rls)

    if not migrations_dir.is_dir():
        print(f"ERROR: migrations directory not found: {migrations_dir}", file=sys.stderr)
        return EXIT_USAGE
    if not verify_rls_path.is_file():
        print(f"ERROR: verify_rls.py not found: {verify_rls_path}", file=sys.stderr)
        return EXIT_USAGE

    try:
        migrations = _gather_migrations(migrations_dir)
    except OSError as exc:
        print(f"ERROR: could not read migrations: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if not migrations:
        print(f"ERROR: no .sql migrations found in {migrations_dir}", file=sys.stderr)
        return EXIT_USAGE

    try:
        verified = load_verified_tables(verify_rls_path)
    except (SyntaxError, ValueError, OSError) as exc:
        print(f"ERROR: could not read the verified table list: {exc}", file=sys.stderr)
        return EXIT_USAGE

    width = 66
    print("=" * width)
    print("Kairos static migration-consistency check")
    print("=" * width)
    print(f"Migrations directory : {migrations_dir}")
    print(f"verify_rls.py        : {verify_rls_path}")
    print(f"Migrations found     : {len(migrations)}")
    print(f"Verified table list  : {len(verified)} tables")
    print("")

    _print_per_migration_report(migrations, width)

    coverage_gaps, rls_gaps, notes = run_checks(migrations, verified)

    print("-" * width)
    print("Check 2: verify_rls.py coverage")
    print("-" * width)
    if coverage_gaps:
        for gap in coverage_gaps:
            print(f"[FAIL] {gap}")
    else:
        print("[PASS] every table created by the migrations is accounted for "
              "(verified list matches)")
    for note in notes:
        print(f"[NOTE] {note}")
    print("")

    print("-" * width)
    print("Check 3: workspace-scoped tables have ENABLE + FORCE RLS and a policy")
    print("-" * width)
    if rls_gaps:
        for gap in rls_gaps:
            print(f"[FAIL] {gap}")
    else:
        print("[PASS] every workspace-scoped table is RLS-enabled, RLS-forced, "
              "and has a policy in its migration")
    print("")

    failed = len(coverage_gaps) + len(rls_gaps)
    print("-" * width)
    print(f"Summary: {failed} gap(s) found, {len(notes)} note(s)")
    if failed == 0:
        print("RESULT: PASS")
        return EXIT_OK

    print("RESULT: FAIL")
    return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
