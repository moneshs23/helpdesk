"""Document ingestion pipeline.

validate → extract text → (OCR) → chunk → embed → store in Qdrant (+ metadata).

Embedding and upserting run in batches so arbitrarily large documents (e.g.
Excel workbooks with tens of thousands of rows) never hold the full vector set
in memory, and callers can observe progress while ingestion is running.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.embeddings import get_embedder
from backend.models.enums import DocumentType
from backend.qdrant import get_vector_store
from backend.rag.chunker import chunk_pages
from backend.rag.document_loader import load_document
from backend.utils.logging import logger

# Chunks embedded + upserted per round-trip. The embedder batches further
# internally (settings.embedding_batch_size).
INGEST_BATCH_SIZE = 128

# async callback(chunks_done, chunks_total) invoked after each stored batch.
ProgressCallback = Callable[[int, int], Awaitable[None]]


@dataclass
class IngestResult:
    pages: int
    chunk_count: int
    point_ids: list[str]


async def ingest_document(
    *,
    document_id: str,
    stored_path: Path,
    filename: str,
    title: str,
    doc_type: DocumentType,
    product: str = "",
    upload_date: datetime | None = None,
    on_progress: ProgressCallback | None = None,
) -> IngestResult:
    upload_date = upload_date or datetime.now(timezone.utc)
    logger.info(f"Ingesting document {filename} ({doc_type.value})")

    pages = load_document(stored_path, doc_type)
    if not pages:
        logger.warning(f"No extractable text in {filename}")
        return IngestResult(pages=0, chunk_count=0, point_ids=[])

    chunks = chunk_pages(pages)
    if not chunks:
        return IngestResult(pages=len(pages), chunk_count=0, point_ids=[])

    embedder = get_embedder()
    store = get_vector_store()

    point_ids: list[str] = []
    for start in range(0, len(chunks), INGEST_BATCH_SIZE):
        batch = chunks[start : start + INGEST_BATCH_SIZE]
        texts = [c.text for c in batch]
        vectors = await embedder.embed_documents(texts)
        payloads = [
            {
                "document_id": document_id,
                "filename": filename,
                "title": title,
                "doc_type": doc_type.value,
                "page": c.page,
                "section": c.section,
                "chunk_index": c.index,
                "product": product,
                "upload_date": upload_date.isoformat(),
            }
            for c in batch
        ]
        point_ids.extend(await store.upsert_documents(vectors, payloads, texts))
        if on_progress is not None:
            await on_progress(len(point_ids), len(chunks))

    logger.info(f"Stored {len(point_ids)} chunks for {filename}")
    return IngestResult(
        pages=len(pages), chunk_count=len(chunks), point_ids=point_ids
    )
