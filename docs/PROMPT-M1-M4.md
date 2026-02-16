# Claude Code Prompt: Librarian M1-M4 Implementation

**Project:** Librarian - Sovereign Document Intelligence Platform
**Goal:** Implement milestones M1-M4 (working keyword search, no AI required)
**Effort:** High (expect 30-60 min)
**Location:** `~/code/librarian`

---

## Overview

You're implementing the first 4 milestones of Librarian, a document intelligence platform. The key constraint: **NO ML FRAMEWORK DEPENDENCIES**. All AI will be externalized via HTTP APIs (not in this phase).

After M4, users will have:
- A working document archive with keyword search
- File watching for automatic ingestion
- REST API for browsing and searching
- Zero AI dependencies

---

## MILESTONE 1: Project Skeleton + Config + CLI + SQLite Schema

### 1.1 Project Structure

Create this directory structure:

```
librarian/
├── pyproject.toml                      # Poetry/pip-compatible
├── alembic.ini                         # Alembic config
├── alembic/
│   ├── env.py
│   └── versions/                       # Empty, will add migrations
├── config/
│   └── config.example.yaml             # Example configuration
├── src/
│   └── librarian/
│       ├── __init__.py                 # Version, exports
│       ├── __main__.py                 # Entry point: python -m librarian
│       ├── config.py                   # Pydantic Settings (YAML + env vars)
│       └── app.py                      # FastAPI app factory (stub for M1)
├── tests/
│   ├── conftest.py                     # Fixtures
│   └── test_config.py                  # Config loading tests
└── docs/
    └── (existing docs remain)
```

### 1.2 pyproject.toml

```toml
[project]
name = "librarian"
version = "0.1.0"
description = "Sovereign document intelligence platform"
requires-python = ">=3.11"

dependencies = [
    # Core
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pydantic>=2.10",
    "pydantic-settings>=2.6",
    "typer>=0.15",
    "rich>=13.9",
    "structlog>=25.1",
    
    # Database
    "sqlalchemy>=2.0",
    "alembic>=1.14",
    "aiosqlite>=0.20",
    
    # File handling
    "watchdog>=6.0",
    "python-magic>=0.4.27",
    "xxhash>=3.5",
    "pymupdf>=1.25",
    "pillow>=11.0",
    "pdf2image>=1.17",
    "ftfy>=6.3",
    "langdetect>=1.0",
    
    # HTTP client (for future LLM calls)
    "httpx>=0.28",
    "litellm>=1.60",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "pytest-cov>=6.0",
    "ruff>=0.9",
    "mypy>=1.14",
]
ocr = [
    "pytesseract>=0.3",
]

[project.scripts]
librarian = "librarian.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 1.3 Configuration System (src/librarian/config.py)

Use Pydantic Settings with hierarchical loading: defaults → YAML → env vars.

```python
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

class WatchConfig(BaseSettings):
    """File watching configuration."""
    directories: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(default=["*.pdf", "*.png", "*.jpg", "*.jpeg"])
    ignore_patterns: list[str] = Field(default=["*/.*", "*/.Trash-*", "*/@eaDir/*"])
    debounce_seconds: float = 2.0
    max_file_size_mb: int = 100

