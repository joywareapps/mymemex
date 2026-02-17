"""ChromaDB vector store for semantic search."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import structlog

try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from ..config import DatabaseConfig

log = structlog.get_logger()


class VectorStore:
    """ChromaDB wrapper for document embeddings."""

    def __init__(self, config: DatabaseConfig):
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb not installed. Run: pip install chromadb")

        self.persist_dir = Path(config.path).parent / "chromadb"
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # ChromaDB 0.6+ uses PersistentClient (auto-persists)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

        log.info(
            "Vector store initialized",
            persist_dir=str(self.persist_dir),
            count=self.collection.count(),
        )

    def add(
        self,
        chunk_id: int,
        document_id: int,
        text: str,
        embedding: list[float],
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Add a chunk embedding to the vector store.

        Returns:
            Vector ID (UUID)
        """
        vector_id = str(uuid.uuid4())

        meta = metadata or {}
        meta.update({
            "chunk_id": chunk_id,
            "document_id": document_id,
        })

        self.collection.add(
            ids=[vector_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta],
        )

        return vector_id

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search for similar chunks.

        Returns:
            List of results with chunk_id, document_id, text, distance.
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, vector_id in enumerate(results["ids"][0]):
                formatted.append({
                    "vector_id": vector_id,
                    "chunk_id": results["metadatas"][0][i]["chunk_id"],
                    "document_id": results["metadatas"][0][i]["document_id"],
                    "text": results["documents"][0][i],
                    "distance": results["distances"][0][i],
                })

        return formatted

    def delete_by_document(self, document_id: int) -> None:
        """Delete all vectors for a document."""
        results = self.collection.get(where={"document_id": document_id})

        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            log.info(
                "Deleted document vectors",
                document_id=document_id,
                count=len(results["ids"]),
            )

    def count(self) -> int:
        """Get total number of vectors."""
        return self.collection.count()
