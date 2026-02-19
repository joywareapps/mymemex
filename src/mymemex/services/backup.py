"""Backup and restore service using tar.gz format."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import AppConfig
from ..storage.repositories import BackupRepository

log = structlog.get_logger()


class BackupService:
    """Creates and restores tar.gz backups."""

    def __init__(self, config: AppConfig, session: AsyncSession):
        self.config = config
        self.session = session
        self.repo = BackupRepository(session)

    def _db_path(self) -> Path:
        return self.config.database.path

    def _chromadb_path(self) -> Path:
        return self._db_path().parent / "chromadb"

    async def create_backup(self) -> object:
        """Create a tar.gz backup and record it in the DB."""
        destination = Path(self.config.backup.destination)
        destination.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        filename = f"mymemex-backup-{timestamp}.tar.gz"
        tar_path = destination / filename

        # Create a DB record first (pending)
        backup_record = await self.repo.create(filename=filename, path=str(tar_path))

        try:
            with tempfile.TemporaryDirectory() as tmp_str:
                tmp = Path(tmp_str)

                doc_count = 0
                includes: dict[str, bool] = {}

                # 1. SQLite backup
                db_src = self._db_path()
                if db_src.exists() and self.config.backup.include.database:
                    dest_db = tmp / "mymemex.db"
                    src_conn = sqlite3.connect(str(db_src))
                    dst_conn = sqlite3.connect(str(dest_db))
                    src_conn.backup(dst_conn)
                    dst_conn.close()
                    src_conn.close()
                    includes["database"] = True

                    # Count documents for metadata
                    try:
                        conn = sqlite3.connect(str(dest_db))
                        row = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
                        doc_count = row[0] if row else 0
                        conn.close()
                    except Exception:
                        pass
                else:
                    includes["database"] = False

                # 2. ChromaDB backup
                chroma_src = self._chromadb_path()
                if chroma_src.exists() and self.config.backup.include.vectors:
                    shutil.copytree(str(chroma_src), str(tmp / "chromadb"))
                    includes["vectors"] = True
                else:
                    includes["vectors"] = False

                # 3. Config file backup
                config_path = _find_config_file()
                if config_path and config_path.exists() and self.config.backup.include.config:
                    shutil.copy2(str(config_path), str(tmp / config_path.name))
                    includes["config"] = True
                else:
                    includes["config"] = False

                # 4. Write metadata.json
                metadata = {
                    "version": "1.0",
                    "created": datetime.now().isoformat(),
                    "document_count": doc_count,
                    "includes": includes,
                    "source": {
                        "database": str(db_src),
                        "chromadb": str(chroma_src),
                    },
                }
                (tmp / "metadata.json").write_text(json.dumps(metadata, indent=2))

                # 5. Pack into tar.gz
                with tarfile.open(str(tar_path), "w:gz") as tar:
                    tar.add(str(tmp), arcname=".")

            size = tar_path.stat().st_size
            await self.repo.update_status(backup_record, "success", size_bytes=size)
            log.info("Backup created", filename=filename, size_bytes=size)

        except Exception as e:
            log.error("Backup failed", error=str(e))
            await self.repo.update_status(backup_record, "failed", error_message=str(e))
            raise

        return backup_record

    async def restore_backup(self, tar_path: str) -> str:
        """
        Validate a tar.gz backup and prepare for restore.

        Returns instructions string (server must be shut down for actual restore).
        """
        path = Path(tar_path)
        if not path.exists():
            raise FileNotFoundError(f"Backup file not found: {tar_path}")

        # Validate it's a valid tar.gz with metadata.json
        with tarfile.open(str(path), "r:gz") as tar:
            names = tar.getnames()
            if "metadata.json" not in names and "./metadata.json" not in names:
                raise ValueError("Invalid backup: missing metadata.json")

        return (
            f"Backup at {tar_path} is valid. "
            "To restore: stop the server, run 'mymemex backup restore <path>', then restart."
        )


def _find_config_file() -> Path | None:
    """Locate the active config file."""
    import os

    env_path = os.environ.get("MYMEMEX_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    for loc in [
        Path.cwd() / "mymemex.yaml",
        Path.cwd() / "config" / "config.yaml",
        Path.home() / ".config" / "mymemex" / "config.yaml",
    ]:
        if loc.exists():
            return loc

    return None
