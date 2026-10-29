"""Idempotently seed clearly-labelled demo assets from sample CSV files.

This is an operator-facing tool, deliberately not part of the product
ingestion API.  It loads the headers of the Olist sample CSVs
(``data/olist/`` by default) into a user's Kairos personal workspace so a
demo user sees real content in the UI.

For every CSV file it creates exactly one ``dataset`` asset (name = file
stem, ``asset_type`` = TABLE) and one ``column_record`` per header column,
leaving the column data type NULL (no type inference).  Only the first CSV
line is read; data rows are never parsed.

The tool is idempotent: it relies on the asset table's workspace-scoped
unique index together with ``ON CONFLICT DO NOTHING``, so repeated runs add
nothing.

By default it runs in dry-run mode and only prints the plan.  Pass
``--apply`` to actually write.
"""
from __future__ import annotations

import argparse
import csv
import sys
import uuid
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# Allow ``python scripts/seed_demo_catalog.py`` from the repository root by
# putting the repo root on sys.path before importing the backend package.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.db import (  # noqa: E402  (import after sys.path tweak)
    DATABASE_URL,
    get_conn,
    provision_personal_workspace,
    reset_workspace_id,
    set_workspace_id,
)

# Demo identity.  The `dataset` identity tuple is
# (source_system, namespace, database_name, schema_name, name, asset_type);
# the demo assets share fixed namespace/database/schema values and are
# labelled by their source_system tag.
DEMO_NAMESPACE = "olist_demo"
DEMO_DATABASE = "olist_demo"
DEMO_SCHEMA = "demo"
ASSET_TYPE = "TABLE"
SCHEMA_VERSION = "v1"

INSERT_DATASET_SQL = """
    INSERT INTO dataset
        (source_system, namespace, database_name, schema_name, name,
         asset_type, description, tags)
    VALUES
        (%(source_system)s, %(namespace)s, %(database_name)s, %(schema_name)s,
         %(name)s, %(asset_type)s, %(description)s, %(tags)s)
    ON CONFLICT DO NOTHING
    RETURNING id
"""

SELECT_DATASET_SQL = """
    SELECT id FROM dataset
    WHERE source_system = %(source_system)s
      AND namespace = %(namespace)s
      AND database_name = %(database_name)s
      AND schema_name = %(schema_name)s
      AND name = %(name)s
      AND asset_type = %(asset_type)s
    LIMIT 1
"""

INSERT_COLUMN_SQL = """
    INSERT INTO column_record (dataset_id, column_name, data_type, schema_version)
    VALUES (%s, %s, NULL, %s)
    ON CONFLICT DO NOTHING
"""


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Load sample CSV headers into the Kairos catalog as clearly-labelled "
            "demo assets.  Dry-run by default; pass --apply to write."
        ),
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="UUID of the owner whose personal workspace receives the demo assets.",
    )
    parser.add_argument(
        "--data-dir",
        default="data/olist",
        help="Directory containing the sample CSV files (default: data/olist).",
    )
    parser.add_argument(
        "--source-system",
        default="kairos_demo",
        help="source_system tag applied to every demo asset (default: kairos_demo).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of CSV files to process (default: no limit).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Actually write the demo assets to the database (default: dry-run).",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan only and never write (this is the default behaviour).",
    )
    return parser.parse_args(argv)


