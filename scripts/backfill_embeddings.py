#!/usr/bin/env python
"""Populate `dataset.embedding` for semantic search (pgvector).

The hybrid search endpoint (``GET /api/v1/search/hybrid?mode=semantic``) uses
``text-embedding-3-small`` (1536 dimensions) and degrades to keyword search when
the column is empty. This script is the only supported way to fill the column.

Reads each dataset that has no embedding yet, builds a short, honest document
from stored metadata (qualified name, description, tags) and writes the vector.
It never invents a description: the document contains the same fields the UI
shows.

Usage:
    python scripts/backfill_embeddings.py --dry-run
    python scripts/backfill_embeddings.py --limit 200
    python scripts/backfill_embeddings.py            # all rows

Environment:
    DATABASE_URL                      required
    OPENAI_API_KEY                    required unless --dry-run
    KAIROS_EMBEDDING_MODEL            optional, defaults to text-embedding-3-small

Exit codes:
    0  every eligible row was embedded (or the dry run succeeded)
    2  DATABASE_URL or OPENAI_API_KEY is missing
    3  the pgvector column is not present (apply migration 0012 first)
    4  an embedding request failed
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Iterable

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover - driver is a hard runtime dependency
    print("ERROR: psycopg2 is required (pip install -e .)", file=sys.stderr)
    raise SystemExit(2)

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

MODEL = os.getenv("KAIROS_EMBEDDING_MODEL", "text-embedding-3-small")
DIMENSIONS = 1536
BATCH_SIZE = 32

SELECT_SQL = """
    SELECT id::text AS id,
           database_name,
           schema_name,
           name,
           description
      FROM public.dataset
     WHERE embedding IS NULL
     ORDER BY created_at NULLS LAST, id
     LIMIT %(limit)s
"""

UPDATE_SQL = """
    UPDATE public.dataset
       SET embedding = %(embedding)s::vector
     WHERE id = %(id)s::uuid
"""

COLUMN_EXISTS_SQL = """
    SELECT 1
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'dataset'
       AND column_name = 'embedding'
"""


def document_for(row: dict) -> str:
    """Build the embedded text from stored fields only."""
    parts = [
        f"{row.get('database_name') or ''}.{row.get('schema_name') or ''}.{row.get('name') or ''}".strip(".")
    ]
    description = (row.get("description") or "").strip()
    if description:
        parts.append(description)
    return "\n".join(part for part in parts if part)


def chunks(items: list, size: int) -> Iterable[list]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def embed(texts: list[str]) -> list[list[float]]:
    try:
        import openai
    except ImportError:
        print(
            "ERROR: the openai package is not installed (pip install -e .)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.embeddings.create(model=MODEL, input=texts)
    return [item.embedding for item in response.data]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show what would be embedded")
    parser.add_argument("--limit", type=int, default=1000, help="maximum rows to process")
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv(".env")
    dsn = (os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        print("ERROR: DATABASE_URL is required", file=sys.stderr)
        return 2
    if not args.dry_run and not (os.getenv("OPENAI_API_KEY") or "").strip():
        print("ERROR: OPENAI_API_KEY is required to generate embeddings", file=sys.stderr)
        return 2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(COLUMN_EXISTS_SQL)
            if cur.fetchone() is None:
                print(
                    "ERROR: public.dataset.embedding does not exist. Apply "
                    "backend/migrations/0012_m3_pgvector_embeddings.sql first.",
                    file=sys.stderr,
                )
                return 3
            cur.execute(SELECT_SQL, {"limit": args.limit})
            rows = cur.fetchall()

        print(f"Datasets without an embedding: {len(rows)} (limit {args.limit})")
        if not rows:
            return 0
        if args.dry_run:
            for row in rows[:10]:
                print(f"  would embed: {document_for(row)[:120]}")
            if len(rows) > 10:
                print(f"  … {len(rows) - 10} more")
            return 0

        written = 0
        for group in chunks(rows, BATCH_SIZE):
            texts = [document_for(row) for row in group]
            try:
                vectors = embed(texts)
            except Exception as exc:  # network, auth, quota — all fatal here
                print(f"ERROR: embedding request failed: {exc}", file=sys.stderr)
                return 4
            with conn.cursor() as cur:
                for row, vector in zip(group, vectors):
                    if len(vector) != DIMENSIONS:
                        print(
                            f"ERROR: model returned {len(vector)} dimensions, expected {DIMENSIONS}",
                            file=sys.stderr,
                        )
                        return 4
                    cur.execute(
                        UPDATE_SQL,
                        {"id": row["id"], "embedding": "[" + ",".join(f"{v:.8f}" for v in vector) + "]"},
                    )
                    written += 1
            conn.commit()
            time.sleep(0.2)
        print(f"Embedded {written} dataset(s) with {MODEL}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
