"""Data access layer."""

from __future__ import annotations

from datetime import date, datetime

import structlog
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Backup,
    Chunk,
    Document,
    DocumentField,
    DocumentTag,
    FileOperationLog,
    FilePath,
    MCPToken,
    SystemLog,
    Tag,
    Task,
    User,
    WatchDirectory,
)

log = structlog.get_logger()


class DocumentRepository:
    """Data access for documents."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, doc_id: int) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def find_by_content_hash(self, content_hash: str) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def find_by_quick_hash(self, quick_hash: str) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.quick_hash == quick_hash)
        )
        return result.scalar_one_or_none()

    async def find_by_path(self, path: str) -> Document | None:
        result = await self.session.execute(
            select(Document)
            .join(FilePath, FilePath.document_id == Document.id)
            .where(FilePath.path == path)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        content_hash: str,
        quick_hash: str,
        file_size: int,
        original_path: str,
        original_filename: str,
        mime_type: str,
        file_modified_at: float | datetime,
    ) -> Document:
        if isinstance(file_modified_at, (int, float)):
            file_modified_at = datetime.fromtimestamp(file_modified_at)

        doc = Document(
            content_hash=content_hash,
            quick_hash=quick_hash,
            file_size=file_size,
            original_path=original_path,
            original_filename=original_filename,
            mime_type=mime_type,
            file_modified_at=file_modified_at,
            status="pending",
        )
        self.session.add(doc)

        # Also create primary file path
        fp = FilePath(
            document_id=0,  # Will be set after flush
            path=original_path,
            is_primary=True,
        )
        self.session.add(doc)
        await self.session.flush()

        fp.document_id = doc.id
        self.session.add(fp)
        await self.session.commit()

        return doc

    async def add_file_path(self, document_id: int, path: str) -> FilePath:
        # Check if path already exists
        existing = await self.session.execute(select(FilePath).where(FilePath.path == path))
        if existing.scalar_one_or_none():
            # Update last_seen
            await self.session.execute(
                update(FilePath)
                .where(FilePath.path == path)
                .values(last_seen_at=datetime.utcnow())
            )
            await self.session.commit()
            result = await self.session.execute(select(FilePath).where(FilePath.path == path))
            return result.scalar_one()

        fp = FilePath(
            document_id=document_id,
            path=path,
            is_primary=False,
        )
        self.session.add(fp)
        await self.session.commit()
        return fp

    async def update_status(
        self, doc: Document, status: str, error: str | None = None
    ) -> None:
        doc.status = status
        if error:
            doc.last_error = error
            doc.error_count = (doc.error_count or 0) + 1
        doc.updated_at = datetime.utcnow()
        await self.session.commit()

    async def update(self, doc: Document, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(doc, key, value)
        doc.updated_at = datetime.utcnow()
        await self.session.commit()

    async def list_documents(
        self,
        page: int = 1,
        per_page: int = 50,
        status: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        q: str | None = None,
        sort_by: str = "ingested_at",
        sort_order: str = "desc",
    ) -> tuple[list[Document], int]:
        """List documents with filtering and pagination."""
        query = select(Document)
        count_query = select(func.count(Document.id))

        if status:
            query = query.where(Document.status == status)
            count_query = count_query.where(Document.status == status)
        if category:
            query = query.where(Document.category == category)
            count_query = count_query.where(Document.category == category)
        if tag:
            query = query.join(DocumentTag).join(Tag).where(Tag.name == tag)
            count_query = count_query.join(DocumentTag).join(Tag).where(Tag.name == tag)
        if q:
            # FTS5 search to find matching document IDs
            fts_query = text(
                "SELECT DISTINCT document_id FROM chunks_fts WHERE chunks_fts MATCH :q"
            )
            fts_result = await self.session.execute(fts_query, {"q": q})
            doc_ids = [row[0] for row in fts_result.fetchall()]
            if doc_ids:
                query = query.where(Document.id.in_(doc_ids))
                count_query = count_query.where(Document.id.in_(doc_ids))
            else:
                return [], 0

        # Sorting
        sort_col = getattr(Document, sort_by, Document.ingested_at)
        if sort_order == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        # Count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        result = await self.session.execute(query)
        documents = list(result.scalars().all())

        return documents, total

    async def get_stats(self) -> dict:
        """Get document statistics."""
        total = await self.session.scalar(select(func.count(Document.id))) or 0
        by_status = {}
        result = await self.session.execute(
            select(Document.status, func.count(Document.id)).group_by(Document.status)
        )
        for row in result.fetchall():
            by_status[row[0]] = row[1]

        return {"total": total, "by_status": by_status}

    async def find_stuck_processing(self) -> list[Document]:
        """Find documents stuck in 'processing' with no active task."""
        active_task_doc_ids = (
            select(Task.document_id)
            .where(Task.document_id.isnot(None))
            .where(Task.status.in_(["pending", "running", "waiting_llm"]))
        )
        result = await self.session.execute(
            select(Document)
            .where(Document.status == "processing")
            .where(Document.id.notin_(active_task_doc_ids))
        )
        return list(result.scalars().all())

    async def delete(self, doc_id: int) -> bool:
        doc = await self.get_by_id(doc_id)
        if not doc:
            return False
        await self.session.delete(doc)
        await self.session.commit()
        return True


class ChunkRepository:
    """Data access for document chunks."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        document_id: int,
        chunk_index: int,
        text: str,
        char_count: int,
        page_number: int | None = None,
        extraction_method: str | None = None,
    ) -> Chunk:
        chunk = Chunk(
            document_id=document_id,
            chunk_index=chunk_index,
            page_number=page_number,
            text=text,
            char_count=char_count,
            extraction_method=extraction_method,
            has_embedding=False,
        )
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def get_by_document(self, document_id: int, limit: int | None = None) -> list[Chunk]:
        query = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def fulltext_search(
        self,
        query: str,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[dict], int]:
        """Full-text search using FTS5."""
        # Count total matches
        count_result = await self.session.execute(
            text("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH :q"),
            {"q": query},
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * per_page

        # Search with ranking
        result = await self.session.execute(
            text("""
                SELECT
                    c.id,
                    c.document_id,
                    c.chunk_index,
                    c.page_number,
                    c.text,
                    c.char_count,
                    snippet(chunks_fts, 0, '<mark>', '</mark>', '...', 32) as snippet,
                    rank
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.rowid
                WHERE chunks_fts MATCH :q
                ORDER BY rank
                LIMIT :limit OFFSET :offset
            """),
            {"q": query, "limit": per_page, "offset": offset},
        )

        rows = result.fetchall()
        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "page_number": row[3],
                "text": row[4],
                "char_count": row[5],
                "snippet": row[6],
                "rank": row[7],
            })

        return results, total

    async def get_chunks_without_embeddings(self, limit: int = 100) -> list[Chunk]:
        """Get chunks that don't have embeddings yet."""
        result = await self.session.execute(
            select(Chunk)
            .where(Chunk.has_embedding == False)  # noqa: E712
            .order_by(Chunk.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, chunk: Chunk, **kwargs) -> None:
        """Update chunk attributes."""
        for key, value in kwargs.items():
            setattr(chunk, key, value)
        await self.session.flush()

    async def get_total_count(self) -> int:
        result = await self.session.scalar(select(func.count(Chunk.id)))
        return result or 0


class TagRepository:
    """Data access for tags."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, name: str) -> Tag:
        result = await self.session.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if tag:
            return tag

        tag = Tag(name=name)
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def list_with_counts(self) -> list[dict]:
        result = await self.session.execute(
            select(Tag.id, Tag.name, Tag.color, func.count(DocumentTag.document_id).label("count"))
            .outerjoin(DocumentTag, DocumentTag.tag_id == Tag.id)
            .group_by(Tag.id)
            .order_by(Tag.name)
        )
        return [
            {"id": row[0], "name": row[1], "color": row[2], "document_count": row[3]}
            for row in result.fetchall()
        ]

    async def add_to_document(self, document_id: int, tag_name: str, is_auto: bool = False) -> Tag:
        tag = await self.get_or_create(tag_name)

        existing = await self.session.execute(
            select(DocumentTag).where(
                DocumentTag.document_id == document_id, DocumentTag.tag_id == tag.id
            )
        )
        if not existing.scalar_one_or_none():
            dt = DocumentTag(document_id=document_id, tag_id=tag.id, is_auto=is_auto)
            self.session.add(dt)
            await self.session.commit()

        return tag

    async def remove_from_document(self, document_id: int, tag_name: str) -> bool:
        result = await self.session.execute(select(Tag).where(Tag.name == tag_name))
        tag = result.scalar_one_or_none()
        if not tag:
            return False

        dt_result = await self.session.execute(
            select(DocumentTag).where(
                DocumentTag.document_id == document_id, DocumentTag.tag_id == tag.id
            )
        )
        dt = dt_result.scalar_one_or_none()
        if not dt:
            return False

        await self.session.delete(dt)
        await self.session.commit()
        return True

    async def get_document_tags(self, document_id: int) -> list[str]:
        result = await self.session.execute(
            select(Tag.name)
            .join(DocumentTag, DocumentTag.tag_id == Tag.id)
            .where(DocumentTag.document_id == document_id)
            .order_by(Tag.name)
        )
        return [row[0] for row in result.fetchall()]

    async def delete(self, tag_id: int) -> bool:
        result = await self.session.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()
        if not tag:
            return False
        await self.session.delete(tag)
        await self.session.commit()
        return True


class DocumentFieldRepository:
    """Data access for extracted document fields."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        document_id: int,
        field_name: str,
        field_type: str,
        value_text: str | None = None,
        value_number: float | None = None,
        value_date: str | None = None,
        currency: str | None = None,
        confidence: float = 1.0,
        source: str = "llm",
    ) -> DocumentField:
        """Create a new document field."""
        field = DocumentField(
            document_id=document_id,
            field_name=field_name,
            field_type=field_type,
            value_text=value_text,
            value_number=value_number,
            value_date=value_date,
            currency=currency,
            confidence=confidence,
            source=source,
        )
        self.session.add(field)
        await self.session.commit()
        await self.session.refresh(field)
        return field

    async def get_by_document(self, document_id: int) -> list[DocumentField]:
        """Get all fields for a document."""
        result = await self.session.execute(
            select(DocumentField).where(DocumentField.document_id == document_id)
        )
        return list(result.scalars().all())

    async def delete_for_document(self, document_id: int) -> int:
        """Delete all fields for a document (for re-extraction)."""
        result = await self.session.execute(
            delete(DocumentField).where(DocumentField.document_id == document_id)
        )
        await self.session.commit()
        return result.rowcount  # type: ignore[return-value]

    async def aggregate_amounts(
        self,
        field_name: str | None = None,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        currency: str | None = None,
        min_confidence: float = 0.5,
    ) -> dict:
        """Aggregate monetary amounts across documents."""
        query = (
            select(
                DocumentField.currency,
                func.sum(DocumentField.value_number).label("total"),
                func.count(DocumentField.id).label("count"),
            )
            .select_from(DocumentField)
            .join(Document)
            .where(DocumentField.field_type == "currency")
            .where(DocumentField.confidence >= min_confidence)
        )

        if field_name:
            query = query.where(DocumentField.field_name == field_name)
        if category:
            query = query.where(Document.category == category)
        if date_from:
            query = query.where(Document.document_date >= date_from)
        if date_to:
            query = query.where(Document.document_date <= date_to)
        if currency:
            query = query.where(DocumentField.currency == currency)

        query = query.group_by(DocumentField.currency)

        result = await self.session.execute(query)
        rows = result.all()

        return {
            "results": [
                {"currency": row.currency, "total": row.total, "count": row.count}
                for row in rows
            ]
        }

    async def get_yearly_breakdown(
        self,
        field_name: str | None = None,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        currency: str | None = None,
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """Get amounts grouped by year."""
        query = (
            select(
                func.strftime("%Y", Document.document_date).label("year"),
                DocumentField.currency,
                func.sum(DocumentField.value_number).label("total"),
                func.count(DocumentField.id).label("count"),
            )
            .select_from(DocumentField)
            .join(Document)
            .where(DocumentField.field_type == "currency")
            .where(DocumentField.confidence >= min_confidence)
            .where(Document.document_date.isnot(None))
        )

        if field_name:
            query = query.where(DocumentField.field_name == field_name)
        if category:
            query = query.where(Document.category == category)
        if date_from:
            query = query.where(Document.document_date >= date_from)
        if date_to:
            query = query.where(Document.document_date <= date_to)
        if currency:
            query = query.where(DocumentField.currency == currency)

        query = query.group_by("year", DocumentField.currency).order_by("year")

        result = await self.session.execute(query)
        return [
            {"year": int(row.year), "currency": row.currency, "total": row.total, "count": row.count}
            for row in result.all()
        ]

    async def list_document_types(self) -> list[dict]:
        """List all document categories with counts."""
        query = (
            select(
                Document.category,
                func.count(Document.id).label("count"),
            )
            .where(Document.category.isnot(None))
            .group_by(Document.category)
            .order_by(func.count(Document.id).desc())
        )

        result = await self.session.execute(query)
        return [
            {"category": row.category, "count": row.count}
            for row in result.all()
        ]


class UserRepository:
    """Data access for user profiles."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.name))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.scalar(select(func.count(User.id)))
        return result or 0

    async def create(self, name: str, aliases: str = "[]") -> User:
        user = User(name=name, aliases=aliases)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: User, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(user, key, value)
        await self.session.commit()

    async def delete(self, user_id: int) -> bool:
        user = await self.get(user_id)
        if not user:
            return False
        await self.session.delete(user)
        await self.session.commit()
        return True


class WatchDirectoryRepository:
    """Data access for watch directory configuration."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[WatchDirectory]:
        result = await self.session.execute(
            select(WatchDirectory).where(WatchDirectory.is_active == True).order_by(WatchDirectory.path)  # noqa: E712
        )
        return list(result.scalars().all())

    async def list(self) -> list[WatchDirectory]:
        result = await self.session.execute(select(WatchDirectory).order_by(WatchDirectory.path))
        return list(result.scalars().all())

    async def get(self, dir_id: int) -> WatchDirectory | None:
        result = await self.session.execute(
            select(WatchDirectory).where(WatchDirectory.id == dir_id)
        )
        return result.scalar_one_or_none()

    async def get_by_path(self, path: str) -> WatchDirectory | None:
        result = await self.session.execute(
            select(WatchDirectory).where(WatchDirectory.path == path)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        path: str,
        patterns: str = "[]",
        is_active: bool = True,
        file_policy: str = "keep_original",
        archive_path: str | None = None,
        rename_template: str | None = None,
    ) -> WatchDirectory:
        wd = WatchDirectory(
            path=path,
            patterns=patterns,
            is_active=is_active,
            file_policy=file_policy,
            archive_path=archive_path,
            rename_template=rename_template,
        )
        self.session.add(wd)
        await self.session.commit()
        await self.session.refresh(wd)
        return wd

    async def update(self, wd: WatchDirectory, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(wd, key, value)
        await self.session.commit()

    async def delete(self, dir_id: int) -> bool:
        wd = await self.get(dir_id)
        if not wd:
            return False
        await self.session.delete(wd)
        await self.session.commit()
        return True


class MCPTokenRepository:
    """Data access for MCP tokens."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self) -> list[MCPToken]:
        result = await self.session.execute(
            select(MCPToken).order_by(MCPToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_hash(self, token_hash: str) -> MCPToken | None:
        result = await self.session.execute(
            select(MCPToken).where(
                MCPToken.token_hash == token_hash,
                MCPToken.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, token_hash: str, token_prefix: str) -> MCPToken:
        token = MCPToken(name=name, token_hash=token_hash, token_prefix=token_prefix)
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def update_last_used(self, token: MCPToken) -> None:
        token.last_used_at = datetime.utcnow()
        await self.session.commit()

    async def revoke(self, token_id: int) -> bool:
        result = await self.session.execute(
            select(MCPToken).where(MCPToken.id == token_id)
        )
        token = result.scalar_one_or_none()
        if not token:
            return False
        token.is_active = False
        await self.session.commit()
        return True


class BackupRepository:
    """Data access for backup records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, page: int = 1, per_page: int = 20) -> tuple[list[Backup], int]:
        total = await self.session.scalar(select(func.count(Backup.id))) or 0
        offset = (page - 1) * per_page
        result = await self.session.execute(
            select(Backup).order_by(Backup.created_at.desc()).offset(offset).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def get(self, backup_id: int) -> Backup | None:
        result = await self.session.execute(select(Backup).where(Backup.id == backup_id))
        return result.scalar_one_or_none()

    async def create(self, filename: str, path: str) -> Backup:
        backup = Backup(filename=filename, path=path, status="pending")
        self.session.add(backup)
        await self.session.commit()
        await self.session.refresh(backup)
        return backup

    async def update_status(
        self,
        backup: Backup,
        status: str,
        size_bytes: int | None = None,
        error_message: str | None = None,
    ) -> None:
        backup.status = status
        if size_bytes is not None:
            backup.size_bytes = size_bytes
        if error_message is not None:
            backup.error_message = error_message
        if status in ("success", "failed"):
            backup.completed_at = datetime.utcnow()
        await self.session.commit()


class FileOperationLogRepository:
    """Data access for file operation logs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        document_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[FileOperationLog], int]:
        query = select(FileOperationLog)
        count_query = select(func.count(FileOperationLog.id))

        if document_id is not None:
            query = query.where(FileOperationLog.document_id == document_id)
            count_query = count_query.where(FileOperationLog.document_id == document_id)
        if status:
            query = query.where(FileOperationLog.status == status)
            count_query = count_query.where(FileOperationLog.status == status)

        total = await self.session.scalar(count_query) or 0
        offset = (page - 1) * per_page
        result = await self.session.execute(
            query.order_by(FileOperationLog.created_at.desc()).offset(offset).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def create(
        self,
        operation: str,
        source_path: str,
        status: str,
        document_id: int | None = None,
        destination_path: str | None = None,
        error_message: str | None = None,
    ) -> FileOperationLog:
        entry = FileOperationLog(
            document_id=document_id,
            operation=operation,
            source_path=source_path,
            destination_path=destination_path,
            status=status,
            error_message=error_message,
        )
        self.session.add(entry)
        await self.session.commit()
        return entry


class SystemLogRepository:
    """Data access for system logs (capped at 10,000 entries)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._insert_count = 0
        self._trim_interval = 50

    async def list(
        self,
        level: str | None = None,
        component: str | None = None,
        page: int = 1,
        per_page: int = 100,
    ) -> tuple[list[SystemLog], int]:
        query = select(SystemLog)
        count_query = select(func.count(SystemLog.id))

        if level:
            query = query.where(SystemLog.level == level)
            count_query = count_query.where(SystemLog.level == level)
        if component:
            query = query.where(SystemLog.component == component)
            count_query = count_query.where(SystemLog.component == component)

        total = await self.session.scalar(count_query) or 0
        offset = (page - 1) * per_page
        result = await self.session.execute(
            query.order_by(SystemLog.created_at.desc()).offset(offset).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def create(
        self,
        level: str,
        component: str,
        message: str,
        details: str | None = None,
    ) -> SystemLog:
        entry = SystemLog(level=level, component=component, message=message, details=details)
        self.session.add(entry)
        await self.session.commit()

        self._insert_count += 1
        if self._insert_count >= self._trim_interval:
            self._insert_count = 0
            await self.trim_to_limit()

        return entry

    async def trim_to_limit(self, limit: int = 10_000) -> None:
        """Delete oldest entries beyond limit."""
        await self.session.execute(
            delete(SystemLog).where(
                SystemLog.id.notin_(
                    select(SystemLog.id).order_by(SystemLog.id.desc()).limit(limit)
                )
            )
        )
        await self.session.commit()