class DatabaseConfig(BaseSettings):
    """Database configuration."""
    path: Path = Field(default=Path("~/.local/share/librarian/librarian.db"))
    pool_size: int = 5
    
    @field_validator("path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        return Path(v).expanduser()

class OCRConfig(BaseSettings):
    """OCR configuration (for M5, stub for now)."""
    enabled: bool = False
    language: str = "eng"
    dpi: int = 300
    confidence_threshold: float = 0.7

class LLMConfig(BaseSettings):
    """LLM configuration (for M6+, stub for now)."""
    provider: Literal["ollama", "openai", "anthropic", "none"] = "none"
    model: str = ""
    api_base: str = "http://localhost:11434"

class AppConfig(BaseSettings):
    """Main application configuration."""
    model_config = SettingsConfigDict(
        env_prefix="LIBRARIAN_",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # Core settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    # Component configs
    watch: WatchConfig = Field(default_factory=WatchConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    
    @classmethod
    def from_yaml(cls, path: Path) -> "AppConfig":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()
        
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        
        return cls.model_validate(data)


def load_config(config_path: Path | None = None) -> AppConfig:
    """
    Load configuration with priority:
    1. Explicit path (if provided)
    2. LIBRARIAN_CONFIG env var
    3. ./librarian.yaml
    4. ~/.config/librarian/config.yaml
    5. Defaults only
    """
    import os
    
    if config_path:
        return AppConfig.from_yaml(config_path)
    
    # Check environment variable
    env_path = os.environ.get("LIBRARIAN_CONFIG")
    if env_path:
        return AppConfig.from_yaml(Path(env_path))
    
    # Check common locations
    for loc in [
        Path.cwd() / "librarian.yaml",
        Path.cwd() / "config" / "config.yaml",
        Path.home() / ".config" / "librarian" / "config.yaml",
    ]:
        if loc.exists():
            return AppConfig.from_yaml(loc)
    
    return AppConfig()
```

### 1.4 CLI (src/librarian/__main__.py)

```python
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path

from .config import load_config, AppConfig
from . import __version__

app = typer.Typer(
    name="librarian",
    help="Sovereign document intelligence platform",
    add_completion=False,
)
console = Console()

@app.command()
def version():
    """Show version information."""
    console.print(f"Librarian v{__version__}")

@app.command()
def config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    path: Path | None = typer.Option(None, "--path", "-p", help="Config file path"),
):
    """Manage configuration."""
    cfg = load_config(path)
    
    if show:
        table = Table(title="Configuration")
        table.add_column("Section", style="cyan")
        table.add_column("Key", style="green")
        table.add_column("Value", style="yellow")
        
        def add_section(section_name: str, obj: BaseSettings):
            for field_name, field_info in obj.model_fields.items():
                value = getattr(obj, field_name)
                if isinstance(value, Path):
                    value = str(value)
                elif isinstance(value, list):
                    value = ", ".join(map(str, value)) if value else "(empty)"
                table.add_row(section_name, field_name, str(value))
        
        add_section("core", cfg)
        add_section("watch", cfg.watch)
        add_section("database", cfg.database)
        add_section("ocr", cfg.ocr)
        add_section("llm", cfg.llm)
        
        console.print(table)

@app.command()
def init(
    path: Path = typer.Argument(
        Path("~/.local/share/librarian"),
        help="Directory to initialize",
    ),
):
    """Initialize a new Librarian instance."""
    path = path.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (path / "chromadb").mkdir(exist_ok=True)
    
    # Create default config
    config_path = path / "config.yaml"
    if not config_path.exists():
        config_content = """# Librarian Configuration
debug: false
log_level: INFO

watch:
  directories:
    - /mnt/nas/documents  # Change to your document path
  file_patterns:
    - "*.pdf"
    - "*.png"
    - "*.jpg"
    - "*.jpeg"
  ignore_patterns:
    - "*/.*"
    - "*/.Trash-*"
    - "*/@eaDir/*"
  debounce_seconds: 2.0
  max_file_size_mb: 100

database:
  path: ~/.local/share/librarian/librarian.db

ocr:
  enabled: false  # Enable for scanned documents (M5)
  language: eng
  dpi: 300

llm:
  provider: none  # Set to 'ollama' for AI features (M6+)
"""
        config_path.write_text(config_content)
        console.print(f"[green]Created:[/] {config_path}")
    
    console.print(f"[green]Initialized Librarian at:[/] {path}")
    console.print(f"\nNext steps:")
    console.print(f"  1. Edit {config_path}")
    console.print(f"  2. Run [cyan]librarian migrate[/] to create database")
    console.print(f"  3. Run [cyan]librarian start[/] to begin watching")

@app.command()
def migrate():
    """Run database migrations."""
    import subprocess
    console.print("[yellow]Running database migrations...[/]")
    # Alembic will be configured in M2
    console.print("[green]Migrations complete.[/]")

@app.command()
def start():
    """Start the Librarian service."""
    console.print("[yellow]Starting Librarian...[/]")
    # Will be implemented in M2-M4
    console.print("[red]Not yet implemented. Complete M2-M4 first.[/]")

def main():
    app()

if __name__ == "__main__":
    main()
```

### 1.5 SQLite Schema (initial migration)

Create `alembic/versions/001_initial_schema.py`:

```python
"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Documents table - core metadata
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('content_hash', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('quick_hash', sa.String(32), nullable=False, index=True),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        
        # File info
        sa.Column('original_path', sa.String(1024), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(127), nullable=False),
        
        # Processing status
        sa.Column('status', sa.String(32), nullable=False, default='pending'),
        # Status values: pending, processing, ready, failed, waiting_llm, waiting_ocr
        
        # Extracted metadata
        sa.Column('page_count', sa.Integer()),
        sa.Column('language', sa.String(10)),
        sa.Column('title', sa.String(512)),
        sa.Column('author', sa.String(255)),
        sa.Column('created_date', sa.DateTime()),
        
        # AI-generated metadata (nullable, for M6+)
        sa.Column('summary', sa.Text()),
        sa.Column('category', sa.String(64)),
        sa.Column('has_embedding', sa.Boolean(), default=False),
        sa.Column('embedding_model', sa.String(64)),
        
        # Timestamps
        sa.Column('file_modified_at', sa.DateTime(), nullable=False),
        sa.Column('ingested_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        # Error tracking
        sa.Column('error_count', sa.Integer(), default=0),
        sa.Column('last_error', sa.Text()),
    )
    
    # File paths - one document can have multiple paths (deduplication)
    op.create_table(
        'file_paths',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('path', sa.String(1024), unique=True, nullable=False),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('first_seen_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_file_paths_path', 'file_paths', ['path'])
    
    # Chunks - text segments for search
    op.create_table(
        'chunks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer()),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('char_count', sa.Integer(), nullable=False),
        sa.Column('extraction_method', sa.String(32)),  # pymupdf_native, tesseract, etc.
        sa.Column('has_embedding', sa.Boolean(), default=False),
    )
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id', 'chunk_index'])
    
    # Tags
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(64), unique=True, nullable=False),
        sa.Column('color', sa.String(7)),  # Hex color
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Document tags (many-to-many)
    op.create_table(
        'document_tags',
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('is_auto', sa.Boolean(), default=False),  # Auto-tagged by AI
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Task queue (SQLite-backed)
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_type', sa.String(64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('status', sa.String(32), default='pending'),
        # Status: pending, running, completed, failed, waiting_llm
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE')),
        sa.Column('attempt_count', sa.Integer(), default=0),
        sa.Column('max_attempts', sa.Integer(), default=3),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('next_retry_at', sa.DateTime()),
    )
    op.create_index('ix_tasks_status_priority', 'tasks', ['status', 'priority'])
    op.create_index('ix_tasks_type', 'tasks', ['task_type', 'status'])
    
    # FTS5 full-text search (virtual table)
    # Note: SQLite FTS5 syntax, not SQLAlchemy
    op.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            text,
            document_id UNINDEXED,
            content='chunks',
            content_rowid='id',
            tokenize='porter unicode61'
        )
    """)
    
    # Triggers to keep FTS in sync
    op.execute("""
        CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, text, document_id)
            VALUES (new.id, new.text, new.document_id);
        END
    """)
    
    op.execute("""
        CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text, document_id)
            VALUES('delete', old.id, old.text, old.document_id);
        END
    """)
    
    op.execute("""
        CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text, document_id)
            VALUES('delete', old.id, old.text, old.document_id);
            INSERT INTO chunks_fts(rowid, text, document_id)
            VALUES (new.id, new.text, new.document_id);
        END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS chunks_au")
    op.execute("DROP TRIGGER IF EXISTS chunks_ad")
    op.execute("DROP TRIGGER IF EXISTS chunks_ai")
    op.execute("DROP TABLE IF EXISTS chunks_fts")
    op.drop_table('tasks')
    op.drop_table('document_tags')
    op.drop_table('tags')
    op.drop_table('chunks')
    op.drop_table('file_paths')
    op.drop_table('documents')
```

---

## MILESTONE 2: File Watcher + Dedup + Task Queue

### 2.1 Two-Phase Hashing (src/librarian/processing/hasher.py)

```python
"""Two-phase file hashing for fast deduplication."""
import hashlib
import os
import xxhash
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileHash:
    """File hash result."""
    content_hash: str      # SHA-256 (canonical)
    quick_hash: str        # xxhash of first 4KB + size
    file_size: int


def quick_fingerprint(path: Path) -> str:
    """
    Fast pre-filter: file size + xxhash of first 4KB.
    ~2 seconds for 50K files on SSD.
    """
    stat = path.stat()
    with open(path, "rb") as f:
        head = f.read(4096)
    return f"{stat.st_size}:{xxhash.xxh64(head).hexdigest()}"


def canonical_hash(path: Path, buf_size: int = 1 << 20) -> str:
    """
    Full SHA-256 hash.
    Only computed for files that pass quick_fingerprint as new.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(buf_size):
            h.update(chunk)
    return h.hexdigest()


def hash_file(path: Path, skip_full: bool = False) -> FileHash:
    """
    Hash a file with two-phase approach.
    
    Args:
        path: File path
        skip_full: If True, only compute quick hash (for pre-filtering)
    
    Returns:
        FileHash with both hashes (content_hash empty if skip_full)
    """
    file_size = path.stat().st_size
    quick = quick_fingerprint(path)
    
    if skip_full:
        return FileHash(
            content_hash="",
            quick_hash=quick,
            file_size=file_size,
        )
    
    content = canonical_hash(path)
    return FileHash(
        content_hash=content,
        quick_hash=quick,
        file_size=file_size,
    )
```

### 2.2 Task Queue (src/librarian/core/queue.py)

```python
"""SQLite-backed task queue."""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Literal
from enum import Enum

import structlog
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.models import Task

log = structlog.get_logger()


class TaskType(str, Enum):
    INGEST = "ingest"
    EXTRACT_TEXT = "extract_text"
    OCR_PAGE = "ocr_page"
    CHUNK = "chunk"
    EMBED = "embed"
    CLASSIFY = "classify"
    SUGGEST = "suggest"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_LLM = "waiting_llm"


class TaskQueue:
    """SQLite-backed async task queue with priorities and retries."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def enqueue(
        self,
        task_type: TaskType,
        payload: dict[str, Any],
        document_id: int | None = None,
        priority: int = 0,
        max_attempts: int = 3,
    ) -> Task:
        """Add a task to the queue."""
        task = Task(
            task_type=task_type.value,
            payload=payload,
            document_id=document_id,
            priority=priority,
            status=TaskStatus.PENDING.value,
            max_attempts=max_attempts,
        )
        self.session.add(task)
        await self.session.commit()
        log.debug("Task enqueued", task_id=task.id, type=task_type.value)
        return task
    
    async def dequeue(
        self,
        task_types: list[TaskType] | None = None,
        limit: int = 1,
    ) -> list[Task]:
        """
        Get next pending tasks, ordered by priority (desc) then created_at (asc).
        
        Args:
            task_types: Filter to specific task types (None = all)
            limit: Max tasks to return
        
        Returns:
            List of tasks with status updated to RUNNING
        """
        query = (
            select(Task)
            .where(Task.status == TaskStatus.PENDING.value)
            .where(
                (Task.next_retry_at == None) |
                (Task.next_retry_at <= datetime.utcnow())
            )
            .order_by(Task.priority.desc(), Task.created_at.asc())
            .limit(limit)
        )
        
        if task_types:
            query = query.where(Task.task_type.in_([t.value for t in task_types]))
        
        result = await self.session.execute(query)
        tasks = list(result.scalars().all())
        
        # Mark as running
        for task in tasks:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.utcnow()
        
        await self.session.commit()
        return tasks
    
    async def complete(self, task: Task) -> None:
        """Mark task as completed."""
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.utcnow()
        await self.session.commit()
        log.debug("Task completed", task_id=task.id)
    
    async def fail(
        self,
        task: Task,
        error: str,
        retryable: bool = True,
    ) -> None:
        """
        Mark task as failed, schedule retry if possible.
        
        Args:
            task: The failed task
            error: Error message
            retryable: Whether this error is retryable
        """
        task.error_message = error
        task.error_count += 1
        task.attempt_count += 1
        
        can_retry = (
            retryable and
            task.attempt_count < task.max_attempts and
            task.task_type in [TaskType.EMBED.value, TaskType.CLASSIFY.value, TaskType.OCR_PAGE.value]
        )
        
        if can_retry:
            # Exponential backoff: 1m, 5m, 15m
            delays = [60, 300, 900]
            delay = delays[min(task.attempt_count - 1, len(delays) - 1)]
            task.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            task.status = TaskStatus.PENDING.value
            log.warning(
                "Task failed, will retry",
                task_id=task.id,
                attempt=task.attempt_count,
                retry_in_seconds=delay,
                error=error,
            )
        else:
            task.status = TaskStatus.FAILED.value
            log.error("Task failed permanently", task_id=task.id, error=error)
        
        await self.session.commit()
    
    async def set_waiting_llm(self, task: Task) -> None:
        """Set task to waiting_llm state (for when LLM is unavailable)."""
        task.status = TaskStatus.WAITING_LLM.value
        await self.session.commit()
        log.info("Task waiting for LLM", task_id=task.id)
    
    async def get_pending_count(self) -> int:
        """Count of pending tasks."""
        result = await self.session.execute(
            select(Task.id).where(Task.status == TaskStatus.PENDING.value)
        )
        return len(list(result.scalars().all()))
    
    async def recover_stale(
        self,
        timeout_minutes: int = 30,
    ) -> int:
        """
        Reset tasks stuck in RUNNING state (e.g., after crash).
        
        Returns:
            Number of tasks recovered
        """
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        result = await self.session.execute(
            update(Task)
            .where(Task.status == TaskStatus.RUNNING.value)
            .where(Task.started_at < cutoff)
            .values(status=TaskStatus.PENDING.value, started_at=None)
            .returning(Task.id)
        )
        recovered = len(list(result.scalars().all()))
        await self.session.commit()
        
        if recovered:
            log.warning("Recovered stale tasks", count=recovered)
        
        return recovered
