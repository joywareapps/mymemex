"""File reconciliation maintenance service."""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog

from ..storage.database import get_session
from ..storage.models import Document, WatchDirectory
from ..storage.repositories import (
    DocumentRepository,
    FileOperationLogRepository,
    WatchDirectoryRepository,
)

log = structlog.get_logger()


class ReconcileService:
    """Reconcile file locations between database records and disk."""

    async def reconcile(self) -> dict:
        """
        For every document, verify the file exists on disk and fix mismatches.

        Logic per document:
          1. current_path exists → OK
          2. current_path missing / None, file found at original_path:
             a. current_path was pointing to an archive dir → the move never
                happened; do the move now to the recorded destination.
             b. otherwise → update current_path = original_path
          3. Neither path exists → search all watch/archive dirs by filename
             and file size; if found update current_path (and move to archive
             if the watch dir policy requires it).
          4. Not found anywhere → report as missing.
        """
        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            wd_repo = WatchDirectoryRepository(session)
            log_repo = FileOperationLogRepository(session)

            watch_dirs = await wd_repo.list()

            # Collect all dirs that are worth searching
            search_roots: list[Path] = []
            for wd in watch_dirs:
                for p in (wd.path, wd.archive_path):
                    if p:
                        pp = Path(p)
                        if pp.exists() and pp not in search_roots:
                            search_roots.append(pp)

            docs, total = await doc_repo.list_documents(per_page=100000)

            report: dict = {
                "checked": total,
                "ok": 0,
                "path_updated": 0,
                "moved": 0,
                "missing": 0,
                "missing_docs": [],
            }

            for doc in docs:
                current = Path(doc.current_path) if doc.current_path else None
                original = Path(doc.original_path)

                # ── Case 1: already where we expect it ──────────────────────
                if current and current.exists():
                    report["ok"] += 1
                    continue

                # ── Locate the file ──────────────────────────────────────────
                if original.exists():
                    actual = original
                else:
                    actual = self._search(doc.original_filename, doc.file_size, search_roots)

                if actual is None:
                    report["missing"] += 1
                    report["missing_docs"].append({
                        "id": doc.id,
                        "filename": doc.original_filename,
                        "original_path": str(original),
                        "current_path": str(current) if current else None,
                    })
                    continue

                # ── Decide where the file should end up ──────────────────────
                dest = self._desired_dest(doc, actual, current, watch_dirs)

                if dest and dest != actual:
                    # File needs to be moved
                    try:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(actual), str(dest))
                        doc.current_path = str(dest)
                        await session.commit()
                        await log_repo.create(
                            operation="reconcile_move",
                            source_path=str(actual),
                            destination_path=str(dest),
                            status="success",
                            document_id=doc.id,
                        )
                        report["moved"] += 1
                        log.info("reconcile: moved", doc_id=doc.id,
                                 src=str(actual), dest=str(dest))
                    except Exception as e:
                        log.error("reconcile: move failed", doc_id=doc.id, error=str(e))
                        doc.current_path = str(actual)
                        await session.commit()
                        report["path_updated"] += 1
                else:
                    # Just update the DB reference
                    doc.current_path = str(actual)
                    await session.commit()
                    report["path_updated"] += 1
                    log.info("reconcile: path updated", doc_id=doc.id, path=str(actual))

            log.info("reconcile complete",
                     **{k: v for k, v in report.items() if k != "missing_docs"})
            return report

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _search(self, filename: str, file_size: int, roots: list[Path]) -> Path | None:
        """Search roots for a file matching name and size.  Returns first exact
        match; if no size match but exactly one name match, returns that."""
        name_matches: list[Path] = []
        for root in roots:
            for found in root.rglob(filename):
                if found.is_file():
                    if found.stat().st_size == file_size:
                        return found          # exact match
                    name_matches.append(found)
        return name_matches[0] if len(name_matches) == 1 else None

    def _find_watch_dir(self, path: Path, watch_dirs: list[WatchDirectory]) -> WatchDirectory | None:
        path_str = str(path)
        for wd in watch_dirs:
            if path_str.startswith(wd.path):
                return wd
        return None

    def _desired_dest(
        self,
        doc: Document,
        actual: Path,
        recorded_current: Path | None,
        watch_dirs: list[WatchDirectory],
    ) -> Path | None:
        """
        Return the path the file should be at, or None if it's fine where it is.

        Priority:
          1. If the DB already recorded a destination in an archive dir
             (current_path), use that — the previous move just never happened.
          2. If the watch dir that owns `actual` has move_to_archive policy,
             derive archive destination.
        """
        # Priority 1: honour the previously recorded archive destination
        if recorded_current:
            rc_str = str(recorded_current)
            for wd in watch_dirs:
                if wd.archive_path and rc_str.startswith(wd.archive_path):
                    if not recorded_current.exists():
                        return recorded_current  # move to where DB promised

        # Priority 2: watch dir policy
        wd = self._find_watch_dir(actual, watch_dirs)
        if wd and wd.archive_path and wd.file_policy == "move_to_archive":
            dest = Path(wd.archive_path) / doc.original_filename
            if dest.exists() and dest != actual:
                # Conflict — append a hash suffix
                import hashlib
                salt = hashlib.md5(str(dest).encode()).hexdigest()[:8]
                dest = dest.with_stem(f"{dest.stem}-{salt}")
            return dest

        return None
