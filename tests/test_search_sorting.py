"""Search result ordering and date metadata."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from mymemex.services.search import SearchService
from mymemex.storage.repositories import ChunkRepository, DocumentRepository


async def _make_doc(doc_repo, *, seed: str, document_date=None, modified=1700000000.0):
    """Create a document with one matching chunk."""
    doc = await doc_repo.create(
        content_hash=seed * 64,
        quick_hash=f"100:{seed * 16}",
        file_size=1024,
        original_path=f"/tmp/{seed}.pdf",
        original_filename=f"{seed}.pdf",
        mime_type="application/pdf",
        file_modified_at=modified,
    )
    if document_date is not None:
        doc.document_date = document_date
    return doc


@pytest.mark.asyncio
async def test_keyword_search_defaults_to_newest_first(db_session, test_config):
    """Default ordering is by document date, newest first."""
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    old = await _make_doc(doc_repo, seed="a", document_date=date(2020, 1, 15))
    new = await _make_doc(doc_repo, seed="b", document_date=date(2024, 6, 1))
    middle = await _make_doc(doc_repo, seed="c", document_date=date(2022, 3, 9))

    for doc in (old, new, middle):
        await chunk_repo.create(
            document_id=doc.id,
            chunk_index=0,
            text="Insurance policy coverage details",
            char_count=33,
            page_number=1,
            extraction_method="pymupdf_native",
        )
    await db_session.commit()

    service = SearchService(db_session, test_config)
    results, total = await service.keyword_search("insurance")

    assert total == 3
    assert [r["document_id"] for r in results] == [new.id, middle.id, old.id]
    assert [r["effective_date"][:10] for r in results] == [
        "2024-06-01",
        "2022-03-09",
        "2020-01-15",
    ]
    assert all(r["date_source"] == "document" for r in results)


@pytest.mark.asyncio
async def test_keyword_search_relevance_sort_is_opt_in(db_session, test_config):
    """sort=relevance restores FTS5 rank ordering."""
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    # The older document is the stronger match (term appears repeatedly).
    strong = await _make_doc(doc_repo, seed="a", document_date=date(2019, 1, 1))
    weak = await _make_doc(doc_repo, seed="b", document_date=date(2025, 1, 1))

    await chunk_repo.create(
        document_id=strong.id,
        chunk_index=0,
        text="insurance insurance insurance insurance policy",
        char_count=46,
        page_number=1,
        extraction_method="pymupdf_native",
    )
    await chunk_repo.create(
        document_id=weak.id,
        chunk_index=0,
        text="a long passage about many unrelated subjects that mentions insurance once",
        char_count=73,
        page_number=1,
        extraction_method="pymupdf_native",
    )
    await db_session.commit()

    service = SearchService(db_session, test_config)

    by_date, _ = await service.keyword_search("insurance", sort="date")
    assert [r["document_id"] for r in by_date] == [weak.id, strong.id]

    by_rank, _ = await service.keyword_search("insurance", sort="relevance")
    assert by_rank[0]["document_id"] == strong.id


@pytest.mark.asyncio
async def test_date_falls_back_when_document_date_missing(db_session, test_config):
    """Documents with no extracted date fall back to file mtime, flagged as such."""
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    dated = await _make_doc(doc_repo, seed="a", document_date=date(2021, 5, 5))
    undated = await _make_doc(
        doc_repo, seed="b", modified=datetime(2023, 8, 8).timestamp()
    )

    for doc in (dated, undated):
        await chunk_repo.create(
            document_id=doc.id,
            chunk_index=0,
            text="Insurance policy coverage details",
            char_count=33,
            page_number=1,
            extraction_method="pymupdf_native",
        )
    await db_session.commit()

    service = SearchService(db_session, test_config)
    results, _ = await service.keyword_search("insurance")

    by_id = {r["document_id"]: r for r in results}
    assert by_id[dated.id]["date_source"] == "document"
    assert by_id[dated.id]["document_date"] == "2021-05-05"
    assert by_id[undated.id]["date_source"] == "modified"
    assert by_id[undated.id]["document_date"] is None
    assert by_id[undated.id]["effective_date"][:10] == "2023-08-08"

    # The fallback date still participates in ordering.
    assert [r["document_id"] for r in results] == [undated.id, dated.id]


@pytest.mark.asyncio
async def test_date_sort_paginates_over_whole_result_set(db_session, test_config):
    """Ordering is applied in SQL, so page 2 continues the date sequence."""
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    docs = []
    for i, seed in enumerate("abcd"):
        doc = await _make_doc(doc_repo, seed=seed, document_date=date(2020 + i, 1, 1))
        docs.append(doc)
        await chunk_repo.create(
            document_id=doc.id,
            chunk_index=0,
            text="Insurance policy coverage details",
            char_count=33,
            page_number=1,
            extraction_method="pymupdf_native",
        )
    await db_session.commit()

    service = SearchService(db_session, test_config)
    page1, total = await service.keyword_search("insurance", page=1, per_page=2)
    page2, _ = await service.keyword_search("insurance", page=2, per_page=2)

    assert total == 4
    assert [r["document_id"] for r in page1] == [docs[3].id, docs[2].id]
    assert [r["document_id"] for r in page2] == [docs[1].id, docs[0].id]


def test_apply_sort_puts_undated_results_last():
    """Results with no date sort after dated ones rather than first."""
    results = [
        {"document_id": 1, "effective_date": None},
        {"document_id": 2, "effective_date": "2022-01-01"},
        {"document_id": 3, "effective_date": "2024-01-01"},
    ]

    ordered = SearchService._apply_sort(results, "date")
    assert [r["document_id"] for r in ordered] == [3, 2, 1]

    # Relevance leaves the caller's order untouched.
    assert SearchService._apply_sort(results, "relevance") == results