```

### 2.3 File Watcher (src/librarian/core/watcher.py)

```python
"""File system watcher with deduplication and task queueing."""
import asyncio
from pathlib import Path
from typing import Callable
import fnmatch

import structlog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from ..config import AppConfig
from ..processing.hasher import hash_file, quick_fingerprint
from ..storage.database import get_session
from ..storage.repositories import DocumentRepository
from ..queue import TaskQueue, TaskType

log = structlog.get_logger()


class FileEvent:
    """Internal file event."""
    def __init__(self, path: Path, event_type: str):
        self.path = path
        self.event_type = event_type  # created, modified, deleted


class FileWatcher(FileSystemEventHandler):
    """
    Watches directories for file changes with:
    - Pattern filtering (include/exclude)
    - Deduplication via two-phase hashing
    - Debouncing
    - Task queueing
    """
    
    def __init__(
        self,
        config: AppConfig,
        on_event: Callable[[FileEvent], None] | None = None,
    ):
        self.config = config
        self.on_event = on_event
        self.observer = Observer()
        self._debounce: dict[str, float] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
    
    def start(self):
        """Start watching configured directories."""
        # Get asyncio loop for thread-safe callback
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        
        for directory in self.config.watch.directories:
            path = Path(directory).expanduser()
            if path.exists():
                self.observer.schedule(self, str(path), recursive=True)
                log.info("Watching directory", path=str(path))
            else:
                log.warning("Watch directory does not exist", path=str(path))
        
        self.observer.start()
    
    def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join()
    
    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_event(event, "created")
    
    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle_event(event, "modified")
    
    def on_deleted(self, event):
        if event.is_directory:
            return
        self._handle_event(event, "deleted")
    
    def _handle_event(self, event, event_type: str):
        """Process a file system event with filtering and debouncing."""
        path = Path(event.src_path)
        
        # Check file patterns
        if not self._matches_patterns(path):
            return
        
        # Check ignore patterns
        if self._matches_ignore_patterns(path):
            return
        
        # Check file size
        if event_type != "deleted":
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
                if size_mb > self.config.watch.max_file_size_mb:
                    log.debug("File too large, skipping", path=str(path), size_mb=size_mb)
                    return
            except FileNotFoundError:
                return
        
        # Debounce
        import time
        now = time.time()
        key = str(path)
        if key in self._debounce:
            if now - self._debounce[key] < self.config.watch.debounce_seconds:
                return
        
        self._debounce[key] = now
        
        # Emit event
        log.debug("File event", path=str(path), event_type=event_type)
        
        if self.on_event:
            file_event = FileEvent(path, event_type)
            if self._loop:
                # Schedule in asyncio loop (thread-safe)
                self._loop.call_soon_threadsafe(
                    lambda: self.on_event(file_event)
                )
            else:
                self.on_event(file_event)
    
    def _matches_patterns(self, path: Path) -> bool:
        """Check if file matches include patterns."""
        filename = path.name
        for pattern in self.config.watch.file_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
    
    def _matches_ignore_patterns(self, path: Path) -> bool:
        """Check if path matches ignore patterns."""
        path_str = str(path)
        for pattern in self.config.watch.ignore_patterns:
            if fnmatch.fnmatch(path_str, pattern):
                return True
            # Also check each parent directory
            for parent in path.parents:
                if fnmatch.fnmatch(str(parent), pattern):
                    return True
        return False


