"""File system watcher with deduplication and task queueing."""

from __future__ import annotations

import asyncio
import fnmatch
import sqlite3
import time
from pathlib import Path
from typing import Callable

import structlog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..config import AppConfig

log = structlog.get_logger()


class FileEvent:
    """Internal file event."""

    def __init__(self, path: Path, event_type: str):
        self.path = path
        self.event_type = event_type  # created, modified, deleted


def _load_active_directories_sync(db_path: str) -> list[str]:
    """Synchronously load active watch directories from SQLite."""
    try:
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                "SELECT path FROM watch_directories WHERE is_active = 1"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        log.warning("Could not load watch directories from DB", error=str(e))
        return []


def _is_directory_active_sync(db_path: str, dir_path: str) -> bool:
    """Check if a specific watch directory is active (sync DB read)."""
    try:
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                "SELECT is_active FROM watch_directories WHERE path = ?", (dir_path,)
            )
            row = cursor.fetchone()
            return bool(row and row[0])
        finally:
            conn.close()
    except Exception:
        return True  # Default to active if check fails


class FileWatcher(FileSystemEventHandler):
    """
    Watches directories for file changes with:
    - Pattern filtering (include/exclude)
    - Debouncing
    - Async event dispatch
    - DB-driven directory configuration
    """

    def __init__(
        self,
        config: AppConfig,
        on_new_file: Callable | None = None,
        on_deleted_file: Callable | None = None,
        db_path: str | None = None,
    ):
        self.config = config
        self.on_new_file = on_new_file
        self.on_deleted_file = on_deleted_file
        self.observer = Observer()
        self._debounce: dict[str, float] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_queue: asyncio.Queue[FileEvent] | None = None
        self._db_path = db_path
        # Map from watched path -> watchdog watch handle
        self._watches: dict[str, object] = {}

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        """Start watching directories loaded from DB (or config fallback)."""
        self._loop = loop

        directories: list[str] = []

        # Load from DB if db_path provided
        if self._db_path:
            directories = _load_active_directories_sync(self._db_path)
            if not directories:
                log.info("No active watch directories found in DB")

        for directory in directories:
            self._schedule_directory(directory)

        if self._watches:
            self.observer.start()
        else:
            # Start observer anyway so we can add directories later
            self.observer.start()

    def _schedule_directory(self, directory: str) -> bool:
        """Schedule a directory for watching. Returns True if newly added."""
        path = Path(directory).expanduser()
        path_str = str(path)

        if path_str in self._watches:
            return False

        if path.exists() and path.is_dir():
            watch = self.observer.schedule(self, path_str, recursive=True)
            self._watches[path_str] = watch
            log.info("Watching directory", path=path_str)
            return True
        else:
            log.warning("Watch directory does not exist", path=path_str)
            return False

    def add_directory(self, path: str) -> bool:
        """Dynamically add a directory to watch without restart."""
        added = self._schedule_directory(path)
        if added and not self.observer.is_alive():
            self.observer.start()
        return added

    def remove_directory(self, path: str) -> bool:
        """Stop watching a directory."""
        path_str = str(Path(path).expanduser())
        watch = self._watches.pop(path_str, None)
        if watch:
            try:
                self.observer.unschedule(watch)
            except Exception as e:
                log.warning("Error unscheduling directory", path=path_str, error=str(e))
            return True
        return False

    def stop(self):
        """Stop watching."""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5)

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_event(event.src_path, "created")

    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle_event(event.src_path, "modified")

    def on_deleted(self, event):
        if event.is_directory:
            return
        self._handle_event(event.src_path, "deleted")

    def _find_watch_root(self, path_str: str) -> str | None:
        """Find which watched directory root contains this path."""
        for watched_path in self._watches:
            if path_str.startswith(watched_path):
                return watched_path
        return None

    def _handle_event(self, src_path: str, event_type: str):
        """Process a file system event with filtering and debouncing."""
        path = Path(src_path)

        if not self._matches_patterns(path):
            return

        if self._matches_ignore_patterns(path):
            return

        # Check if the originating watch directory is still active
        if self._db_path:
            watch_root = self._find_watch_root(src_path)
            if watch_root and not _is_directory_active_sync(self._db_path, watch_root):
                log.debug("Watch directory paused, skipping event", path=src_path)
                return

        # Check file size for non-delete events
        if event_type != "deleted":
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
                if size_mb > self.config.watch.max_file_size_mb:
                    log.debug("File too large, skipping", path=str(path), size_mb=round(size_mb, 1))
                    return
                if path.stat().st_size == 0:
                    return
            except (FileNotFoundError, OSError):
                return

        # Debounce
        now = time.time()
        key = str(path)
        if key in self._debounce:
            if now - self._debounce[key] < self.config.watch.debounce_seconds:
                return
        self._debounce[key] = now

        log.debug("File event", path=str(path), event_type=event_type)

        # Dispatch to async handler
        if self._loop and (event_type in ("created", "modified") and self.on_new_file):
            self._loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self.on_new_file(path),
            )
        elif self._loop and event_type == "deleted" and self.on_deleted_file:
            self._loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self.on_deleted_file(path),
            )

    def _matches_patterns(self, path: Path) -> bool:
        """Check if file matches include patterns."""
        filename = path.name
        for pattern in self.config.watch.file_patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        return False

    def _matches_ignore_patterns(self, path: Path) -> bool:
        """Check if path matches ignore patterns."""
        path_str = str(path)
        for pattern in self.config.watch.ignore_patterns:
            if fnmatch.fnmatch(path_str, pattern):
                return True
        return False
