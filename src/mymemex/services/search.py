"""Search orchestration across keyword, semantic, and hybrid modes."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import AppConfig
from ..storage.repositories import ChunkRepository, DocumentRepository, TagRepository
from .exceptions import ServiceError, ServiceUnavailableError

log = structlog.get_logger()


class SearchService:
    """Search orchestration across keyword, semantic, and hybrid modes."""

    def __init__(self, session: AsyncSession, config: AppConfig):
        self.session = session
        self.config = config
        self.chunk_repo = ChunkRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.tag_repo = TagRepository(session)

    async def keyword_search(
        self, query: str, page: int = 1, per_page: int = 20, sort: str = "date"
    ) -> tuple[list[dict], int]:
        """Full-text keyword search using SQLite FTS5.

        sort: "date" (newest document first, default) or "relevance".
        """
        rows, total = await self.chunk_repo.fulltext_search(
            query, page=page, per_page=per_page, sort=sort
        )
        results = await self._enrich_keyword_results(rows)
        return results, total

    async def semantic_search(
        self, query: str, limit: int = 10, sort: str = "date"
    ) -> list[dict]:
        """Semantic search using vector embeddings.

        sort: "date" (newest document first, default) or "relevance".
        """
        if not self.config.ai.semantic_search_enabled:
            raise ServiceUnavailableError("Semantic search disabled in configuration")

        from ..intelligence.embedder import Embedder
        from ..storage.vector_store import CHROMADB_AVAILABLE, VectorStore

        if not CHROMADB_AVAILABLE:
            raise ServiceUnavailableError("ChromaDB not installed")

        embedder = Embedder(
            api_base=self.config.llm.api_base,
            embedding_model=self.config.ai.embedding_model,
            provider=self.config.llm.provider,
        )
        if not await embedder.is_available():
            raise ServiceUnavailableError(
                "Embedding model not available (Ollama unreachable)"
            )

        query_embedding = await embedder.embed(query)
        if query_embedding is None:
            raise ServiceError("Failed to generate query embedding")

        vector_store = VectorStore(self.config.database)
        vector_results = vector_store.search(
            query_embedding=query_embedding, n_results=limit
        )

        results = await self._enrich_semantic_results(vector_results)
        return self._apply_sort(results, sort)

    async def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        keyword_weight: float = 0.3,
        sort: str = "date",
    ) -> dict:
        """Hybrid search combining keyword + semantic with RRF merge.

        Falls back to keyword-only when semantic search is unavailable.

        sort: "date" (newest document first, default) or "relevance". Relevance
        always decides *which* results make the cut; sort only orders them.
        """
        keyword_results = await self._keyword_search_raw(query, limit * 2)

        semantic_results: list[dict] = []
        if self.config.ai.semantic_search_enabled:
            try:
                from ..intelligence.embedder import Embedder
                from ..storage.vector_store import CHROMADB_AVAILABLE, VectorStore

                if CHROMADB_AVAILABLE:
                    embedder = Embedder(
                        api_base=self.config.llm.api_base,
                        embedding_model=self.config.ai.embedding_model,
                        provider=self.config.llm.provider,
                    )
                    if await embedder.is_available():
                        query_embedding = await embedder.embed(query)
                        if query_embedding:
                            vector_store = VectorStore(self.config.database)
                            semantic_results = vector_store.search(
                                query_embedding=query_embedding,
                                n_results=limit * 2,
                            )
            except Exception:
                pass  # Graceful degradation

        merged = self._reciprocal_rank_fusion(
            keyword_results, semantic_results, keyword_weight
        )
        enriched = await self._enrich_hybrid_results(merged[:limit])

        return {
            "results": self._apply_sort(enriched, sort),
            "keyword_count": len(keyword_results),
            "semantic_count": len(semantic_results),
        }

    # --- Private helpers ---

    async def _keyword_search_raw(self, query: str, limit: int) -> list[dict]:
        """Run keyword search returning raw results for RRF merging.

        Always relevance-ordered: RRF fuses by *rank*, so feeding it a
        date-ordered list would corrupt the fused scores.
        """
        rows, _ = await self.chunk_repo.fulltext_search(
            query, page=1, per_page=limit, sort="relevance"
        )
        return rows

    # Weakest-to-strongest fallbacks for "the date of this document".
    _DATE_FIELDS = (
        ("document_date", "document"),
        ("created_date", "created"),
        ("file_modified_at", "modified"),
        ("ingested_at", "ingested"),
    )

    @classmethod
    def _doc_dates(cls, doc) -> tuple[str | None, str | None, str | None]:
        """Return (document_date, effective_date, date_source) as ISO strings."""
        if doc is None:
            return None, None, None

        document_date = getattr(doc, "document_date", None)
        for field, source in cls._DATE_FIELDS:
            value = getattr(doc, field, None)
            if value:
                return (
                    document_date.isoformat() if document_date else None,
                    value.isoformat(),
                    source,
                )
        return None, None, None

    @staticmethod
    def _apply_sort(results: list[dict], sort: str) -> list[dict]:
        """Order already-scored results for display.

        Relevance order is whatever the caller produced, so it is left alone.
        Undated results sort last rather than jumping to the top.
        """
        if sort == "relevance":
            return results
        return sorted(
            results,
            key=lambda r: (r.get("effective_date") is not None, r.get("effective_date") or ""),
            reverse=True,
        )

    @staticmethod
    def _reciprocal_rank_fusion(
        keyword_results: list[dict],
        semantic_results: list[dict],
        keyword_weight: float,
        k: int = 60,
    ) -> list[dict]:
        """Merge results using Reciprocal Rank Fusion (RRF).

        RRF score = weight / (k + rank)
        """
        scores: dict[int, dict] = {}

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

        return sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    async def _enrich_keyword_results(self, rows: list[dict]) -> list[dict]:
        """Enrich keyword search results with document info and tags."""
        results = []
        doc_cache: dict[int, object] = {}

        for row in rows:
            doc_id = row["document_id"]
            if doc_id not in doc_cache:
                doc_cache[doc_id] = await self.doc_repo.get_by_id(doc_id)

            doc = doc_cache[doc_id]
            if not doc:
                continue

            tags = await self.tag_repo.get_document_tags(doc_id)
            document_date, effective_date, date_source = self._doc_dates(doc)
            results.append({
                "document_id": doc_id,
                "title": doc.title,
                "original_filename": doc.original_filename,
                "file_path": doc.original_path,
                "page_number": row["page_number"],
                "chunk_index": row["chunk_index"],
                "snippet": row["snippet"],
                "text": row["text"],
                "rank": row["rank"],
                "tags": tags,
                "category": doc.category,
                "document_date": document_date,
                "effective_date": effective_date,
                "date_source": date_source,
            })

        return results

    async def _enrich_semantic_results(self, vector_results: list[dict]) -> list[dict]:
        """Enrich semantic search results with document info and tags."""
        results = []
        doc_cache: dict[int, object] = {}

        for vr in vector_results:
            doc_id = vr["document_id"]
            if doc_id not in doc_cache:
                doc_cache[doc_id] = await self.doc_repo.get_by_id(doc_id)

            doc = doc_cache.get(doc_id)
            tags = await self.tag_repo.get_document_tags(doc_id) if doc else []
            document_date, effective_date, date_source = self._doc_dates(doc)

            results.append({
                "document_id": doc_id,
                "chunk_id": vr["chunk_id"],
                "title": doc.title if doc else None,
                "original_filename": doc.original_filename if doc else None,
                "text": vr["text"],
                "distance": vr["distance"],
                "tags": tags,
                "document_date": document_date,
                "effective_date": effective_date,
                "date_source": date_source,
            })

        return results

    async def _enrich_hybrid_results(self, merged: list[dict]) -> list[dict]:
        """Enrich merged hybrid results with document info and tags."""
        results = []
        doc_cache: dict[int, object] = {}

        for item in merged:
            doc_id = item.get("document_id")
            if doc_id and doc_id not in doc_cache:
                doc_cache[doc_id] = await self.doc_repo.get_by_id(doc_id)

            doc = doc_cache.get(doc_id) if doc_id else None
            tags = await self.tag_repo.get_document_tags(doc_id) if doc_id else []
            document_date, effective_date, date_source = self._doc_dates(doc)

            results.append({
                "document_id": doc_id or 0,
                "chunk_id": item["chunk_id"],
                "title": doc.title if doc else None,
                "original_filename": doc.original_filename if doc else None,
                "text": item.get("text"),
                "score": item["score"],
                "tags": tags,
                "document_date": document_date,
                "effective_date": effective_date,
                "date_source": date_source,
            })

        return results
