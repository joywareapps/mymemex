"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class FilePolicy(str, Enum):
    """File handling policy after ingestion."""

    keep_original = "keep_original"
    rename_template = "rename_template"
    move_to_archive = "move_to_archive"
    copy_organized = "copy_organized"
    delete_original = "delete_original"


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    quick_hash: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # File info
    original_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)

    # Processing status: pending, processing, processed, failed, waiting_llm, waiting_ocr
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    # Extracted metadata
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # AI-generated metadata (nullable, for M6+)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    has_embedding: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Timestamps
    file_modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # File policy tracking (M11)
    current_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_policy_applied: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Multi-page image sequences (e.g. img-X-001.jpg, img-X-002.jpg, ...)
    page_images: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of image paths

    # User ownership (M12)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    document_frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)  # yearly, monthly, quarterly, one-time
    time_period: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 2024, 2024-03, 2024-Q1

    # Error tracking
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    file_paths: Mapped[list[FilePath]] = relationship(
        "FilePath", back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )
    tags: Mapped[list[DocumentTag]] = relationship(
        "DocumentTag", back_populates="document", cascade="all, delete-orphan"
    )
    extracted_fields: Mapped[list["DocumentField"]] = relationship(
        "DocumentField", back_populates="document", cascade="all, delete-orphan"
    )


class FilePath(Base):
    __tablename__ = "file_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship("Document", back_populates="file_paths")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    has_embedding: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="chunks")

    __table_args__ = (Index("ix_chunks_document_id", "document_id", "chunk_index"),)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    documents: Mapped[list[DocumentTag]] = relationship(
        "DocumentTag", back_populates="tag", cascade="all, delete-orphan"
    )


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship("Document", back_populates="tags")
    tag: Mapped[Tag] = relationship("Tag", back_populates="documents")


class DocumentField(Base):
    """Extracted structured field from a document."""

    __tablename__ = "document_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)  # currency, date, string, number

    # Typed value storage (only one populated per field)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_date: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ISO date

    # For currency fields
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # Metadata
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # llm, regex, manual
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped["Document"] = relationship("Document", back_populates="extracted_fields")

    __table_args__ = (
        Index("ix_doc_fields_document", "document_id"),
        Index("ix_doc_fields_name", "field_name"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # Status: pending, running, completed, failed, waiting_llm, cancelled
    status: Mapped[str] = mapped_column(String(32), default="pending")
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_tasks_status_priority", "status", "priority"),
        Index("ix_tasks_type", "task_type", "status"),
    )


class User(Base):
    """User profile for LLM context and person tagging."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of strings
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)  # NULL = no auth required
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WatchDirectory(Base):
    """Watch folder configuration stored in database."""

    __tablename__ = "watch_directories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    patterns: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    file_policy: Mapped[str] = mapped_column(String(32), default="keep_original")
    archive_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    rename_template: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    routing_rules: Mapped[list["RoutingRule"]] = relationship(
        "RoutingRule", back_populates="watch_directory",
        cascade="all, delete-orphan", order_by="RoutingRule.priority"
    )


class RoutingRule(Base):
    """Tag-based file routing rule for a watch directory."""

    __tablename__ = "routing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_directory_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("watch_directories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255))
    directory_name: Mapped[str] = mapped_column(String(1024))   # subfolder under archive_path
    tags: Mapped[str] = mapped_column(Text, default="[]")        # JSON array of tag name strings
    match_mode: Mapped[str] = mapped_column(String(8), default="any")   # "any" | "all"
    priority: Mapped[int] = mapped_column(Integer, default=100)          # lower = higher priority
    sub_levels: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of template strings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    watch_directory: Mapped["WatchDirectory"] = relationship(
        "WatchDirectory", back_populates="routing_rules"
    )


class MCPToken(Base):
    """MCP API token for HTTP transport authentication."""

    __tablename__ = "mcp_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False)  # display only
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Backup(Base):
    """Backup record tracking."""

    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Status: pending, success, failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FileOperationLog(Base):
    """Log of file operations performed by file policies."""

    __tablename__ = "file_operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    destination_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # success, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_file_ops_document_id", "document_id"),)


class SystemLog(Base):
    """System activity log (capped at 10,000 entries)."""

    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False)  # debug, info, warning, error
    component: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_system_logs_level", "level", "component"),)
