"""Classification service."""

from __future__ import annotations

import structlog

from ..config import AppConfig
from ..intelligence.classifier import ClassificationResult, DocumentClassifier
from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentRepository, TagRepository, UserRepository
from .user import UserContextBuilder

log = structlog.get_logger()


class ClassificationService:
    """Service for document classification and auto-tagging."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.classifier = DocumentClassifier(config)

    async def classify_document(self, document_id: int) -> ClassificationResult | None:
        """
        Classify a document and apply auto-tags.

        Args:
            document_id: Document to classify

        Returns:
            ClassificationResult or None if classification failed
        """
        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)
            tag_repo = TagRepository(session)

            doc = await doc_repo.get_by_id(document_id)
            if not doc:
                log.warning("Document not found", document_id=document_id)
                return None

            # Get content (first few chunks)
            chunks = await chunk_repo.get_by_document(document_id, limit=3)
            if not chunks:
                log.warning("No chunks found", document_id=document_id)
                return None

            content = "\n\n".join(chunk.text for chunk in chunks)

            # Build user context for LLM
            user_repo = UserRepository(session)
            users = await user_repo.list()
            user_context_builder = UserContextBuilder(session)
            user_context = await user_context_builder.build_prompt_context()
            user_names = UserContextBuilder.get_user_names(users)

            # Classify
            result = await self.classifier.classify(
                content, user_context=user_context, user_names=user_names
            )
            if not result:
                log.warning("Classification returned no result", document_id=document_id)
                return None

            # Auto-add user tags based on known users (fallback text matching)
            person_tags = user_context_builder.get_person_tags(content, users)
            for ptag in person_tags:
                try:
                    await tag_repo.add_to_document(document_id, ptag, is_auto=True)
                except Exception:
                    pass

            # Apply tags
            tags_to_apply = self.classifier.filter_tags_by_confidence(result.tags)

            for tag_name in tags_to_apply:
                try:
                    await tag_repo.add_to_document(
                        document_id,
                        tag_name,
                        is_auto=True,
                    )
                    log.debug(
                        "Auto-tag applied",
                        document_id=document_id,
                        tag=tag_name,
                    )
                except Exception as e:
                    log.error(
                        "Failed to apply tag",
                        document_id=document_id,
                        tag=tag_name,
                        error=str(e),
                    )

            # Also tag with document type if above threshold
            threshold = self.config.classification.confidence_threshold
            if result.document_type and result.type_confidence >= threshold:
                try:
                    await tag_repo.add_to_document(
                        document_id,
                        result.document_type,
                        is_auto=True,
                    )
                except Exception:
                    pass

            # Update document summary, category, and frequency if provided
            if result.summary or result.document_type or result.document_frequency:
                updates = {}
                if result.summary:
                    updates["summary"] = result.summary
                if result.document_type and result.type_confidence >= threshold:
                    updates["category"] = result.document_type
                if result.document_frequency:
                    updates["document_frequency"] = result.document_frequency
                if updates:
                    await doc_repo.update(doc, **updates)

            return result

    async def reclassify_all(self) -> int:
        """
        Re-classify all ready documents.

        Returns count of documents reclassified.
        """
        async with get_session() as session:
            doc_repo = DocumentRepository(session)

            docs, total = await doc_repo.list_documents(
                status="processed", per_page=10000
            )
            count = 0

            for doc in docs:
                try:
                    result = await self.classify_document(doc.id)
                    if result:
                        count += 1
                except Exception as e:
                    log.error(
                        "Reclassification failed",
                        document_id=doc.id,
                        error=str(e),
                    )

            log.info("Reclassification complete", count=count, total=total)
            return count
