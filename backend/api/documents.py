"""Document management endpoints: list, get, delete, replace, versions, preview."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.api.deps import DocumentServiceDep
from backend.models.schemas import (
    DocumentListResponse,
    DocumentMetadata,
    DocumentVersionInfo,
    MessageResponse,
    UploadResponse,
)
from backend.utils.logging import logger
from backend.utils.security import ValidationError

router = APIRouter(prefix="/api/documents", tags=["documents"])


class UpdateDocumentRequest(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    pinned: bool | None = None
    product: str | None = None


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDep,
    product: str | None = Query(None),
    query: str | None = Query(None),
) -> DocumentListResponse:
    docs = await service.list_documents(product=product, query=query)
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str, service: DocumentServiceDep) -> DocumentMetadata:
    doc = await service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/versions", response_model=list[DocumentVersionInfo])
async def get_versions(
    document_id: str, service: DocumentServiceDep
) -> list[DocumentVersionInfo]:
    return await service.versions(document_id)


@router.get("/{document_id}/preview")
async def preview_document(document_id: str, service: DocumentServiceDep):
    path = await service.get_stored_path(document_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=path.name)


@router.patch("/{document_id}", response_model=DocumentMetadata)
async def update_document(
    document_id: str, body: UpdateDocumentRequest, service: DocumentServiceDep
) -> DocumentMetadata:
    doc = await service.update_metadata(
        document_id,
        title=body.title,
        tags=body.tags,
        pinned=body.pinned,
        product=body.product,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.put("/{document_id}/replace", response_model=UploadResponse)
async def replace_document(
    document_id: str, service: DocumentServiceDep, file: UploadFile = File(...)
) -> UploadResponse:
    content = await file.read()
    try:
        doc = await service.replace(
            document_id, content=content, filename=file.filename or "document"
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Replace failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return UploadResponse(document=doc, message="Document replaced successfully.")


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: str, service: DocumentServiceDep
) -> MessageResponse:
    ok = await service.delete(document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return MessageResponse(message="Document deleted.")
