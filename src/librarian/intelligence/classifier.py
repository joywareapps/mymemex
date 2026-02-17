"""Document classification using LLM."""

from __future__ import annotations

from typing import Any

import structlog

from ..config import AppConfig, LLMConfig
from .llm_client import LLMClient, create_llm_client

log = structlog.get_logger()

DEFAULT_CLASSIFICATION_PROMPT = """Analyze this document and classify it.

Document content:
{content}

Instructions:
1. Identify the document type (e.g., invoice, tax_return, receipt, contract, medical_record, insurance_policy, bank_statement, utility_bill, other)
2. Extract relevant tags (e.g., financial, legal, medical, personal, work, insurance, tax)
3. Assign confidence scores (0.0-1.0)

Return JSON:
{{
  "document_type": "type_here",
  "type_confidence": 0.95,
  "tags": [
    {{"name": "tag1", "confidence": 0.9}},
    {{"name": "tag2", "confidence": 0.8}}
  ],
  "summary": "Brief 1-2 sentence description"
}}
"""


class ClassificationResult:
    """Result of document classification."""

    def __init__(
        self,
        document_type: str,
        type_confidence: float,
        tags: list[dict[str, Any]],
        summary: str,
    ):
        self.document_type = document_type
        self.type_confidence = type_confidence
        self.tags = tags
        self.summary = summary

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassificationResult:
        """Create from LLM response dict."""
        return cls(
            document_type=data.get("document_type", "other"),
            type_confidence=data.get("type_confidence", 0.0),
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
        )


class DocumentClassifier:
    """Classify documents using LLM."""

    def __init__(self, config: AppConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.classification_config = config.classification
        self.llm = llm_client or self._create_client()

    def _create_client(self) -> LLMClient:
        """Create LLM client from config."""
        llm_config = LLMConfig(
            provider=self.config.llm.provider,
            model=self.classification_config.model or self.config.llm.model,
            api_base=self.config.llm.api_base,
        )
        return create_llm_client(llm_config)

    async def classify(self, content: str) -> ClassificationResult | None:
        """
        Classify document content.

        Args:
            content: Document text (first N chunks or summary)

        Returns:
            ClassificationResult or None if classification fails
        """
        if not self.classification_config.enabled:
            log.debug("Classification disabled")
            return None

        if not self.config.llm.provider or self.config.llm.provider == "none":
            log.debug("No LLM provider configured")
            return None

        try:
            prompt_template = (
                self.classification_config.prompt_template
                or DEFAULT_CLASSIFICATION_PROMPT
            )
            prompt = prompt_template.format(content=content[:3000])

            response = await self.llm.generate_json(prompt)

            result = ClassificationResult.from_dict(response)

            log.info(
                "Document classified",
                type=result.document_type,
                confidence=result.type_confidence,
                tags=len(result.tags),
            )

            return result

        except Exception as e:
            log.error("Classification failed", error=str(e))
            return None

    def filter_tags_by_confidence(
        self,
        tags: list[dict[str, Any]],
    ) -> list[str]:
        """
        Filter tags by confidence threshold.

        Returns list of tag names that meet the threshold.
        """
        threshold = self.classification_config.confidence_threshold
        max_tags = self.classification_config.max_tags

        filtered = [
            tag["name"]
            for tag in tags
            if tag.get("confidence", 0) >= threshold
        ]

        return filtered[:max_tags]