def read_csv_headers(path: Path) -> List[str]:
    """Return the header row of ``path``; only the first line is read.

    Blank header cells are dropped.  Data rows are never read or parsed.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        first_line = handle.readline()
    if not first_line.strip():
        return []
    try:
        headers = next(csv.reader([first_line]))
    except (csv.Error, StopIteration):
        return []
    return [header.strip() for header in headers if header.strip()]


def discover_csv_files(data_dir: Path, limit: Optional[int]) -> List[Path]:
    """Return a deterministic, optionally limited list of CSV files."""
    if not data_dir.is_dir():
        return []
    files = sorted(p for p in data_dir.glob("*.csv") if p.is_file())
    if limit is not None:
        files = files[: max(0, limit)]
    return files


def build_plan(files: Sequence[Path]) -> List[Tuple[Path, List[str]]]:
    """Return one ``(path, headers)`` entry per CSV file."""
    return [(path, read_csv_headers(path)) for path in files]


def print_plan(
    plan: Sequence[Tuple[Path, List[str]]],
    *,
    data_dir: Path,
    user_id: str,
    source_system: str,
    limit: Optional[int],
) -> int:
    print("DRY RUN - no database writes. Pass --apply to write.")
    print(f"Owner (--user-id): {user_id}")
    print(f"Data directory:    {data_dir}")
    print(f"Source system:     {source_system}")
    limit_label = "none" if limit is None else str(limit)
    print(f"CSV file limit:    {limit_label}")
    print()

    if not plan:
        print(f"No CSV files found in {data_dir}; nothing to seed.")
        return 0

    name_width = max(len(path.stem) for path, _ in plan)
    total_columns = 0
    for index, (path, headers) in enumerate(plan, start=1):
        total_columns += len(headers)
        print(f"  {index:>3}. {path.stem:<{name_width}}  columns: {len(headers)}")

    print()
    print(f"Total: {len(plan)} assets, {total_columns} columns (data types left NULL).")
    return 0


def apply_plan(
    plan: Sequence[Tuple[Path, List[str]]],
    *,
    user_id: str,
    source_system: str,
) -> int:
    if not DATABASE_URL:
        print(
            "ERROR: DATABASE_URL is not set. Add it to the repo .env file or the "
            "environment before running with --apply.",
            file=sys.stderr,
        )
        return 1

    workspace_id = provision_personal_workspace(user_id)
    print(f"Target workspace: {workspace_id}")

    token = set_workspace_id(workspace_id)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                for path, headers in plan:
                    params = {
                        "source_system": source_system,
                        "namespace": DEMO_NAMESPACE,
                        "database_name": DEMO_DATABASE,
                        "schema_name": DEMO_SCHEMA,
                        "name": path.stem,
                        "asset_type": ASSET_TYPE,
                        "description": f"Kairos demo asset seeded from {path.name}",
                        "tags": [source_system],
                    }
                    cur.execute(INSERT_DATASET_SQL, params)
                    row = cur.fetchone()
                    created = row is not None
                    if created:
                        dataset_id = row[0]
                    else:
                        cur.execute(SELECT_DATASET_SQL, params)
                        existing = cur.fetchone()
                        if existing is None:
                            raise RuntimeError(
                                f"Asset {path.stem!r} could not be created or found"
                            )
                        dataset_id = existing[0]

                    if headers:
                        cur.executemany(
                            INSERT_COLUMN_SQL,
                            [(dataset_id, name, SCHEMA_VERSION) for name in headers],
                        )

                    status = "created" if created else "already present"
                    print(
                        f"  {path.stem:<40} {status}; columns: {len(headers)}"
                    )
    finally:
        reset_workspace_id(token)

    print()
    print(f"Done: {len(plan)} demo assets processed.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        uuid.UUID(args.user_id)
    except (ValueError, AttributeError, TypeError):
        print(f"ERROR: --user-id must be a valid UUID, got {args.user_id!r}", file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir)
    files = discover_csv_files(data_dir, args.limit)
    plan = build_plan(files)

    if not args.apply:
        return print_plan(
            plan,
            data_dir=data_dir,
            user_id=args.user_id,
            source_system=args.source_system,
            limit=args.limit,
        )

    if not plan:
        print(f"No CSV files found in {data_dir}; nothing to seed.")
        return 0

    try:
        return apply_plan(plan, user_id=args.user_id, source_system=args.source_system)
    except Exception as exc:  # noqa: BLE001 - surface any database failure clearly
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