async def process_file_event(event: FileEvent, config: AppConfig) -> None:
    """
    Process a file event: deduplicate and queue for ingestion.
    
    This is the main handler for file watcher events.
    """
    if event.event_type == "deleted":
        # TODO: Mark document as deleted or remove file_path
        log.info("File deleted", path=str(event.path))
        return
    
    async with get_session() as session:
        repo = DocumentRepository(session)
        queue = TaskQueue(session)
        
        # Quick hash for dedup check
        try:
            quick = quick_fingerprint(event.path)
        except Exception as e:
            log.error("Failed to hash file", path=str(event.path), error=str(e))
            return
        
        # Check if we already have this file by quick hash
        existing = await repo.find_by_quick_hash(quick)
        if existing:
            # Already have this content - just add another path
            log.info("Duplicate detected", path=str(event.path), existing_id=existing.id)
            await repo.add_file_path(existing.id, str(event.path))
            return
        
        # Check by full hash (in case quick hash missed)
        full_hash = hash_file(event.path)
        existing = await repo.find_by_content_hash(full_hash.content_hash)
        if existing:
            log.info("Duplicate by content hash", path=str(event.path), existing_id=existing.id)
            await repo.add_file_path(existing.id, str(event.path))
            return
        
        # New document - create and queue
        doc = await repo.create(
            content_hash=full_hash.content_hash,
            quick_hash=full_hash.quick_hash,
            file_size=full_hash.file_size,
            original_path=str(event.path),
            original_filename=event.path.name,
            mime_type=get_mime_type(event.path),
            file_modified_at=event.path.stat().st_mtime,
        )
        
        await queue.enqueue(
            task_type=TaskType.INGEST,
            payload={"document_id": doc.id},
            document_id=doc.id,
            priority=0,
        )
        
        log.info("New document queued", doc_id=doc.id, path=str(event.path))


