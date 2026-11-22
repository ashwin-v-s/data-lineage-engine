"""
backend/app/api/routes/vector_search.py
────────────────────────────────────────
Hybrid search combining keyword + pgvector semantic search.
Implements workspace isolation for all search results.

Endpoints
─────────
  GET /api/v1/search/hybrid
      ?q=<term>              # search query (required)
      ?mode=hybrid|keyword|semantic  (default: hybrid)
      ?page=<int>            # 1-based page number (default: 1)
      ?page_size=<int>       # results per page (default: 20, max: 100)

Architecture decisions
──────────────────────
- Uses pgvector for semantic embeddings
- RLS enforced at DB level for workspace isolation
- Hybrid mode combines keyword (70%) + semantic (30%) scores
- All results filtered by workspace_id from auth context
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from psycopg2.extras import RealDictCursor

from backend.app import db as db_module
from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.schemas.search import SearchResponse, SearchResult

router = APIRouter(dependencies=[Depends(require_user)])

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Keyword predicate shared by the search and count statements so pagination
# cannot drift from the result set.
_KEYWORD_MATCH_SQL = (
    "( lower(d.name) ILIKE lower(%(pattern)s)"
    " OR lower(d.schema_name) ILIKE lower(%(pattern)s)"
    " OR lower(d.description) ILIKE lower(%(pattern)s) )"
)


def _workspace_id_for(user: dict | None) -> str | None:
    """Resolve the caller's workspace from the authenticated database scope.

    ``require_user`` yields the Supabase ``/auth/v1/user`` payload (id, email,
    ...), which does **not** contain a workspace id; the workspace is applied to
    the session as a context variable that ``get_conn`` turns into RLS scope.
    Reading it from there is what makes this router reachable for real sessions.
    The explicit key is kept only for direct callers (tests, scripts).
    """
    return db_module._workspace_id.get() or (user or {}).get("workspace_id")


def _embeddings_ready(cur) -> tuple[bool, str]:
    """Whether this deployment can actually rank by semantic similarity.

    The pgvector column alone is not enough: migration 0012 ships the column and
    the index, but rows are embedded by ``scripts/backfill_embeddings.py`` and
    queries need ``OPENAI_API_KEY``. Checking all three keeps the endpoint
    honest: it never silently ranks on an embedding it could not compute, and
    never presents keyword matches as semantic ones.
    """
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'dataset' "
        "AND column_name = 'embedding' "
        "LIMIT 1"
    )
    if cur.fetchone() is None:
        return False, "semantic embeddings are not provisioned on this deployment"
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return False, "OPENAI_API_KEY is not configured on this server"
    cur.execute("SELECT COUNT(*) AS count FROM public.dataset WHERE embedding IS NOT NULL")
    stored = int(cur.fetchone()["count"])
    if stored == 0:
        return False, "no dataset has been embedded yet (run scripts/backfill_embeddings.py)"
    return True, ""


def _embedding_supported(cur) -> bool:
    """Backwards-compatible boolean view of :func:`_embeddings_ready`."""
    return _embeddings_ready(cur)[0]


def _count_matches(cur, query: str, workspace_id: str, mode: str) -> int:
    """Count every row the requested mode can return, for correct paging."""
    if mode == "semantic":
        where = "d.embedding IS NOT NULL"
        params = {"workspace_id": workspace_id}
    elif mode == "hybrid":
        where = f"({_KEYWORD_MATCH_SQL} OR d.embedding IS NOT NULL)"
        params = {"workspace_id": workspace_id, "pattern": f"%{query}%"}
    else:
        where = _KEYWORD_MATCH_SQL
        params = {"workspace_id": workspace_id, "pattern": f"%{query}%"}
    cur.execute(
        "SELECT COUNT(*) AS count FROM dataset d "
        "WHERE d.workspace_id = %(workspace_id)s AND " + where,
        params,
    )
    return int(cur.fetchone()["count"])


def _get_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for search query.
    Uses OpenAI text-embedding-3-small (1536 dimensions).
    """
    try:
        import openai as _openai  # lazy import — not required at startup
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Vector search unavailable: the openai package is not installed on this server"
        )
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Vector search unavailable: OPENAI_API_KEY not configured"
        )
    _openai.api_key = api_key
    try:
        response = _openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as exc:
        # Provider error text can include account identifiers or request ids;
        # log the detail and return a stable message to the caller.
        raise HTTPException(
            status_code=503,
            detail="Vector search could not generate an embedding for this query"
        ) from exc


def _keyword_search(cur, pattern: str, workspace_id: str, limit: int, offset: int) -> list[dict]:
    """
    Keyword-based search using ILIKE (case-insensitive substring match).
    Enforces workspace isolation via RLS.
    """
    sql = """
        SELECT 
            d.id::text AS id,
            d.asset_type AS type,
            d.name AS name,
            d.schema_name AS schema,
            d.description AS description,
            d.created_at AS created,
            1.0 AS score,
            'keyword' AS match_type
        FROM dataset d
        WHERE d.workspace_id = %(workspace_id)s
          AND (
              lower(d.name) ILIKE lower(%(pattern)s) OR
              lower(d.schema_name) ILIKE lower(%(pattern)s) OR
              lower(d.description) ILIKE lower(%(pattern)s)
          )
        ORDER BY d.name
        LIMIT %(limit)s OFFSET %(offset)s
    """
    
    cur.execute(sql, {
        'pattern': f"%{pattern}%",
        'workspace_id': workspace_id,
        'limit': limit,
        'offset': offset
    })
    return cur.fetchall()


