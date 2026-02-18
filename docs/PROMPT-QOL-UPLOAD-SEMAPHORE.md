# QOL: Add Semaphore for Concurrent Upload Processing

## Context

Librarian uses SQLite with async sessions (aiosqlite). Multiple task workers can process documents concurrently. While SQLite WAL mode handles concurrent reads, concurrent writes cause lock contention.

Current mitigation: `busy_timeout=30000` (30 seconds) — a band-aid, not a real solution.

## Problem

When multiple documents are uploaded simultaneously:
1. Each upload triggers `run_ingest_pipeline()`
2. Pipeline writes to `documents`, `chunks`, `chunks_fts` tables
3. SQLite writer lock contention causes delays and potential timeouts
4. User experience degrades with concurrent uploads

## Goal

Add a semaphore to limit concurrent ingestion pipeline executions, reducing SQLite lock contention while maintaining good throughput.

## Constraints

1. **Keep it simple** — no external dependencies, use `asyncio.Semaphore`
2. **Configurable** — max concurrent ingestions should be in config (default: 2)
3. **Non-breaking** — existing tests must pass
4. **Graceful** — if semaphore acquisition fails, log and retry (don't crash)

## Relevant Files

### `src/librarian/config.py`
Add configuration option:
```python
class IngestionConfig(BaseModel):
    max_concurrent: int = 2  # Max concurrent ingestion pipelines
```

### `src/librarian/processing/pipeline.py`
Key function to protect:
```python
async def run_ingest_pipeline(
    document_id: int,
    config: AppConfig,
    events: EventManager | None = None,
) -> None:
    """Run full ingestion pipeline for a document."""
    # This function writes to SQLite extensively
    # Need semaphore around the body
```

### `src/librarian/storage/database.py`
Current pragmas:
```python
cursor.execute("PRAGMA busy_timeout=30000")  # 30s for concurrent uploads
```

## Expected Implementation

1. Add `IngestionConfig` to `config.py` with `max_concurrent` field
2. Create a module-level semaphore in `pipeline.py` initialized from config
3. Wrap `run_ingest_pipeline()` body with `async with semaphore:`
4. Handle semaphore initialization (needs to happen after config load)

## Tests to Add

1. Test that concurrent uploads respect the semaphore limit
2. Test that semaphore acquisition timeout is handled gracefully
3. Test that single upload works unchanged

## Questions to Answer

1. Where should the semaphore live? Module-level in `pipeline.py` or a shared resource?
2. How to initialize it after config is loaded? (semaphore size needs config value)
3. Should classification and extraction also be semaphored, or just ingestion?

## Deliverables

1. Updated `config.py` with `IngestionConfig`
2. Updated `pipeline.py` with semaphore protection
3. New tests in `tests/test_concurrency.py` (or similar)
4. Brief note on where to add semaphores for other heavy write operations

---

## Commands

```bash
cd ~/code/librarian
# Run tests before and after
pytest -xvs

# Check specific files
cat src/librarian/config.py
cat src/librarian/processing/pipeline.py
```