def get_mime_type(path: Path) -> str:
    """Get MIME type for a file."""
    import magic
    try:
        mime = magic.from_file(str(path), mime=True)
        return mime
    except Exception:
        # Fallback to extension
        ext = path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".txt": "text/plain",
        }
        return mime_map.get(ext, "application/octet-stream")
```

---

## MILESTONE 3: Text Extraction + Chunking + FTS5

### 3.1 Text Extractor (src/librarian/processing/extractor.py)

```python
"""Text extraction from PDFs using PyMuPDF."""
import fitz  # PyMuPDF
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import structlog

log = structlog.get_logger()


@dataclass
class ExtractedPage:
    """Text extracted from a single page."""
    page_number: int
    text: str
    char_count: int
    method: str  # pymupdf_native, needs_ocr


def extract_text_from_pdf(
    path: Path,
    min_chars_for_native: int = 50,
) -> Iterator[ExtractedPage]:
    """
    Extract text from PDF using PyMuPDF native extraction.
    
    For ~60% of PDFs (born-digital), this gives instant text.
    For scanned PDFs, returns empty text (to be filled by OCR in M5).
    
    Args:
        path: Path to PDF file
        min_chars_for_native: Minimum chars to consider page as having native text
    
    Yields:
        ExtractedPage for each page
    """
    try:
        doc = fitz.open(str(path))
    except Exception as e:
        log.error("Failed to open PDF", path=str(path), error=str(e))
        raise
    
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Try native text extraction
            text = page.get_text("text")
            
            if len(text.strip()) >= min_chars_for_native:
                # Clean up text
                text = _clean_text(text)
                yield ExtractedPage(
                    page_number=page_num,
                    text=text,
                    char_count=len(text),
                    method="pymupdf_native",
                )
            else:
                # Needs OCR (will be handled in M5)
                yield ExtractedPage(
                    page_number=page_num,
                    text="",
                    char_count=0,
                    method="needs_ocr",
                )
    finally:
        doc.close()


def _clean_text(text: str) -> str:
    """Clean extracted text."""
    import ftfy
    
    # Fix encoding issues
    text = ftfy.fix_text(text)
    
    # Normalize whitespace
    lines = text.split("\n")
    lines = [line.strip() for line in lines]
    lines = [line for line in lines if line]
    
    return "\n".join(lines)


def get_pdf_page_count(path: Path) -> int:
    """Get number of pages in PDF."""
    try:
        doc = fitz.open(str(path))
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0
```

### 3.2 Chunker (src/librarian/processing/chunker.py)

```python
"""Text chunking for embedding and search."""
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass
class TextChunk:
    """A chunk of text."""
    text: str
    chunk_index: int
    page_number: int | None
    char_count: int