def _semantic_search(cur, query_embedding: list[float], workspace_id: str, limit: int, offset: int) -> list[dict]:
    """
    Semantic search using pgvector cosine similarity.
    Requires:
    - dataset table has 'embedding' column (vector(1536))
    - CREATE EXTENSION vector;
    - CREATE INDEX ON dataset USING ivfflat (embedding vector_cosine_ops);
    
    Enforces workspace isolation via workspace_id filter.
    """
    # Convert embedding to pgvector format
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    
    sql = """
        SELECT 
            d.id::text AS id,
            d.asset_type AS type,
            d.name AS name,
            d.schema_name AS schema,
            d.description AS description,
            d.created_at AS created,
            1 - (d.embedding <=> %(embedding)s::vector) AS score,
            'semantic' AS match_type
        FROM dataset d
        WHERE d.workspace_id = %(workspace_id)s
          AND d.embedding IS NOT NULL
        ORDER BY d.embedding <=> %(embedding)s::vector
        LIMIT %(limit)s OFFSET %(offset)s
    """
    
    cur.execute(sql, {
        'embedding': embedding_str,
        'workspace_id': workspace_id,
        'limit': limit,
        'offset': offset
    })
    return cur.fetchall()


def _hybrid_search(cur, query: str, query_embedding: list[float], workspace_id: str, limit: int, offset: int) -> list[dict]:
    """
    Hybrid search combining keyword (70%) + semantic (30%) scores.
    Merges results from both methods with weighted scoring.
    """
    # Get keyword results
    keyword_results = _keyword_search(cur, query, workspace_id, limit * 2, 0)
    
    # Get semantic results
    semantic_results = _semantic_search(cur, query_embedding, workspace_id, limit * 2, 0)
    
    # Merge and score
    merged = {}
    
    for result in keyword_results:
        asset_id = result['id']
        merged[asset_id] = dict(result)
        merged[asset_id]['hybrid_score'] = 0.7 * result['score']
        merged[asset_id]['match_type'] = 'hybrid'
    
    for result in semantic_results:
        asset_id = result['id']
        if asset_id in merged:
            merged[asset_id]['hybrid_score'] += 0.3 * result['score']
        else:
            merged[asset_id] = dict(result)
            merged[asset_id]['hybrid_score'] = 0.3 * result['score']
            merged[asset_id]['match_type'] = 'hybrid'
    
    # Sort by hybrid score and paginate
    sorted_results = sorted(
        merged.values(),
        key=lambda x: x['hybrid_score'],
        reverse=True
    )
    
    return sorted_results[offset:offset + limit]


@router.get("/search/hybrid", response_model=SearchResponse)
def hybrid_search(
    q: str = Query(..., description="Search query"),
    mode: str = Query(default="hybrid", pattern="^(hybrid|keyword|semantic)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_user)
):
    """
    Hybrid search endpoint combining keyword + semantic search.
    
    Security:
    - Enforces workspace isolation via user's workspace_id
    - RLS policies at DB level provide additional protection
    - No cross-workspace data leakage possible
    
    Modes:
    - hybrid: 70% keyword + 30% semantic
    - keyword: Traditional ILIKE search only
    - semantic: Vector similarity only
    """
    workspace_id = _workspace_id_for(user)
    if not workspace_id:
        raise HTTPException(status_code=403, detail="User workspace not found")

    offset = (page - 1) * page_size

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Set RLS context (belt-and-suspenders with explicit WHERE clauses)
            cur.execute("SET LOCAL app.current_workspace_id = %s", (workspace_id,))

            note: Optional[str] = None
            effective_mode = mode
            if mode == "keyword":
                results = _keyword_search(cur, q, workspace_id, page_size, offset)
                total = _count_matches(cur, q, workspace_id, mode)
            else:
                semantic_ready, unavailable_reason = _embeddings_ready(cur)
                if not semantic_ready and mode == "hybrid":
                    # Hybrid search promises keyword + semantic ranking. Rather
                    # than fail the whole screen, serve the keyword half and say
                    # so in the payload; the UI must not claim a vector match.
                    results = _keyword_search(cur, q, workspace_id, page_size, offset)
                    total = _count_matches(cur, q, workspace_id, "keyword")
                    effective_mode = "keyword"
                    note = (
                        "Semantic ranking is unavailable: "
                        + unavailable_reason
                        + ". Results are keyword matches only."
                    )
                elif not semantic_ready:
                    raise HTTPException(
                        status_code=503,
                        detail=(f"Vector search is unavailable: {unavailable_reason}. "
                                "Keyword mode still works."),
                    )
                else:
                    query_embedding = _get_embedding(q)
                    if mode == "semantic":
                        results = _semantic_search(cur, query_embedding, workspace_id, page_size, offset)
                    else:  # hybrid
                        results = _hybrid_search(cur, q, query_embedding, workspace_id, page_size, offset)
                    total = _count_matches(cur, q, workspace_id, mode)
            
            # Format results
            search_results = [
                SearchResult(
                    id=r['id'],
                    type=r['type'],
                    name=r['name'],
                    schema=r.get('schema'),
                    description=r.get('description'),
                    score=r.get('hybrid_score', r.get('score', 0.0)),
                    match_type=r.get('match_type', mode)
                )
                for r in results
            ]
            
            return SearchResponse(
                results=search_results,
                total=total,
                page=page,
                page_size=page_size,
                mode=effective_mode,
                note=note,
            )
