"""Watch directory rescanning logic."""

from __future__ import annotations

from pathlib import Path
import fnmatch
import structlog

from ..config import AppConfig
from ..core.events import EventManager
from .pipeline import handle_new_file

log = structlog.get_logger()

async def rescan_directory(
    path: str | Path,
    config: AppConfig,
    events: EventManager | None = None,
) -> int:
    """
    Manually rescan a directory and ingest all matching files.
    Returns the number of files discovered.
    """
    root = Path(path).expanduser()
    if not root.exists() or not root.is_dir():
        log.error("Rescan failed: path does not exist or is not a directory", path=str(root))
        return 0

    log.info("Starting directory rescan", path=str(root))
    
    count = 0
    # Use rglob to get all files recursively
    for p in root.rglob("*"):
        if not p.is_file():
            continue
            
        # Apply the same filtering as the watcher
        if not _matches_patterns(p, config):
            continue
        if _matches_ignore_patterns(p, config):
            continue
            
        # Check file size
        try:
            size_mb = p.stat().st_size / (1024 * 1024)
            if size_mb > config.watch.max_file_size_mb:
                continue
            if p.stat().st_size == 0:
                continue
        except (FileNotFoundError, OSError):
            continue

        # Ingest
        log.info("Rescan discovered file", path=str(p))
        await handle_new_file(p, config, events)
        count += 1

    log.info("Rescan complete", path=str(root), discovered=count)
    return count

def _matches_patterns(path: Path, config: AppConfig) -> bool:
    """Check if file matches include patterns."""
    filename = path.name
    for pattern in config.watch.file_patterns:
        if fnmatch.fnmatch(filename.lower(), pattern.lower()):
            return True
    return False

def _matches_ignore_patterns(path: Path, config: AppConfig) -> bool:
    """Check if path matches ignore patterns."""
    path_str = str(path)
    for pattern in config.watch.ignore_patterns:
        if fnmatch.fnmatch(path_str, pattern):
            return True
    return False
