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
import openai

from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.schemas.search import SearchResponse, SearchResult

router = APIRouter(dependencies=[Depends(require_user)])

# OpenAI client for embeddings (requires OPENAI_API_KEY env var)
openai.api_key = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _get_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for search query.
    Uses OpenAI text-embedding-3-small (1536 dimensions).
    """
    if not openai.api_key:
        raise HTTPException(
            status_code=503,
            detail="Vector search unavailable: OPENAI_API_KEY not configured"
        )
    
    try:
        response = openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embedding: {str(e)}"
        )


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
    mode: str = Query(default="hybrid", regex="^(hybrid|keyword|semantic)$"),
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
    workspace_id = user.get('workspace_id')
    if not workspace_id:
        raise HTTPException(status_code=403, detail="User workspace not found")
    
    offset = (page - 1) * page_size
    
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Set RLS context (belt-and-suspenders with explicit WHERE clauses)
            cur.execute("SET LOCAL app.current_workspace_id = %s", (workspace_id,))
            
            if mode == "keyword":
                results = _keyword_search(cur, q, workspace_id, page_size, offset)
                
            elif mode == "semantic":
                query_embedding = _get_embedding(q)
                results = _semantic_search(cur, query_embedding, workspace_id, page_size, offset)
                
            else:  # hybrid
                query_embedding = _get_embedding(q)
                results = _hybrid_search(cur, q, query_embedding, workspace_id, page_size, offset)
            
            # Count total (for pagination)
            count_sql = """
                SELECT COUNT(*) FROM dataset d
                WHERE d.workspace_id = %(workspace_id)s
                  AND (
                      lower(d.name) ILIKE lower(%(pattern)s) OR
                      lower(d.schema_name) ILIKE lower(%(pattern)s) OR
                      lower(d.description) ILIKE lower(%(pattern)s)
                  )
            """
            cur.execute(count_sql, {
                'workspace_id': workspace_id,
                'pattern': f"%{q}%"
            })
            total = cur.fetchone()['count']
            
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
                mode=mode
            )
