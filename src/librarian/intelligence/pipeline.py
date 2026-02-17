"""Embedding generation pipeline."""

from __future__ import annotations

import structlog

from ..config import AppConfig
from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentRepository
from ..storage.vector_store import CHROMADB_AVAILABLE, VectorStore
from .embedder import Embedder

log = structlog.get_logger()


async def embed_pending_chunks(config: AppConfig) -> int:
    """
    Generate embeddings for chunks that don't have them yet.

    Returns:
        Number of chunks embedded.
    """
    if not config.ai.semantic_search_enabled:
        return 0

    if not CHROMADB_AVAILABLE:
        log.warning("ChromaDB not installed, skipping embeddings")
        return 0

    embedder = Embedder(config.llm)

    if not await embedder.is_available():
        log.debug("Embedder not available, skipping")
        return 0

    vector_store = VectorStore(config.database)
    embedded_count = 0

    async with get_session() as session:
        chunk_repo = ChunkRepository(session)

        chunks = await chunk_repo.get_chunks_without_embeddings(
            limit=config.ai.embedding_batch_size,
        )

        if not chunks:
            return 0

        log.info("Embedding chunks", count=len(chunks))

        for chunk in chunks:
            embedding = await embedder.embed(chunk.text)

            if embedding is None:
                log.warning("Failed to embed chunk", chunk_id=chunk.id)
                continue

            vector_id = vector_store.add(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                embedding=embedding,
                metadata={
                    "page_number": chunk.page_number or 0,
                    "extraction_method": chunk.extraction_method or "",
                },
            )

            await chunk_repo.update(
                chunk,
                has_embedding=True,
                vector_id=vector_id,
            )

            embedded_count += 1

        await session.commit()

    log.info("Embedding batch complete", total=embedded_count)
    return embedded_count
