"""Document management service: upload, ingest, list, delete, replace, versions.

Ingestion (extract → chunk → embed → store) runs as a background task so large
files (e.g. multi-MB Excel workbooks producing tens of thousands of chunks)
don't block or time out the upload request. The document row is committed with
status ``processing`` first; the task updates ``chunk_count`` as batches land
and flips the status to ``ready``/``failed`` at the end.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.models import DocumentORM, DocumentVersionORM
from backend.models.enums import DocumentStatus, DocumentType
from backend.models.schemas import (
    DocumentMetadata,
    DocumentVersionInfo,
)
from backend.qdrant import get_vector_store
from backend.rag.ingest import ingest_document
from backend.utils.logging import logger
from backend.utils.security import sanitize_filename, validate_upload

# Keep strong references so background ingest tasks aren't garbage-collected.
_INGEST_TASKS: set[asyncio.Task] = set()


class _DocumentDeleted(Exception):
    """Raised when the document row disappears mid-ingest (user deleted it)."""


def _tags_to_list(tags: str) -> list[str]:
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


def _to_metadata(doc: DocumentORM) -> DocumentMetadata:
    return DocumentMetadata(
        id=doc.id,
        filename=doc.filename,
        title=doc.title or doc.filename,
        doc_type=DocumentType.from_extension(doc.doc_type),
        upload_date=doc.upload_date,
        size_bytes=doc.size_bytes,
        pages=doc.pages,
        chunk_count=doc.chunk_count,
        version=doc.version,
        status=DocumentStatus(doc.status),
        tags=_tags_to_list(doc.tags),
        pinned=doc.pinned,
        error=doc.error or None,
    )


async def _run_ingest(
    *,
    document_id: str,
    stored_path: Path,
    filename: str,
    title: str,
    doc_type: DocumentType,
    product: str,
    upload_date: datetime,
    version: int,
) -> None:
    """Background ingestion: updates the document row as batches are stored."""
    from backend.database.session import AsyncSessionLocal  # noqa: PLC0415

    async def on_progress(done: int, total: int) -> None:
        async with AsyncSessionLocal() as session:
            doc = await session.get(DocumentORM, document_id)
            if doc is None:
                raise _DocumentDeleted(document_id)
            doc.chunk_count = done
            await session.commit()

    try:
        result = await ingest_document(
            document_id=document_id,
            stored_path=stored_path,
            filename=filename,
            title=title,
            doc_type=doc_type,
            product=product,
            upload_date=upload_date,
            on_progress=on_progress,
        )
    except _DocumentDeleted:
        # Deleted while processing: drop any vectors stored since the delete.
        logger.info(f"Document {document_id} deleted mid-ingest; cleaning up.")
        await get_vector_store().delete_document(document_id)
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Ingestion failed for {filename}")
        async with AsyncSessionLocal() as session:
            doc = await session.get(DocumentORM, document_id)
            if doc is not None:
                doc.status = DocumentStatus.FAILED.value
                doc.error = str(exc)
                await session.commit()
        return

    async with AsyncSessionLocal() as session:
        doc = await session.get(DocumentORM, document_id)
        if doc is None:
            await get_vector_store().delete_document(document_id)
            return
        doc.pages = result.pages
        doc.chunk_count = result.chunk_count
        doc.status = (
            DocumentStatus.READY.value
            if result.chunk_count > 0
            else DocumentStatus.FAILED.value
        )
        doc.error = "" if result.chunk_count > 0 else "No extractable text found."
        await session.execute(
            update(DocumentVersionORM)
            .where(
                DocumentVersionORM.document_id == document_id,
                DocumentVersionORM.version == version,
            )
            .values(chunk_count=result.chunk_count)
        )
        await session.commit()


def _spawn_ingest(**kwargs) -> None:
    task = asyncio.create_task(_run_ingest(**kwargs))
    _INGEST_TASKS.add(task)
    task.add_done_callback(_INGEST_TASKS.discard)


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.store = get_vector_store()

    async def _save_file(self, content: bytes, filename: str) -> tuple[Path, str]:
        safe = sanitize_filename(filename)
        unique = f"{uuid.uuid4().hex[:8]}_{safe}"
        dest = settings.upload_path / unique
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)
        return dest, safe

    async def upload(
        self,
        *,
        content: bytes,
        filename: str,
        title: str | None = None,
        product: str = "",
        tags: list[str] | None = None,
    ) -> DocumentMetadata:
        doc_type = validate_upload(filename, len(content))

        # Re-uploading a file replaces any existing document with the same name.
        duplicates = (
            (
                await self.session.execute(
                    select(DocumentORM.id).where(
                        DocumentORM.filename == sanitize_filename(filename)
                    )
                )
            )
            .scalars()
            .all()
        )
        for old_id in duplicates:
            await self.delete(old_id)

        dest, safe_name = await self._save_file(content, filename)

        document_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        doc = DocumentORM(
            id=document_id,
            filename=safe_name,
            stored_path=str(dest),
            title=(title or Path(safe_name).stem).strip(),
            doc_type=doc_type.value,
            size_bytes=len(content),
            product=product or "",
            tags=",".join(tags or []),
            status=DocumentStatus.PROCESSING.value,
            upload_date=now,
        )
        self.session.add(doc)
        self.session.add(
            DocumentVersionORM(
                document_id=document_id,
                version=1,
                stored_path=str(dest),
                size_bytes=len(content),
                chunk_count=0,
                note="Initial upload",
                upload_date=now,
            )
        )
        # Commit before spawning so the background task's session sees the row.
        await self.session.commit()

        _spawn_ingest(
            document_id=document_id,
            stored_path=dest,
            filename=safe_name,
            title=doc.title,
            doc_type=doc_type,
            product=product or "",
            upload_date=now,
            version=1,
        )
        return _to_metadata(doc)

    async def replace(
        self, document_id: str, *, content: bytes, filename: str
    ) -> DocumentMetadata:
        doc = await self.session.get(DocumentORM, document_id)
        if doc is None:
            raise ValueError("Document not found")

        doc_type = validate_upload(filename, len(content))
        # Remove old vectors, keep old file for version history.
        await self.store.delete_document(document_id)
        dest, safe_name = await self._save_file(content, filename)
        now = datetime.now(timezone.utc)

        doc.filename = safe_name
        doc.stored_path = str(dest)
        doc.doc_type = doc_type.value
        doc.size_bytes = len(content)
        doc.pages = 0
        doc.chunk_count = 0
        doc.version += 1
        doc.status = DocumentStatus.PROCESSING.value
        doc.error = ""
        doc.upload_date = now

        self.session.add(
            DocumentVersionORM(
                document_id=document_id,
                version=doc.version,
                stored_path=str(dest),
                size_bytes=len(content),
                chunk_count=0,
                note="Replaced",
                upload_date=now,
            )
        )
        await self.session.commit()

        _spawn_ingest(
            document_id=document_id,
            stored_path=dest,
            filename=safe_name,
            title=doc.title,
            doc_type=doc_type,
            product=doc.product,
            upload_date=now,
            version=doc.version,
        )
        return _to_metadata(doc)

    async def list_documents(
        self, *, product: str | None = None, query: str | None = None
    ) -> list[DocumentMetadata]:
        stmt = select(DocumentORM).order_by(
            DocumentORM.pinned.desc(), DocumentORM.upload_date.desc()
        )
        if product:
            stmt = stmt.where(DocumentORM.product == product)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                DocumentORM.filename.ilike(like) | DocumentORM.title.ilike(like)
            )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_metadata(d) for d in rows]

    async def get(self, document_id: str) -> DocumentMetadata | None:
        doc = await self.session.get(DocumentORM, document_id)
        return _to_metadata(doc) if doc else None

    async def get_stored_path(self, document_id: str) -> Path | None:
        doc = await self.session.get(DocumentORM, document_id)
        return Path(doc.stored_path) if doc else None

    async def versions(self, document_id: str) -> list[DocumentVersionInfo]:
        stmt = (
            select(DocumentVersionORM)
            .where(DocumentVersionORM.document_id == document_id)
            .order_by(DocumentVersionORM.version.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            DocumentVersionInfo(
                version=r.version,
                upload_date=r.upload_date,
                size_bytes=r.size_bytes,
                chunk_count=r.chunk_count,
                note=r.note or None,
            )
            for r in rows
        ]

    async def update_metadata(
        self,
        document_id: str,
        *,
        title: str | None = None,
        tags: list[str] | None = None,
        pinned: bool | None = None,
        product: str | None = None,
    ) -> DocumentMetadata | None:
        doc = await self.session.get(DocumentORM, document_id)
        if doc is None:
            return None
        if title is not None:
            doc.title = title
        if tags is not None:
            doc.tags = ",".join(tags)
        if pinned is not None:
            doc.pinned = pinned
        if product is not None:
            doc.product = product
        await self.session.flush()
        return _to_metadata(doc)

    async def delete(self, document_id: str) -> bool:
        doc = await self.session.get(DocumentORM, document_id)
        if doc is None:
            return False
        await self.store.delete_document(document_id)
        try:
            Path(doc.stored_path).unlink(missing_ok=True)
        except OSError:
            pass
        await self.session.execute(
            delete(DocumentVersionORM).where(
                DocumentVersionORM.document_id == document_id
            )
        )
        await self.session.delete(doc)
        await self.session.flush()
        logger.info(f"Deleted document {document_id}")
        return True

    async def reindex_all(self) -> dict:
        """Re-chunk and re-embed every stored document, replacing old vectors."""
        docs = (await self.session.execute(select(DocumentORM))).scalars().all()
        reindexed = 0
        failed = 0
        for doc in docs:
            path = Path(doc.stored_path)
            if not path.exists():
                doc.status = DocumentStatus.FAILED.value
                doc.error = "Stored file is missing."
                failed += 1
                continue
            try:
                await self.store.delete_document(doc.id)
                result = await ingest_document(
                    document_id=doc.id,
                    stored_path=path,
                    filename=doc.filename,
                    title=doc.title or doc.filename,
                    doc_type=DocumentType.from_extension(doc.doc_type),
                    product=doc.product or "",
                    upload_date=doc.upload_date,
                )
                doc.pages = result.pages
                doc.chunk_count = result.chunk_count
                if result.chunk_count > 0:
                    doc.status = DocumentStatus.READY.value
                    doc.error = ""
                    reindexed += 1
                else:
                    doc.status = DocumentStatus.FAILED.value
                    doc.error = "No extractable text found."
                    failed += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"Reindex failed for {doc.filename}")
                doc.status = DocumentStatus.FAILED.value
                doc.error = str(exc)
                failed += 1
        await self.session.flush()
        return {"total": len(docs), "reindexed": reindexed, "failed": failed}

    async def count(self) -> int:
        return int(
            (await self.session.execute(select(func.count(DocumentORM.id)))).scalar() or 0
        )

    async def recent(self, limit: int = 5) -> list[DocumentMetadata]:
        stmt = (
            select(DocumentORM)
            .order_by(DocumentORM.upload_date.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_metadata(d) for d in rows]
