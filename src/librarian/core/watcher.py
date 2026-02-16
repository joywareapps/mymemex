"""File system watcher with deduplication and task queueing."""

from __future__ import annotations

import asyncio
import fnmatch
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


class FileWatcher(FileSystemEventHandler):
    """
    Watches directories for file changes with:
    - Pattern filtering (include/exclude)
    - Debouncing
    - Async event dispatch
    """

    def __init__(
        self,
        config: AppConfig,
        on_new_file: Callable | None = None,
        on_deleted_file: Callable | None = None,
    ):
        self.config = config
        self.on_new_file = on_new_file
        self.on_deleted_file = on_deleted_file
        self.observer = Observer()
        self._debounce: dict[str, float] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_queue: asyncio.Queue[FileEvent] | None = None

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        """Start watching configured directories."""
        self._loop = loop

        for directory in self.config.watch.directories:
            path = Path(directory).expanduser()
            if path.exists() and path.is_dir():
                self.observer.schedule(self, str(path), recursive=True)
                log.info("Watching directory", path=str(path))
            else:
                log.warning("Watch directory does not exist", path=str(path))

        if self.config.watch.directories:
            self.observer.start()

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

    def _handle_event(self, src_path: str, event_type: str):
        """Process a file system event with filtering and debouncing."""
        path = Path(src_path)

        if not self._matches_patterns(path):
            return

        if self._matches_ignore_patterns(path):
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