def chunk_text(
    text: str,
    page_number: int | None = None,
    max_chars: int = 1500,
    overlap_chars: int = 200,
) -> list[TextChunk]:
    """
    Split text into overlapping chunks.
    
    Strategy:
    1. Split on double newlines (paragraphs)
    2. If still too big, split on single newlines
    3. If still too big, split on sentence boundaries
    4. Last resort: hard split
    
    Args:
        text: Text to chunk
        page_number: Page number this text came from
        max_chars: Maximum chars per chunk (~375 tokens at 4 chars/token)
        overlap_chars: Overlap between chunks (~50 tokens)
    
    Returns:
        List of TextChunks
    """
    if not text.strip():
        return []
    
    if len(text) <= max_chars:
        return [TextChunk(
            text=text.strip(),
            chunk_index=0,
            page_number=page_number,
            char_count=len(text.strip()),
        )]
    
    # Try paragraph split
    chunks = _split_on_separator(text, "\n\n", max_chars, overlap_chars)
    if chunks:
        return [
            TextChunk(text=c, chunk_index=i, page_number=page_number, char_count=len(c))
            for i, c in enumerate(chunks)
        ]
    
    # Try line split
    chunks = _split_on_separator(text, "\n", max_chars, overlap_chars)
    if chunks:
        return [
            TextChunk(text=c, chunk_index=i, page_number=page_number, char_count=len(c))
            for i, c in enumerate(chunks)
        ]
    
    # Try sentence split
    chunks = _split_on_separator(text, r"(?<=[.!?])\s+", max_chars, overlap_chars, regex=True)
    if chunks:
        return [
            TextChunk(text=c, chunk_index=i, page_number=page_number, char_count=len(c))
            for i, c in enumerate(chunks)
        ]
    
    # Hard split
    chunks = _hard_split(text, max_chars, overlap_chars)
    return [
        TextChunk(text=c, chunk_index=i, page_number=page_number, char_count=len(c))
        for i, c in enumerate(chunks)
    ]


def _split_on_separator(
    text: str,
    sep: str,
    max_chars: int,
    overlap_chars: int,
    regex: bool = False,
) -> list[str] | None:
    """Split text on separator, respecting max_chars."""
    if regex:
        parts = re.split(sep, text)
    else:
        parts = text.split(sep)
    
    parts = [p.strip() for p in parts if p.strip()]
    
    if not parts:
        return None
    
    # Check if all parts are small enough
    if all(len(p) <= max_chars for p in parts):
        # Merge small consecutive parts
        return _merge_chunks(parts, max_chars)
    
    # Some parts are too big - need recursive splitting
    result = []
    for part in parts:
        if len(part) <= max_chars:
            result.append(part)
        else:
            # Recurse with different separator
            sub_chunks = chunk_text(part, max_chars=max_chars, overlap_chars=overlap_chars)
            result.extend([c.text for c in sub_chunks])
    
    return _merge_chunks(result, max_chars)


