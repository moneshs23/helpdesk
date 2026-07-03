"""Document management service: upload, ingest, list, delete, replace, versions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from sqlalchemy import delete, func, select
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
        await self.session.flush()

        try:
            result = await ingest_document(
                document_id=document_id,
                stored_path=dest,
                filename=safe_name,
                title=doc.title,
                doc_type=doc_type,
                product=product or "",
                upload_date=now,
            )
            doc.pages = result.pages
            doc.chunk_count = result.chunk_count
            doc.status = (
                DocumentStatus.READY.value
                if result.chunk_count > 0
                else DocumentStatus.FAILED.value
            )
            if result.chunk_count == 0:
                doc.error = "No extractable text found."
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"Ingestion failed for {safe_name}")
            doc.status = DocumentStatus.FAILED.value
            doc.error = str(exc)

        self.session.add(
            DocumentVersionORM(
                document_id=document_id,
                version=1,
                stored_path=str(dest),
                size_bytes=len(content),
                chunk_count=doc.chunk_count,
                note="Initial upload",
                upload_date=now,
            )
        )
        await self.session.flush()
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

        result = await ingest_document(
            document_id=document_id,
            stored_path=dest,
            filename=safe_name,
            title=doc.title,
            doc_type=doc_type,
            product=doc.product,
            upload_date=now,
        )
        doc.filename = safe_name
        doc.stored_path = str(dest)
        doc.doc_type = doc_type.value
        doc.size_bytes = len(content)
        doc.pages = result.pages
        doc.chunk_count = result.chunk_count
        doc.version += 1
        doc.status = DocumentStatus.READY.value
        doc.error = ""
        doc.upload_date = now

        self.session.add(
            DocumentVersionORM(
                document_id=document_id,
                version=doc.version,
                stored_path=str(dest),
                size_bytes=len(content),
                chunk_count=result.chunk_count,
                note="Replaced",
                upload_date=now,
            )
        )
        await self.session.flush()
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
