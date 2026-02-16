"""Search API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
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
        # Cache doc lookups
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
