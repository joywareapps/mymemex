import asyncio
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from mymemex.processing.pipeline import run_ingest_pipeline, _get_ingest_semaphore
from mymemex.storage.repositories import DocumentRepository
from mymemex.config import AppConfig

@pytest.mark.asyncio
async def test_ingest_semaphore_limits_concurrency(test_config, db_session, sample_pdf):
    # Setup: 3 documents with unique paths
    repo = DocumentRepository(db_session)
    docs = []
    for i in range(3):
        unique_path = str(sample_pdf).replace(".pdf", f"_{i}.pdf")
        shutil.copy(sample_pdf, unique_path)
        
        doc = await repo.create(
            content_hash=f"hash{i}",
            quick_hash=f"quick{i}",
            file_size=100,
            original_path=unique_path,
            original_filename=f"file{i}.pdf",
            mime_type="application/pdf",
            file_modified_at=123456789.0,
        )
        docs.append(doc)
    await db_session.commit()

    # Configure semaphore to 2
    test_config.ingestion.max_concurrent = 2
    
    # Reset module-level semaphore for test
    import mymemex.processing.pipeline as pipeline
    pipeline._ingest_semaphore = None

    active_count = 0
    max_active = 0
    lock = asyncio.Lock()

    async def mocked_update(self, doc, **kwargs):
        nonlocal active_count, max_active
        if "page_count" in kwargs:  # Use this step to simulate work
            async with lock:
                active_count += 1
                max_active = max(max_active, active_count)
            
            await asyncio.sleep(0.1)
            
            async with lock:
                active_count -= 1
        
        # Original update logic (simplified)
        for key, value in kwargs.items():
            setattr(doc, key, value)
        await self.session.commit()

    with (
        patch("mymemex.storage.repositories.DocumentRepository.update", autospec=True, side_effect=mocked_update),
        patch("mymemex.processing.pipeline.extract_text_from_pdf", return_value=[])
    ):
        
        # Run 3 ingestions concurrently
        # IMPORTANT: We simulate what _process_task does (acquiring semaphore)
        sem = _get_ingest_semaphore(test_config)
        
        async def run_with_sem(doc_id):
            async with sem:
                await run_ingest_pipeline(doc_id, test_config)

        tasks = [
            run_with_sem(doc.id)
            for doc in docs
        ]
        await asyncio.gather(*tasks)

    # Verify max_active was at most 2
    assert max_active == 2
    # Verify all were processed
    for doc in docs:
        await db_session.refresh(doc)
        assert doc.status == "processed"

@pytest.mark.asyncio
async def test_single_ingest_works_unchanged(test_config, db_session, sample_pdf):
    # Setup: 1 document
    repo = DocumentRepository(db_session)
    doc = await repo.create(
        content_hash="single_hash",
        quick_hash="single_quick",
        file_size=100,
        original_path=str(sample_pdf),
        original_filename="single.pdf",
        mime_type="application/pdf",
        file_modified_at=123456789.0,
    )
    await db_session.commit()

    # Reset module-level semaphore
    import mymemex.processing.pipeline as pipeline
    pipeline._ingest_semaphore = None

    # Run ingestion
    await run_ingest_pipeline(doc.id, test_config)

    # Verify document is ready (waiting_llm if classification is enabled, else processed)
    await db_session.refresh(doc)
    assert doc.status in ("processed", "waiting_llm")
    assert doc.page_count is not None