def _merge_chunks(chunks: list[str], max_chars: int) -> list[str]:
    """Merge small consecutive chunks."""
    result = []
    current = ""
    
    for chunk in chunks:
        if len(current) + len(chunk) + 2 <= max_chars:
            if current:
                current += "\n\n" + chunk
            else:
                current = chunk
        else:
            if current:
                result.append(current)
            current = chunk
    
    if current:
        result.append(current)
    
    return result


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Hard split on max_chars boundary with overlap."""
    result = []
    start = 0
    
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end].strip()
        if chunk:
            result.append(chunk)
        start = end - overlap_chars
    
    return result
```

### 3.3 Ingestion Pipeline (src/librarian/processing/pipeline.py)

```python
"""Document ingestion pipeline."""
import asyncio
from pathlib import Path

import structlog

from ..config import AppConfig
from ..storage.database import get_session
from ..storage.repositories import DocumentRepository, ChunkRepository
from ..queue import TaskQueue, TaskType, TaskStatus
from ..models import Task
from .extractor import extract_text_from_pdf, get_pdf_page_count
from .chunker import chunk_text

log = structlog.get_logger()


async def run_ingest_pipeline(document_id: int, config: AppConfig) -> None:
    """
    Run full ingestion pipeline for a document.
    
    Steps:
    1. Extract text from PDF (PyMuPDF native)
    2. Chunk text
    3. Store chunks (triggers FTS5 indexing)
    4. Update document status
    5. Queue OCR for pages that need it (M5)
    """
    async with get_session() as session:
        repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        queue = TaskQueue(session)
        
        doc = await repo.get_by_id(document_id)
        if not doc:
            log.error("Document not found", doc_id=document_id)
            return
        
        path = Path(doc.original_path)
        if not path.exists():
            log.error("File not found", path=str(path))
            await repo.update_status(doc, "failed", error="File not found")
            return
        
        # Update status
        await repo.update_status(doc, "processing")
        
        try:
            # Get page count
            page_count = get_pdf_page_count(path)
            await repo.update(doc, page_count=page_count)
            
            # Extract text
            all_chunks = []
            pages_needing_ocr = []
            
            for page in extract_text_from_pdf(path):
                if page.method == "needs_ocr":
                    pages_needing_ocr.append(page.page_number)
                    continue
                
                # Chunk the page text
                page_chunks = chunk_text(
                    page.text,
                    page_number=page.page_number,
                )
                all_chunks.extend(page_chunks)
            
            # Store chunks
            for chunk in all_chunks:
                await chunk_repo.create(
                    document_id=doc.id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    char_count=chunk.char_count,
                    extraction_method="pymupdf_native",
                )
            
            # Update document status
            await repo.update_status(doc, "ready")
            await repo.update(doc, processed_at=datetime.utcnow())
            
            log.info(
                "Document ingested",
                doc_id=doc.id,
                chunks=len(all_chunks),
                pages=page_count,
                pages_needing_ocr=len(pages_needing_ocr),
            )
            
            # Queue OCR tasks for pages that need it (M5)
            if config.ocr.enabled and pages_needing_ocr:
                for page_num in pages_needing_ocr:
                    await queue.enqueue(
                        task_type=TaskType.OCR_PAGE,
                        payload={"document_id": doc.id, "page_number": page_num},
                        document_id=doc.id,
                        priority=1,
                    )
        
        except Exception as e:
            log.exception("Ingestion failed", doc_id=doc.id, error=str(e))
            await repo.update_status(doc, "failed", error=str(e))


# Worker that processes tasks
async def task_worker(config: AppConfig, worker_id: int = 0) -> None:
    """
    Background worker that processes tasks from the queue.
    
    Run multiple workers for parallelism.
    """
    log.info("Task worker started", worker_id=worker_id)
    
    while True:
        try:
            async with get_session() as session:
                queue = TaskQueue(session)
                
                # Get next task
                tasks = await queue.dequeue(limit=1)
                
                if not tasks:
                    await asyncio.sleep(1)
                    continue
                
                task = tasks[0]
                
                try:
                    await process_task(task, config, queue)
                except Exception as e:
                    log.exception("Task processing error", task_id=task.id)
                    await queue.fail(task, str(e))
        
        except asyncio.CancelledError:
            log.info("Task worker stopping", worker_id=worker_id)
            break
        except Exception as e:
            log.exception("Worker error", worker_id=worker_id, error=str(e))
            await asyncio.sleep(5)


async def process_task(task: Task, config: AppConfig, queue: TaskQueue) -> None:
    """Process a single task based on its type."""
    log.info("Processing task", task_id=task.id, type=task.task_type)
    
    if task.task_type == TaskType.INGEST.value:
        doc_id = task.payload["document_id"]
        await run_ingest_pipeline(doc_id, config)
        await queue.complete(task)
    
    elif task.task_type == TaskType.OCR_PAGE.value:
        # M5 implementation
        log.warning("OCR not yet implemented", task_id=task.id)
        await queue.fail(task, "OCR not implemented in M1-M4")
    
    else:
        log.warning("Unknown task type", task_id=task.id, type=task.task_type)
        await queue.fail(task, f"Unknown task type: {task.task_type}")
```

---

## MILESTONE 4: REST API + Keyword Search

### 4.1 FastAPI App Factory (src/librarian/app.py)

```python
"""FastAPI application factory."""
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import load_config, AppConfig
from .api.router import api_router
from .core.watcher import FileWatcher, process_file_event
from .core.queue import TaskQueue
from .processing.pipeline import task_worker
from .storage.database import init_database

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    config: AppConfig = app.state.config
    
    # Startup
    log.info("Librarian starting up", debug=config.debug)
    
    # Initialize database
    await init_database(config.database.path)
    
    # Start file watcher
    watcher = FileWatcher(config, on_event=lambda e: asyncio.create_task(process_file_event(e, config)))
    watcher.start()
    app.state.watcher = watcher
    
    # Start task workers
    app.state.workers = []
    for i in range(2):  # 2 workers for parallelism
        worker = asyncio.create_task(task_worker(config, worker_id=i))
        app.state.workers.append(worker)
    
    log.info("Librarian ready")
    
    yield
    
    # Shutdown
    log.info("Librarian shutting down")
    
    # Stop workers
    for worker in app.state.workers:
        worker.cancel()
    
    # Stop watcher
    watcher.stop()
    
    log.info("Librarian stopped")


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create FastAPI application."""
    if config is None:
        config = load_config()
    
    app = FastAPI(
        title="Librarian",
        description="Sovereign document intelligence platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    app.state.config = config
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(api_router, prefix="/api/v1")
    
    return app


import asyncio
