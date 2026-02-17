"""Search API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentRepository, TagRepository

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
        chunk_repo = ChunkRepository(session)
        doc_repo = DocumentRepository(session)
        tag_repo = TagRepository(session)

        rows, total = await chunk_repo.fulltext_search(q, page=page, per_page=per_page)

        results = []
        doc_cache: dict[int, object] = {}

        for row in rows:
            doc_id = row["document_id"]
            if doc_id not in doc_cache:
                doc_cache[doc_id] = await doc_repo.get_by_id(doc_id)

            doc = doc_cache[doc_id]
            if not doc:
                continue

            tags = await tag_repo.get_document_tags(doc_id)

            results.append(
                KeywordSearchResult(
                    document_id=doc_id,
                    title=doc.title,
                    original_filename=doc.original_filename,
                    file_path=doc.original_path,
                    page_number=row["page_number"],
                    chunk_index=row["chunk_index"],
                    snippet=row["snippet"],
                    text=row["text"],
                    rank=row["rank"],
                    tags=tags,
                    category=doc.category,
                )
            )

        return KeywordSearchResponse(
            results=results,
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
    config = request.app.state.config

    if not config.ai.semantic_search_enabled:
        raise HTTPException(503, "Semantic search disabled in configuration")

    from ..intelligence.embedder import Embedder
    from ..storage.vector_store import CHROMADB_AVAILABLE, VectorStore

    if not CHROMADB_AVAILABLE:
        raise HTTPException(503, "ChromaDB not installed")

    embedder = Embedder(config.llm)

    if not await embedder.is_available():
        raise HTTPException(503, "Embedding model not available (Ollama unreachable)")

    query_embedding = await embedder.embed(q)
    if query_embedding is None:
        raise HTTPException(500, "Failed to generate query embedding")

    vector_store = VectorStore(config.database)
    vector_results = vector_store.search(
        query_embedding=query_embedding,
        n_results=limit,
    )

    # Enrich results with document info
    results = []
    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        tag_repo = TagRepository(session)
        doc_cache: dict[int, object] = {}

        for vr in vector_results:
            doc_id = vr["document_id"]
            if doc_id not in doc_cache:
                doc_cache[doc_id] = await doc_repo.get_by_id(doc_id)

            doc = doc_cache.get(doc_id)
            tags = await tag_repo.get_document_tags(doc_id) if doc else []

            results.append(
                SemanticSearchResult(
                    document_id=doc_id,
                    chunk_id=vr["chunk_id"],
                    title=doc.title if doc else None,
                    original_filename=doc.original_filename if doc else None,
                    text=vr["text"],
                    distance=vr["distance"],
                    tags=tags,
                )
            )

    return SemanticSearchResponse(
        results=results,
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
    config = request.app.state.config

    # Keyword results (always available)
    keyword_results = await _keyword_search_internal(q, limit * 2)

    # Semantic results (best-effort)
    semantic_results: list[dict] = []
    if config.ai.semantic_search_enabled:
        try:
            from ..intelligence.embedder import Embedder
            from ..storage.vector_store import CHROMADB_AVAILABLE, VectorStore

            if CHROMADB_AVAILABLE:
                embedder = Embedder(config.llm)
                if await embedder.is_available():
                    query_embedding = await embedder.embed(q)
                    if query_embedding:
                        vector_store = VectorStore(config.database)
                        semantic_results = vector_store.search(
                            query_embedding=query_embedding,
                            n_results=limit * 2,
                        )
        except Exception:
            pass  # Graceful degradation

    # Merge with RRF
    merged = _reciprocal_rank_fusion(keyword_results, semantic_results, keyword_weight)

    # Enrich top results with document info
    results = []
    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        tag_repo = TagRepository(session)
        chunk_repo = ChunkRepository(session)
        doc_cache: dict[int, object] = {}

        for item in merged[:limit]:
            chunk_id = item["chunk_id"]
            doc_id = item.get("document_id")
            text = item.get("text")

            # Try to get document info
            if doc_id and doc_id not in doc_cache:
                doc_cache[doc_id] = await doc_repo.get_by_id(doc_id)
            doc = doc_cache.get(doc_id) if doc_id else None
            tags = await tag_repo.get_document_tags(doc_id) if doc_id else []

            results.append(
                HybridSearchResult(
                    document_id=doc_id or 0,
                    chunk_id=chunk_id,
                    title=doc.title if doc else None,
                    original_filename=doc.original_filename if doc else None,
                    text=text,
                    score=item["score"],
                    tags=tags,
                )
            )

    return HybridSearchResponse(
        results=results,
        total=len(results),
        query=q,
        keyword_count=len(keyword_results),
        semantic_count=len(semantic_results),
    )


# --- Internal helpers ---


async def _keyword_search_internal(query: str, limit: int) -> list[dict]:
    """Run keyword search and return raw results for RRF merging."""
    async with get_session() as session:
        chunk_repo = ChunkRepository(session)
        rows, _ = await chunk_repo.fulltext_search(query, page=1, per_page=limit)
        return rows


def _reciprocal_rank_fusion(
    keyword_results: list[dict],
    semantic_results: list[dict],
    keyword_weight: float,
    k: int = 60,
) -> list[dict]:
    """
    Merge results using Reciprocal Rank Fusion (RRF).

    RRF score = weight / (k + rank)
    """
    scores: dict[int, dict] = {}

    # Score keyword results
    for rank, result in enumerate(keyword_results):
        chunk_id = result.get("chunk_id") or result.get("id")
        if chunk_id is None:
            continue
        score = keyword_weight / (k + rank + 1)
        if chunk_id not in scores:
            scores[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": result.get("document_id"),
                "text": result.get("text"),
                "score": 0.0,
            }
        scores[chunk_id]["score"] += score

    # Score semantic results
    semantic_weight = 1.0 - keyword_weight
    for rank, result in enumerate(semantic_results):
        chunk_id = result["chunk_id"]
        score = semantic_weight / (k + rank + 1)
        if chunk_id not in scores:
            scores[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": result.get("document_id"),
                "text": result.get("text"),
                "score": 0.0,
            }
        scores[chunk_id]["score"] += score

    # Sort by score descending
    return sorted(scores.values(), key=lambda x: x["score"], reverse=True)
