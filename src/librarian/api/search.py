"""Search API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..services import ServiceError, ServiceUnavailableError
from ..services.search import SearchService
from ..storage.database import get_session

router = APIRouter()


# --- Schemas ---


class KeywordSearchResult(BaseModel):
    document_id: int
    title: str | None
    original_filename: str
    file_path: str
    page_number: int | None
    chunk_index: int
    snippet: str
    text: str
    rank: float
    tags: list[str] = []
    category: str | None = None


class KeywordSearchResponse(BaseModel):
    results: list[KeywordSearchResult]
    total: int
    page: int
    per_page: int
    query: str
    search_mode: str = "keyword"


class SemanticSearchResult(BaseModel):
    document_id: int
    chunk_id: int
    title: str | None = None
    original_filename: str | None = None
    text: str
    distance: float
    tags: list[str] = []


class SemanticSearchResponse(BaseModel):
    results: list[SemanticSearchResult]
    total: int
    query: str
    search_mode: str = "semantic"


class HybridSearchResult(BaseModel):
    document_id: int
    chunk_id: int
    title: str | None = None
    original_filename: str | None = None
    text: str | None = None
    score: float
    tags: list[str] = []


class HybridSearchResponse(BaseModel):
    results: list[HybridSearchResult]
    total: int
    query: str
    keyword_count: int
    semantic_count: int
    search_mode: str = "hybrid"


# --- Endpoints ---


@router.get("/keyword", response_model=KeywordSearchResponse)
async def keyword_search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Full-text keyword search using SQLite FTS5.

    Works without LLM — always available.
    Supports standard FTS5 query syntax:
    - Simple terms: "insurance policy"
    - Phrase: '"car insurance"'
    - Boolean: "insurance AND NOT health"
    - Prefix: "insur*"
    """
    async with get_session() as session:
        service = SearchService(session, request.app.state.config)
        results, total = await service.keyword_search(q, page, per_page)

        return KeywordSearchResponse(
            results=[KeywordSearchResult(**r) for r in results],
            total=total,
            page=page,
            per_page=per_page,
            query=q,
        )


@router.get("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100),
):
    """
    Semantic search using vector embeddings.

    Requires Ollama running with an embedding model.
    Returns chunks ranked by semantic similarity to query.
    """
    async with get_session() as session:
        service = SearchService(session, request.app.state.config)
        try:
            results = await service.semantic_search(q, limit)
        except ServiceUnavailableError as e:
            raise HTTPException(503, str(e))
        except ServiceError as e:
            raise HTTPException(500, str(e))

        return SemanticSearchResponse(
            results=[SemanticSearchResult(**r) for r in results],
            total=len(results),
            query=q,
        )


@router.get("/hybrid", response_model=HybridSearchResponse)
async def hybrid_search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    keyword_weight: float = Query(0.3, ge=0.0, le=1.0),
):
    """
    Hybrid search: combines FTS5 keyword + semantic vector search.

    Uses Reciprocal Rank Fusion to merge results.
    Falls back to keyword-only when semantic search is unavailable.
    """
    async with get_session() as session:
        service = SearchService(session, request.app.state.config)
        data = await service.hybrid_search(q, limit, keyword_weight)

        return HybridSearchResponse(
            results=[HybridSearchResult(**r) for r in data["results"]],
            total=len(data["results"]),
            query=q,
            keyword_count=data["keyword_count"],
            semantic_count=data["semantic_count"],
        )
