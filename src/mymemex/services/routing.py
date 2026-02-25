"""Tag-based file routing service."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.queue import TaskQueue, TaskStatus, TaskType
from ..storage.database import get_session
from ..storage.models import Document, RoutingRule, Task
from ..storage.repositories import (
    DocumentRepository,
    FileOperationLogRepository,
    RoutingRuleRepository,
    TagRepository,
    WatchDirectoryRepository,
)
from .file_policy import FilePolicyService, _resolve_conflict, _safe_filename

log = structlog.get_logger()

_TAG_PREFIX_RE = re.compile(r"\{tag:([^}]+)\}")


def _resolve_tag_prefix(template: str, doc_tags: list[str]) -> str:
    """Replace {tag:prefix} placeholders with the value of the matching tag."""
    def replacer(m: re.Match) -> str:
        prefix = m.group(1)
        for tag in doc_tags:
            if tag.startswith(f"{prefix}:"):
                return _safe_filename(tag[len(prefix) + 1:])
        return prefix  # fallback: prefix itself
    return _TAG_PREFIX_RE.sub(replacer, template)


def render_routing_template(template: str, doc: Document, doc_tags: list[str]) -> str:
    """Render a routing sub-level template string with document-derived values."""
    template = _resolve_tag_prefix(template, doc_tags)
    ref_date = doc.document_date
    if ref_date is None:
        ref_date = datetime.utcnow().date()
    # document_date may be a date or datetime object
    if hasattr(ref_date, "date"):
        ref_date = ref_date.date()
    values = {
        "year": str(ref_date.year),
        "month": f"{ref_date.month:02d}",
        "day": f"{ref_date.day:02d}",
        "date": ref_date.isoformat(),
        "category": _safe_filename(doc.category or "other"),
        "title": _safe_filename(doc.title or doc.original_filename),
        "original_name": Path(doc.original_filename).stem,
        "ext": Path(doc.original_filename).suffix.lstrip("."),
        "hash": doc.content_hash[:8] if doc.content_hash else "00000000",
    }
    try:
        return _safe_filename(template.format(**values))
    except KeyError:
        return _safe_filename(template)


def _rule_matches(rule: RoutingRule, doc_tags: set[str]) -> bool:
    """Return True if the rule's tag criteria match the document's tags."""
    rule_tags = set(json.loads(rule.tags or "[]"))
    if not rule_tags:
        return False  # empty rule never matches
    if rule.match_mode == "all":
        return rule_tags.issubset(doc_tags)
    return bool(rule_tags & doc_tags)  # "any"


async def _has_pending_route_task(session: AsyncSession, document_id: int) -> bool:
    """Return True if there's already a pending ROUTE_FILE task for this document."""
    result = await session.execute(
        select(Task).where(
            Task.document_id == document_id,
            Task.task_type == TaskType.ROUTE_FILE.value,
            Task.status == TaskStatus.PENDING.value,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


class RoutingService:
    """Apply tag-based routing rules to move documents to the correct destination."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def route_document(self, document_id: int) -> bool:
        """
        Route a document to the correct destination based on its tags.

        Returns True if the file was moved, False otherwise (no match, already in place, etc.).
        """
        doc_repo = DocumentRepository(self.session)
        wd_repo = WatchDirectoryRepository(self.session)
        tag_repo = TagRepository(self.session)
        rule_repo = RoutingRuleRepository(self.session)
        log_repo = FileOperationLogRepository(self.session)

        doc = await doc_repo.get_by_id(document_id)
        if not doc:
            log.warning("route_document: document not found", document_id=document_id)
            return False

        # Determine the actual file location
        source_path_str = doc.current_path or doc.original_path
        source = Path(source_path_str)
        if not source.exists():
            log.warning(
                "route_document: file not found on disk",
                document_id=document_id,
                path=str(source),
            )
            return False

        # Find the watch directory
        dirs = await wd_repo.list_active()
        wd = None
        for d in dirs:
            if doc.original_path.startswith(d.path):
                wd = d
                break

        if not wd or not wd.archive_path:
            # No watch dir or no archive path — fall back to file policy
            if wd:
                policy_service = FilePolicyService(self.session)
                await policy_service.apply(doc, wd)
            return False

        # Load active rules and document tags
        rules = await rule_repo.list_for_watch_dir(wd.id)
        doc_tags = await tag_repo.get_document_tags(document_id)
        doc_tags_set = set(doc_tags)

        # Find first matching rule (rules already ordered by priority ASC)
        matched_rule = None
        for rule in rules:
            if _rule_matches(rule, doc_tags_set):
                matched_rule = rule
                break

        if matched_rule is None:
            # No rule matched — fall back to file policy
            policy_service = FilePolicyService(self.session)
            await policy_service.apply(doc, wd)
            return False

        # Build destination path
        archive_base = Path(wd.archive_path)
        dest_parts = [archive_base, matched_rule.directory_name]

        sub_levels = json.loads(matched_rule.sub_levels or "[]")
        for level_template in sub_levels:
            rendered = render_routing_template(level_template, doc, doc_tags)
            if rendered:
                dest_parts.append(rendered)

        dest_dir = Path(*dest_parts)
        natural_dest = dest_dir / doc.original_filename

        # Idempotency check: file is already at the natural destination
        if str(natural_dest) == source_path_str:
            return False

        dest = _resolve_conflict(natural_dest)

        # Move the file
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest))

            doc.current_path = str(dest)
            doc.file_policy_applied = "route_file"
            await self.session.commit()

            await log_repo.create(
                operation="route_file",
                source_path=str(source),
                destination_path=str(dest),
                status="success",
                document_id=doc.id,
            )
            log.info(
                "File routed",
                document_id=document_id,
                rule=matched_rule.name,
                src=str(source),
                dest=str(dest),
            )
            return True

        except Exception as e:
            log.error(
                "route_document: move failed",
                document_id=document_id,
                error=str(e),
            )
            await log_repo.create(
                operation="route_file",
                source_path=str(source),
                destination_path=str(dest),
                status="failed",
                document_id=doc.id,
                error_message=str(e),
            )
            return False
