"""Database engine and session management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

log = structlog.get_logger()

_engine = None
_session_factory = None


async def init_database(db_path: Path) -> None:
    """Initialize the database engine and create tables."""
    global _engine, _session_factory

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"sqlite+aiosqlite:///{db_path}"
    _engine = create_async_engine(
        url,
        echo=False,
        connect_args={"timeout": 60},  # aiosqlite busy-wait timeout (seconds)
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Set SQLite pragmas for performance
    @event.listens_for(_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30s for concurrent uploads
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()

    # Create all tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Add any columns introduced after the initial schema (lightweight migrations)
    async with _engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(documents)"))
        existing_cols = {row[1] for row in result}
        _new_document_cols = [
            ("page_images", "TEXT"),  # multi-page image sequences
        ]
        for col_name, col_type in _new_document_cols:
            if col_name not in existing_cols:
                await conn.execute(
                    text(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
                )

    # Create FTS5 virtual table and triggers
    async with _engine.begin() as conn:
        await conn.execute(
            text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text,
                document_id UNINDEXED,
                content='chunks',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)
        )

        # Triggers to keep FTS in sync
        await conn.execute(
            text("""
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, text, document_id)
                VALUES (new.id, new.text, new.document_id);
            END
        """)
        )
        await conn.execute(
            text("""
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, text, document_id)
                VALUES('delete', old.id, old.text, old.document_id);
            END
        """)
        )
        await conn.execute(
            text("""
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, text, document_id)
                VALUES('delete', old.id, old.text, old.document_id);
                INSERT INTO chunks_fts(rowid, text, document_id)
                VALUES (new.id, new.text, new.document_id);
            END
        """)
        )

    log.info("Database initialized", path=str(db_path))


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_engine():
    """Get the database engine (for direct use in special cases)."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine
